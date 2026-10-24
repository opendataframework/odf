# 23 — Reverse Proxy

A project deployed the way [Deploying](../../docs/ui.md#deploying) describes:
`odf run` in one container, [Traefik](https://doc.traefik.io/traefik/) in front
of it with HTTPS and a login, the UI at `https://localhost/` and the MCP server
at `https://localhost/mcp`. The project is a `Notebooks` repository like
[`21-notebook-view`](../21-notebook-view/)'s, so **Edit in Jupyter** can be
tried through the proxy too. The setup is the point: `compose.yaml` and
`traefik/`.

## Run it

Needs Docker with Compose. Set a password for the login, then start it:

```bash
cd examples/23-reverse-proxy
cp .env.example .env    # and set ODF_PASSWORD in it
docker compose up --build
```

Open `https://localhost/` and sign in as `odf` (or `ODF_USER`) with that
password. The certificate is self-signed, generated into `secrets/` on first
start, so the browser warns about it once.

Click **View Documents** on `Notebooks`, open `scratch`, and press **Edit in
Jupyter**: Jupyter's editor and its kernel run through the proxy, at
`/proxy/jupyter/` with kernels over `wss://`, behind the same login and with
nothing Jupyter-specific in Traefik's config. Notebooks saved there land in
`notebooks/` on your machine, which is mounted into the container.

## What each piece is for

**Ports off the network.** `odf run` binds to `0.0.0.0` so Traefik's container
reaches it, and `compose.yaml` only `expose`s 4747 and 4748 to the compose
network: nothing but Traefik can reach the UI or the MCP server, so nothing
gets around the login. Only Traefik publishes ports, 443, and 80 to redirect to
HTTPS.

**The login.** The UI and the MCP server have none of their own. A `basicAuth`
middleware in `traefik/dynamic.toml` checks every request against
`secrets/users`, which the one-shot `setup` service writes from `ODF_USER` and
`ODF_PASSWORD` with `htpasswd`.

**`passHostHeader = false`.** Traefik then sends the upstream's own host as
`Host`, and the host the browser asked for as `X-Forwarded-Host`, which it sets
by default. The UI compares a request's `Origin` with that host, and refuses
saves, Runs and Jupyter's WebSockets that don't match as cross-site. In a
container the setting makes no difference, since a UI bound to `0.0.0.0`
answers any `Host`. On the proxy's own machine, with the UI bound to
`127.0.0.1`, it's required: that UI only answers loopback hosts, and answers
`Host: odf.example.com` with 421.

**What Traefik already does.** It passes WebSocket upgrades on (Jupyter's
kernels need them), streams responses as they come (the UI's `/api/events` and
the MCP server's event streams), and doesn't limit request bodies (saving a
notebook sends it whole). nginx needs each of these set by hand; see
[nginx and other proxies](../../docs/ui.md#nginx-and-other-proxies).

## Connecting an MCP client

MCP clients can't go through a browser login, so they send the credentials
themselves, as a Basic auth header. With Claude Code, trusting the generated
certificate:

```bash
claude mcp add --transport http reverse-proxy https://localhost/mcp \
  --header "Authorization: Basic $(printf 'odf:YOUR_PASSWORD' | base64)"
NODE_EXTRA_CA_CERTS=secrets/odf.crt claude
```

## Logging in with an identity provider

`compose.oidc.yaml` swaps the password file for
[oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/) and your identity
provider (any OpenID Connect one: Google, GitHub, Microsoft Entra, Keycloak,
...). Register a client with `https://localhost/oauth2/callback` as its
redirect URL, fill in the `OIDC_*` and `OAUTH2_PROXY_COOKIE_SECRET` values in
`.env`, and start both files:

```bash
docker compose -f compose.yaml -f compose.oidc.yaml up --build
```

Traefik now uses `traefik/dynamic.oidc.toml`, whose `forwardAuth` middleware
asks oauth2-proxy about every request. A browser that isn't signed in gets
oauth2-proxy's sign-in page through an `errors` middleware, for 401s only, so
the UI's own 403s pass through as they are. `/mcp` has no sign-in page: an MCP
client sends a token from your provider (`Authorization: Bearer ...`), which
oauth2-proxy accepts with `OAUTH2_PROXY_SKIP_JWT_BEARER_TOKENS`. odf itself
needs no configuration for either login.

## Going to production

- Add a `Host` rule to each router, such as
  ``rule = "Host(`odf.example.com`) && PathPrefix(`/`)"``. Serve odf at the
  root of a host, a subdomain if the domain serves other things: the UI can't
  run under a subpath yet.
- Replace the self-signed certificate with one from Let's Encrypt: a
  `certificatesResolvers` entry with an ACME challenge in `traefik/traefik.toml`,
  and `certResolver` on the routers' `tls`.
- Keep `secrets/` and `.env` out of version control (`.gitignore` here does).

## Trying unreleased odf

The image installs `odf` from PyPI. To try builds that aren't published yet,
serve their wheels from a local package index and point the build at it with
`ODF_INDEX_URL`, which pip looks in besides PyPI:

```bash
# in odf/ (and opendataframework/, if its version isn't on PyPI either)
poetry build
mkdir -p /tmp/wheels && cp dist/*.whl /tmp/wheels/

docker run -d --rm -p 8080:8080 -v /tmp/wheels:/data/packages \
  pypiserver/pypiserver:latest run -a . -P .

cd examples/23-reverse-proxy
ODF_INDEX_URL=http://host.docker.internal:8080/simple/ docker compose up --build
```

## Structure

```
23-reverse-proxy/
├── Dockerfile           # odf[ui,mcp,notebook] from PyPI, then odf run --ui-host 0.0.0.0 --mcp --mcp-host 0.0.0.0
├── compose.yaml         # odf, the one-shot setup (certificate, password file) and Traefik
├── compose.oidc.yaml    # oauth2-proxy in place of the password file
├── .env.example         # the password, the identity provider, ODF_INDEX_URL
├── traefik/
│   ├── traefik.toml     # static config: HTTPS on 443, 80 redirecting to it, routes from a file
│   ├── dynamic.toml     # the UI at /, MCP at /mcp, behind basicAuth
│   └── dynamic.oidc.toml  # the same behind oauth2-proxy (forwardAuth)
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — lists the notebooks, without Docker
├── notebooks/
│   └── scratch.ipynb    # a short notebook to edit through the proxy
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py      # Notebook(name, content) — @Entity
    └── repositories.py  # Notebooks — @Storage @Repository(Notebook), one record per .ipynb file
```
