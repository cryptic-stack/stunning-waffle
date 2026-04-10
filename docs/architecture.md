# Architecture

## Overview

The platform is organized around a small control plane and short-lived browser session workers:

- `apps/frontend`: React UI for launching and viewing browser and desktop sessions
- `apps/api`: FastAPI REST, signaling, TTL, and cleanup control plane
- `apps/session-agent`: worker-side runtime launch, media, and input bridge
- `images/*`: Chromium, Firefox, Brave, Edge, Vivaldi, Ubuntu XFCE, and Kali XFCE worker images
- `infra/`: local deployment and edge configuration assets

## Current system boundaries

Implemented:

- session lifecycle orchestration in Postgres + Redis
- thin WebSocket signaling between viewer and worker peers
- WebRTC viewer negotiation with media outside the control plane
- Browser and desktop workers launch on the internal Docker network
- direct launch into a requested target URL inside the worker browser
- desktop workers start XFCE sessions inside Xvfb and ignore `target_url` in v1
- single-host local target access by rewriting loopback URLs to the Docker host gateway
- mouse, keyboard, wheel, and clipboard control over a data channel with signaling fallback
- single-host file upload delivery into per-session worker containers
- ownership-aware access checks plus audit-style event records

Still intentionally deferred:

- persistent desktop profiles
- recording pipeline
- arbitrary shell access inside worker containers
- multi-user sharing within the same session

## Planned deployment model

- Frontend served at `browser.example.com`
- API served at `api.example.com`
- TURN served at `turn.example.com`
- session workers remain private on an internal Docker network

## Core infrastructure

- React + TypeScript frontend
- FastAPI backend on Python 3.12
- Redis for TTL and presence
- Postgres for metadata and audits
- coturn for STUN/TURN
- Docker Compose for local and single-host deployment

## Worker model

- one container per session
- non-root runtime user
- read-only root filesystem by default
- tmpfs-backed writable paths for browser state and downloads
- CPU, memory, and pid limits enforced at container launch
