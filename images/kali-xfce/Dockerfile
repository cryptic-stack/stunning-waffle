FROM python:3.12-slim AS python-builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY apps/session-agent/pyproject.toml /app/pyproject.toml
COPY apps/session-agent/session_agent /app/session_agent

RUN python -m pip install --upgrade pip && \
    python -m pip install .

FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV PATH="/usr/local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    dbus-x11 \
    firefox-esr \
    fonts-liberation \
    fonts-noto-color-emoji \
    kali-defaults \
    kali-desktop-xfce \
    kali-menu \
    kali-themes \
    kali-tools-top10 \
    sudo \
    thunar \
    xclip \
    xdotool \
    xfce4-terminal \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-builder /usr/local /usr/local

RUN useradd --create-home --shell /bin/bash browserlab && \
    usermod -aG sudo browserlab && \
    echo "browserlab ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/browserlab && \
    chmod 0440 /etc/sudoers.d/browserlab

WORKDIR /home/browserlab

USER browserlab

ENTRYPOINT ["browserlab-session-agent"]
