# One image for every simulated tool; compose.yaml picks which one a container
# runs (uvicorn tools.world:app, tools.pos:app or tools.messenger:app).
FROM python:3.14-slim

RUN pip install --no-cache-dir "fastapi==0.141.1" "uvicorn==0.54.0"

RUN useradd --create-home tools && install -d -o tools /srv/tools /data /shared-drive
WORKDIR /srv/tools
COPY --chown=tools tools tools
USER tools

ENV DATA_DIR=/data
