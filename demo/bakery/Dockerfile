# The bakery's odf project, with odf installed from this repository's own
# source, so the demo always runs the odf it sits next to. Built from the
# repository root (see compose.yaml); Dockerfile.dockerignore keeps the context
# down to what's copied below.
FROM python:3.14-slim

WORKDIR /src/odf
COPY pyproject.toml README.md ./
COPY src src
# A package index to look in besides PyPI, for an opendataframework release
# that isn't published yet (see "Unreleased opendataframework" in the README).
# Unset, everything comes from PyPI.
ARG ODF_INDEX_URL=""
RUN if [ -n "$ODF_INDEX_URL" ]; then \
        host=$(printf '%s' "$ODF_INDEX_URL" | sed -E 's#^[a-z]+://([^/@]*@)?([^/:]+).*#\2#'); \
        set -- --extra-index-url "$ODF_INDEX_URL" --trusted-host "$host"; \
    fi; \
    pip install --no-cache-dir "$@" ".[ui,mcp,chat]"

RUN useradd --create-home bakery && install -d -o bakery /srv/bakery /srv/bakery/data /shared-drive
WORKDIR /srv/bakery
COPY --chown=bakery demo/bakery/config.toml demo/bakery/layout.json ./
COPY --chown=bakery demo/bakery/app app
COPY --chown=bakery demo/bakery/icons icons
USER bakery

# The UI and MCP bind every interface inside the container; compose publishes
# them on the host's loopback only. The webhook receiver (4750) is reachable
# from the other containers only.
EXPOSE 4747 4748 4750
CMD ["odf", "run", "--ui-host", "0.0.0.0", "--mcp", "--mcp-host", "0.0.0.0", "--chat"]
