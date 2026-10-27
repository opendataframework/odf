import os
import shutil
import subprocess
import tomllib

import pytest

from .conftest import EXAMPLE_DIR

TRAEFIK = EXAMPLE_DIR / "traefik"
DYNAMIC = ["dynamic.toml", "dynamic.oidc.toml"]


def _dynamic(name):
    return tomllib.loads((TRAEFIK / name).read_text())


def _service_block(compose, name):
    """The lines of ``compose.yaml``'s service ``name``, up to the next service."""
    lines = compose.splitlines()
    start = lines.index(f"  {name}:") + 1
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("  ") and lines[i][2] != " "),
        len(lines),
    )
    return lines[start:end]


def test_traefik_listens_on_https_and_reads_the_dynamic_file():
    static = tomllib.loads((TRAEFIK / "traefik.toml").read_text())

    assert static["entryPoints"]["websecure"]["address"] == ":443"
    assert static["entryPoints"]["web"]["http"]["redirections"]["entryPoint"]["to"] == "websecure"
    assert static["providers"]["file"]["filename"] == "/etc/traefik/dynamic.toml"


@pytest.mark.parametrize("name", DYNAMIC)
def test_ui_and_mcp_are_routed_behind_the_login(name):
    http = _dynamic(name)["http"]
    routers, services = http["routers"], http["services"]

    assert routers["odf"]["rule"] == "PathPrefix(`/`)"
    assert routers["mcp"]["rule"] == "PathPrefix(`/mcp`)"
    assert routers["mcp"]["priority"] > routers["odf"]["priority"]
    for key, url in [("odf", "http://odf:4747"), ("mcp", "http://odf:4748")]:
        router = routers[key]
        assert "login" in router["middlewares"]
        assert router["entryPoints"] == ["websecure"] and "tls" in router
        balancer = services[router["service"]]["loadBalancer"]
        assert balancer["servers"] == [{"url": url}]
        assert balancer["passHostHeader"] is False


@pytest.mark.parametrize("name", DYNAMIC)
def test_the_generated_certificate_is_the_default(name):
    default = _dynamic(name)["tls"]["stores"]["default"]["defaultCertificate"]

    assert default == {
        "certFile": "/etc/traefik/secrets/odf.crt",
        "keyFile": "/etc/traefik/secrets/odf.key",
    }


def test_the_identity_provider_signs_in_browsers_but_not_mcp_clients():
    http = _dynamic("dynamic.oidc.toml")["http"]

    assert http["middlewares"]["login"]["forwardAuth"]["address"] == (
        "http://oauth2-proxy:4180/oauth2/auth"
    )
    assert http["middlewares"]["sign-in"]["errors"]["status"] == ["401"]
    assert http["routers"]["odf"]["middlewares"] == ["sign-in", "login"]
    assert http["routers"]["mcp"]["middlewares"] == ["login"]
    assert http["routers"]["oauth2"]["rule"] == "PathPrefix(`/oauth2/`)"


def test_odf_s_ports_are_only_exposed_to_the_compose_network():
    odf = _service_block((EXAMPLE_DIR / "compose.yaml").read_text(), "odf")

    assert "    expose:" in odf
    assert "    ports:" not in odf


def test_a_local_package_index_is_optional():
    dockerfile = (EXAMPLE_DIR / "Dockerfile").read_text()
    odf = _service_block((EXAMPLE_DIR / "compose.yaml").read_text(), "odf")

    assert 'ARG ODF_INDEX_URL=""' in dockerfile
    assert 'if [ -n "$ODF_INDEX_URL" ]; then' in dockerfile
    assert '"odf[ui,mcp,notebook]>=0.4.0,<0.5.0"' in dockerfile
    assert "        ODF_INDEX_URL: ${ODF_INDEX_URL:-}" in odf


@pytest.mark.skipif(shutil.which("docker") is None, reason="needs the docker CLI")
@pytest.mark.parametrize("files", [["compose.yaml"], ["compose.yaml", "compose.oidc.yaml"]])
def test_compose_files_parse(files):
    env = os.environ | {
        "OIDC_ISSUER_URL": "https://id.example.com",
        "OIDC_CLIENT_ID": "odf",
        "OIDC_CLIENT_SECRET": "secret",
        "OAUTH2_PROXY_COOKIE_SECRET": "secret",
    }
    args = [arg for f in files for arg in ("-f", f)]

    result = subprocess.run(
        ["docker", "compose", *args, "config", "--quiet"],
        cwd=EXAMPLE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    if "is not a docker command" in result.stderr:
        pytest.skip("needs docker compose")
    assert result.returncode == 0, result.stderr
