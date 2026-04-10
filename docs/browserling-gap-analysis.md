# Browserling Gap Analysis

## Scope

This comparison uses Browserling's public product materials as of 2026-04-09 and compares them against the current `foss-browserlab` repository state.

Primary Browserling sources:

- https://www.browserling.com/browser-sandbox
- https://www.browserling.com/local-testing
- https://www.browserling.com/api
- https://www.browserling.com/ftp/browserling-features.pdf
- https://www.browserling.com/ftp/browserling-security.pdf

## Where We Match Today

- Real interactive remote browsers: Browserling describes live, interactive browsers running on their infrastructure, and `foss-browserlab` already delivers live Chromium, Firefox, Brave, Edge, and Vivaldi sessions through an HTML5 viewer with WebRTC media.
- Ephemeral session model: Browserling emphasizes fresh, disposable environments per session. Our platform launches one isolated worker container per session, enforces TTL and idle cleanup, and destroys workers on close or expiry.
- Core interaction path: Mouse, keyboard, wheel input, clipboard sync, and file upload are implemented end to end.
- Self-hosted control plane: Our React, FastAPI, Redis, Postgres, coturn, and Docker deployment model maps well to the "small portal plus disposable workers" architecture goal.
- Thin signaling layer: Browserling's public material separates interactive delivery from orchestration. Our FastAPI service keeps signaling/control thin while media stays on the peer path.

## Partial Parity

- Security isolation: Browserling publicly positions each session as a dedicated VM with stronger isolation claims. We currently use hardened Docker containers with non-root execution, read-only rootfs, tmpfs scratch paths, and quotas. This is good MVP hardening, but it is not VM or hypervisor isolation.
- URL launch: Browserling lets users jump directly into a chosen site. `foss-browserlab` now supports launching sessions to a requested `target_url`, but we do not yet support saved launch profiles, one-click presets, or tunnel-backed private URLs.
- Embedded browser API: Browserling's Live API is aimed at embedding and automating browsers from third-party apps. We now expose a bearer-authenticated automation session API plus session-scoped viewer signaling tokens, but we still do not provide a full public SDK, white-label API surface, or non-WebRTC automation modes.
- Debugging and power-user workflows: Because the worker runs a real headful browser, built-in browser tools are available in principle, and we now provide download-out plus screenshot capture. We still do not provide explicit UX around DevTools, recording export, or browser extension workflows.
- Metadata retention: Browserling says session content and URLs are not persistently retained in normal operation. We already prune old closed sessions, but we intentionally retain some session metadata and audit records for operations and multi-user accountability.

## Clear Gaps Versus Browserling

- Browser and OS coverage: Browserling markets Chrome, Firefox, Safari, Opera, Edge, IE, Tor, Android, iOS, macOS, and multiple Windows generations. We currently ship Chromium, Firefox, Brave, Edge, and Vivaldi workers on Linux, but still do not cover Safari/WebKit, IE, Tor, mobile, or non-Linux worker OS targets.
- Local testing and private app access: Browserling prominently supports reverse SSH tunnels for localhost and internal network testing. `foss-browserlab` now supports single-host local testing by rewriting loopback targets to the Docker host gateway, but we do not yet have a remote tunnel broker or broader private-network reachability path.
- Geo and network controls: Browserling advertises geo-browsing, datacenter/residential/mobile IP choices, custom proxy paths, Bring Your Own IP, and Tor access. We currently have only a coarse outbound allow/deny control for worker containers.
- Downloads and artifacts: Browserling documents both upload-in and download-out flows. We now support upload into the worker, listing and downloading files back out, and PNG screenshot capture. We still do not provide session recording export.
- Team management and enterprise controls: Browserling calls out team management and enterprise workflows. We currently have ownership enforcement and audit events, but not a full admin console, org model, quotas-by-plan, or delegated team management.
- Automation surface: Browserling's Live API markets browser embedding plus automation methods. We now provide an external automation session API and screenshot API, but we do not yet provide headless automation methods, a public SDK, or richer embed primitives.
- Mobile and touch UX: Browserling positions responsive and mobile testing as first-class. Our viewer is desktop-pointer oriented today and does not yet have touch gestures, device presets, or mobile browser workers.

## Recommended Next Phase

The highest-value next phase is `remote private target access`, because the single-host localhost path is now in place and the biggest remaining Browserling parity gap is multi-network access.

Recommended deliverables:

- Add a tunnel broker service for reverse SSH or agent-based local access.
- Extend session create requests with a private target reference, not just a public or host-local `target_url`.
- Issue per-session tunnel credentials and short-lived private target URLs.
- Add recording export for files generated during a session.
- Add explicit viewer UX for DevTools guidance and reconnect/error states around tunneled targets.

## Follow-On Phases

- Browser matrix expansion: add Edge/WebKit/Safari-compatible strategy, then mobile/browser presets.
- Network controls: add per-session proxy selection, geo egress, and optional Tor/proxy chaining.
- Enterprise surface: add org/team model, admin UI, quota controls, and stronger auth proxy integration.
- Isolation upgrade: evaluate Firecracker, Kata Containers, gVisor, or VM-backed workers for customers who need Browserling-like VM isolation claims.

## Bottom Line

`foss-browserlab` now matches Browserling's core interaction model well: real remote browsers, HTML5 delivery, interactive control, ephemeral sessions, and a small orchestration layer. The biggest remaining parity gaps are not the viewer itself, but everything around breadth and enterprise depth: browser/OS coverage, private/local testing, geo/network controls, downloads/artifacts, external embed automation, and stronger isolation semantics.
