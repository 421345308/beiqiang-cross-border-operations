FROM node:22-bookworm-slim

# Explicit build-time override only; never install a floating "latest" release.
ARG CODEX_VERSION=0.166.0
RUN apt-get update \
    && apt-get install --no-install-recommends -y python3 ca-certificates gosu tini passwd \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global --ignore-scripts "@openai/codex@${CODEX_VERSION}" \
    && codex --version \
    && install -d -o node -g node -m 0700 /home/node/.ssh \
    && install -d -m 0700 /root/.ssh \
    && usermod --unlock root

ENV PYTHONUNBUFFERED=1 \
    CODEX_HOME=/var/data/codex \
    WORKBENCH_RUNNER_STATE=/var/data/runner \
    WORKBENCH_RUNNER_PERSISTENT_ROOT=/var/data \
    WORKBENCH_CODEX_VERSION=${CODEX_VERSION} \
    WORKBENCH_RUNNER_URL=https://www.beiqiang.online/api/workbench-runner \
    RUNNER_ENABLED=false

WORKDIR /opt/worker
# The build context is cloud-runner, never the workspace or its local assets.
COPY runner.py preflight.py ./
COPY deploy/entrypoint.sh ./deploy/entrypoint.sh
RUN chmod 0555 /opt/worker/deploy/entrypoint.sh \
    && chmod 0444 /opt/worker/runner.py /opt/worker/preflight.py

# Root only initializes the two exact mounted directories, then drops to node.
# Render Dashboard Shell may enter as root; use gosu node for every Codex command.
USER root
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/worker/deploy/entrypoint.sh"]
