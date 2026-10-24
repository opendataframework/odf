FROM python:3.14-slim

# A package index to look in besides PyPI, for odf or opendataframework
# builds that aren't published yet (see "Trying unreleased odf" in the README).
# Unset, everything comes from PyPI.
ARG ODF_INDEX_URL=""

RUN if [ -n "$ODF_INDEX_URL" ]; then \
        host=$(printf '%s' "$ODF_INDEX_URL" | sed -E 's#^[a-z]+://([^/@]*@)?([^/:]+).*#\2#'); \
        set -- --extra-index-url "$ODF_INDEX_URL" --trusted-host "$host"; \
    fi; \
    pip install --no-cache-dir "$@" "odf[ui,mcp,notebook]>=0.4.0,<0.5.0"

RUN useradd --create-home odf && install -d -o odf /srv/odf
WORKDIR /srv/odf
COPY --chown=odf config.toml main.py ./
COPY --chown=odf app app
COPY --chown=odf notebooks notebooks
USER odf

# Bound to every interface so Traefik's container reaches them; compose only
# exposes these to its own network, never to the host.
EXPOSE 4747 4748
CMD ["odf", "run", "--ui-host", "0.0.0.0", "--mcp", "--mcp-host", "0.0.0.0"]
