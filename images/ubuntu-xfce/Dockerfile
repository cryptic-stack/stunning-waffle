FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DISPLAY=:99
ENV VIRTUAL_ENV=/opt/browserlab-venv
ENV PATH="/opt/browserlab-venv/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    dbus-x11 \
    epiphany-browser \
    fonts-liberation \
    fonts-noto-color-emoji \
    python3 \
    python3-pip \
    python3-venv \
    thunar \
    xclip \
    xdotool \
    xfce4 \
    xfce4-terminal \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash browserlab

WORKDIR /app

COPY apps/session-agent/pyproject.toml /app/pyproject.toml
COPY apps/session-agent/session_agent /app/session_agent

RUN python3 -m venv "${VIRTUAL_ENV}" && \
    "${VIRTUAL_ENV}/bin/pip" install .

USER browserlab

CMD ["browserlab-session-agent"]
