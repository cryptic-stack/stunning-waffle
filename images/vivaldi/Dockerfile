FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    xclip \
    xdotool \
    fonts-liberation \
    fonts-noto-color-emoji \
    xvfb \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://repo.vivaldi.com/archive/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/vivaldi.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/vivaldi.gpg] https://repo.vivaldi.com/archive/deb stable main" > /etc/apt/sources.list.d/vivaldi.list \
    && apt-get update && apt-get install -y --no-install-recommends vivaldi-stable \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash browserlab

WORKDIR /app

COPY apps/session-agent/pyproject.toml /app/pyproject.toml
COPY apps/session-agent/session_agent /app/session_agent

RUN python -m pip install --upgrade pip && python -m pip install .

USER browserlab

CMD ["browserlab-session-agent"]
