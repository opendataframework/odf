# The bakery's odf project, with odf installed from this repository's own
# source, so the demo always runs the odf it sits next to. Built from the
# repository root (see compose.yaml); Dockerfile.dockerignore keeps the context
# down to what's copied below.
FROM python:3.14-slim

WORKDIR /src/odf
COPY pyproject.toml README.md ./
COPY src src
RUN pip install --no-cache-dir ".[ui,mcp,chat]"

RUN useradd --create-home bakery && install -d -o bakery /srv/bakery /srv/bakery/data /shared-drive
WORKDIR /srv/bakery
COPY --chown=bakery demo/bakery/config.toml ./
COPY --chown=bakery demo/bakery/app app
USER bakery

# The UI and MCP bind every interface inside the container; compose publishes
# them on the host's loopback only. The webhook receiver (4750) is reachable
# from the other containers only.
EXPOSE 4747 4748 4750
CMD ["odf", "run", "--ui-host", "0.0.0.0", "--mcp", "--mcp-host", "0.0.0.0"]
