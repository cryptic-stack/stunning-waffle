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
    && curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg \
    && curl -fsSLo /etc/apt/sources.list.d/brave-browser-release.sources https://brave-browser-apt-release.s3.brave.com/brave-browser.sources \
    && apt-get update && apt-get install -y --no-install-recommends brave-browser \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash browserlab

WORKDIR /app

COPY apps/session-agent/pyproject.toml /app/pyproject.toml
COPY apps/session-agent/session_agent /app/session_agent

RUN python -m pip install --upgrade pip && python -m pip install .

USER browserlab

CMD ["browserlab-session-agent"]
