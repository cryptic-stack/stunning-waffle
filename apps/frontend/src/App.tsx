import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, ClipboardEvent, KeyboardEvent, PointerEvent, WheelEvent } from "react";
import {
  type BrowserName,
  type DesktopProfileName,
  defaultSessionRequest,
  type DownloadItem,
  type RtcConfigResponse,
  type SessionKind,
  supportedBrowsers,
  supportedDesktopProfiles,
  type SessionCreateRequest,
  type SessionResponse,
} from "@foss-browserlab/shared-types";
import {
  buildApiUrl,
  buildWebSocketUrl,
  captureSessionScreenshot,
  createSession,
  deleteSession,
  fetchRtcConfig,
  listSessionDownloads,
  listSessions,
  syncSessionClipboard,
  uploadSessionFile,
} from "@foss-browserlab/shared-client";
import {
  isClipboardShortcut,
  projectPointerToSession,
  shouldSendAsTextInput,
  toKeyPayload,
} from "./viewerProtocol";

type ViewportPresetId = "desktop" | "laptop" | "tablet" | "mobile";

const browserCatalog: Record<BrowserName, { label: string; accentClass: string }> = {
  chromium: {
    label: "Chrome",
    accentClass: "is-chromium",
  },
  firefox: {
    label: "Firefox",
    accentClass: "is-firefox",
  },
  brave: {
    label: "Brave",
    accentClass: "is-brave",
  },
  edge: {
    label: "Edge",
    accentClass: "is-edge",
  },
  vivaldi: {
    label: "Vivaldi",
    accentClass: "is-vivaldi",
  },
};

const desktopCatalog: Record<DesktopProfileName, { label: string; accentClass: string }> = {
  "ubuntu-xfce": {
    label: "Ubuntu XFCE",
    accentClass: "is-ubuntu",
  },
  "kali-xfce": {
    label: "Kali XFCE",
    accentClass: "is-kali",
  },
};

const viewportPresets: Array<{
  id: ViewportPresetId;
  label: string;
  width: number;
  height: number;
  description: string;
}> = [
  { id: "desktop", label: "Desktop", width: 1600, height: 900, description: "Wide browser viewport" },
  { id: "laptop", label: "Laptop", width: 1365, height: 768, description: "Typical notebook size" },
  { id: "tablet", label: "Tablet", width: 1024, height: 768, description: "Tablet landscape viewport" },
  { id: "mobile", label: "Mobile", width: 390, height: 844, description: "Tall handset viewport" },
];

function BrowserMark({ browser }: { browser: BrowserName }) {
  if (browser === "chromium") {
    return (
      <svg viewBox="0 0 32 32" aria-hidden="true" className="browser-mark-svg">
        <circle cx="16" cy="16" r="15" fill="#1c2632" />
        <path d="M16 2a14 14 0 0 1 12.12 7H16Z" fill="#ea4335" />
        <path d="M4.4 9h11.6l5.8 10.1-5.8 10A14 14 0 0 1 4.4 9Z" fill="#34a853" />
        <path d="M16 29l5.8-10L28.1 9A14 14 0 0 1 16 29Z" fill="#fbbc05" />
        <circle cx="16" cy="16" r="6.5" fill="#4ea1ff" />
      </svg>
    );
  }
  if (browser === "firefox") {
    return (
      <svg viewBox="0 0 32 32" aria-hidden="true" className="browser-mark-svg">
        <defs>
          <linearGradient id="firefoxGrad" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#ff9b2f" />
            <stop offset="100%" stopColor="#ff4e45" />
          </linearGradient>
        </defs>
        <circle cx="16" cy="16" r="15" fill="url(#firefoxGrad)" />
        <path
          d="M22.6 10.2c-1.7-2.2-4.9-3.5-7.8-2.8 1.4.8 2.2 2 2.3 3.2-3-.3-5.8 2-5.8 5.4 0 3.8 3.2 6.1 6.8 6.1 4.3 0 7.4-3.2 7.4-7.3 0-1.8-.9-3.6-2.9-4.6Z"
          fill="#fff4dc"
        />
      </svg>
    );
  }
  if (browser === "brave") {
    return (
      <svg viewBox="0 0 32 32" aria-hidden="true" className="browser-mark-svg">
        <path
          d="M16 2.5 24.2 5l3 7.2L24 27l-8 2.5L8 27 4.8 12.2 7.8 5Z"
          fill="#ff6a3d"
        />
        <path
          d="M11 11.2 13.2 8h5.6l2.2 3.2-.8 6.4-4.2 3.6-4.2-3.6Z"
          fill="#fff2ec"
        />
      </svg>
    );
  }
  if (browser === "edge") {
    return (
      <svg viewBox="0 0 32 32" aria-hidden="true" className="browser-mark-svg">
        <defs>
          <linearGradient id="edgeGrad" x1="0" x2="1" y1="1" y2="0">
            <stop offset="0%" stopColor="#0f7fdb" />
            <stop offset="100%" stopColor="#2ad2b6" />
          </linearGradient>
        </defs>
        <path
          d="M28 18.5c0 6.1-4.7 11-11.2 11C9.8 29.5 5 25.2 5 19c0-5.6 4.2-10.3 10-10.7 5.7-.5 11.5 3.1 13 10.2Z"
          fill="url(#edgeGrad)"
        />
        <path
          d="M24.8 13.6c-1.2-4-5.6-7.1-10.4-6.6C9.1 7.4 5 11.6 5 17c1.7-2.5 4.6-3.7 7.8-3.7 4 0 7 1.7 8.6 5.2.4-1.3.4-3.1-.1-4.9Z"
          fill="#0b5cc1"
        />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className="browser-mark-svg">
      <circle cx="16" cy="16" r="15" fill="#c6284e" />
      <path d="M10 8h12l-6 16Z" fill="#ffe2ea" />
      <circle cx="16" cy="16" r="3.5" fill="#fff" />
    </svg>
  );
}

function DesktopMark({ profile }: { profile: DesktopProfileName }) {
  const accent = profile === "ubuntu-xfce" ? "#e95420" : "#367bf0";
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className="browser-mark-svg">
      <rect x="4" y="6" width="24" height="16" rx="3" fill="#1c2632" />
      <rect x="7" y="9" width="18" height="10" rx="1.5" fill={accent} />
      <rect x="13" y="24" width="6" height="2" rx="1" fill="#566172" />
      <rect x="10" y="26" width="12" height="2" rx="1" fill="#8d98a7" />
    </svg>
  );
}

function runtimeLabel(session: SessionResponse): string {
  if (session.session_kind === "desktop" && session.desktop_profile) {
    return desktopCatalog[session.desktop_profile].label;
  }
  if (session.browser) {
    return browserCatalog[session.browser].label;
  }
  return "Unknown runtime";
}

function App() {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [statusMessage, setStatusMessage] = useState("Fetching session inventory...");
  const [, setViewerStatus] = useState("Disconnected");
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedSessionKind, setSelectedSessionKind] = useState<SessionKind>(
    defaultSessionRequest.session_kind ?? "browser",
  );
  const [selectedBrowser, setSelectedBrowser] = useState<BrowserName>(
    defaultSessionRequest.browser ?? "chromium",
  );
  const [selectedDesktopProfile, setSelectedDesktopProfile] =
    useState<DesktopProfileName>("ubuntu-xfce");
  const [selectedPreset, setSelectedPreset] = useState<ViewportPresetId>("desktop");
  const [selectedResolution, setSelectedResolution] = useState(defaultSessionRequest.resolution);
  const [targetUrl, setTargetUrl] = useState(defaultSessionRequest.target_url ?? "https://example.com");
  const [rtcConfig, setRtcConfig] = useState<RtcConfigResponse | null>(null);
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const viewerSurfaceRef = useRef<HTMLDivElement | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const negotiationStartedRef = useRef(false);
  const activeSessionRef = useRef<SessionResponse | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const manualDisconnectRef = useRef(false);
  const pointerMoveFrameRef = useRef<number | null>(null);
  const pointerMovePayloadRef = useRef<{ x: number; y: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const viewerAttemptRef = useRef(0);

  async function refreshSessions() {
    const response = await listSessions();
    startTransition(() => {
      setSessions(response.items);
      setStatusMessage(
        response.items.length === 0
          ? "No sessions launched yet."
          : `${response.items.length} session${response.items.length === 1 ? "" : "s"} tracked.`,
      );
    });
  }

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const closeViewer = useCallback(
    (options?: { preserveActiveSession?: boolean; allowReconnect?: boolean }) => {
      manualDisconnectRef.current = !(options?.allowReconnect ?? false);
      viewerAttemptRef.current += 1;
      clearReconnectTimer();
      socketRef.current?.close();
      peerRef.current?.close();
      dataChannelRef.current?.close();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      socketRef.current = null;
      peerRef.current = null;
      dataChannelRef.current = null;
      streamRef.current = null;
      negotiationStartedRef.current = false;
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      if (pointerMoveFrameRef.current !== null) {
        cancelAnimationFrame(pointerMoveFrameRef.current);
        pointerMoveFrameRef.current = null;
      }
      setViewerStatus("Disconnected");
      if (!options?.preserveActiveSession) {
        activeSessionRef.current = null;
        setActiveSessionId(null);
        setDownloads([]);
      }
    },
    [clearReconnectTimer],
  );

  useEffect(() => {
    void Promise.all([refreshSessions(), fetchRtcConfig()])
      .then(([, config]) => {
        setRtcConfig(config);
      })
      .catch((error: Error) => {
        setStatusMessage(error.message);
      });
    return () => closeViewer();
  }, [closeViewer]);

  useEffect(() => {
    const preset = viewportPresets.find((item) => item.id === selectedPreset);
    if (!preset) {
      return;
    }
    setSelectedResolution({ width: preset.width, height: preset.height });
  }, [selectedPreset]);

  function sendControl(event: string, payload?: unknown) {
    const message = JSON.stringify({ type: "control", event, payload });
    if (dataChannelRef.current?.readyState === "open") {
      dataChannelRef.current.send(message);
      return true;
    }
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(message);
      return true;
    }
    return false;
  }

  async function startNegotiation(peerConnection: RTCPeerConnection, websocket: WebSocket) {
    if (negotiationStartedRef.current) {
      return;
    }
    negotiationStartedRef.current = true;
    setViewerStatus("Negotiating...");
    peerConnection.addTransceiver("video", { direction: "recvonly" });
    const controlChannel = peerConnection.createDataChannel("control");
    dataChannelRef.current = controlChannel;
    controlChannel.onopen = () => {
      setViewerStatus("Connected");
      controlChannel.send(JSON.stringify({ type: "control", event: "viewer-ready" }));
      viewerSurfaceRef.current?.focus();
    };
    controlChannel.onmessage = (event) => handleControlMessage(event.data);
    controlChannel.onclose = () => {
      if (dataChannelRef.current === controlChannel) {
        dataChannelRef.current = null;
      }
    };
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    websocket.send(JSON.stringify({ type: "offer", sdp: offer.sdp }));
  }

  async function connectViewer(sessionId: string, options?: { reconnecting?: boolean }) {
    clearReconnectTimer();
    manualDisconnectRef.current = true;
    closeViewer({ preserveActiveSession: true });
    manualDisconnectRef.current = false;
    const attemptId = viewerAttemptRef.current;
    setActiveSessionId(sessionId);
    const session = sessions.find((item) => item.session_id === sessionId) ?? activeSessionRef.current;
    activeSessionRef.current = session ?? null;
    setViewerStatus(options?.reconnecting ? "Reconnecting..." : "Connecting...");

    const peerConnection = new RTCPeerConnection({
      iceTransportPolicy: "relay",
      iceServers:
        rtcConfig?.ice_servers.map((server) => ({
          urls: server.urls,
          username: server.username ?? undefined,
          credential: server.credential ?? undefined,
        })) ?? [],
    });
    const websocket = new WebSocket(buildWebSocketUrl(`/ws/signaling/${sessionId}`));
    const mediaStream = new MediaStream();

    streamRef.current = mediaStream;
    peerRef.current = peerConnection;
    socketRef.current = websocket;

    if (videoRef.current) {
      videoRef.current.srcObject = mediaStream;
    }

    peerConnection.ontrack = (event) => {
      if (peerRef.current !== peerConnection || streamRef.current !== mediaStream) {
        return;
      }
      if (event.streams[0]) {
        event.streams[0].getTracks().forEach((track) => {
          mediaStream.addTrack(track);
        });
      } else {
        mediaStream.addTrack(event.track);
      }
      if (videoRef.current) {
        void videoRef.current.play().catch(() => undefined);
      }
    };

    peerConnection.onicecandidate = (event) => {
      if (peerRef.current !== peerConnection || socketRef.current !== websocket) {
        return;
      }
      if (!event.candidate || websocket.readyState !== WebSocket.OPEN) {
        return;
      }
      websocket.send(
        JSON.stringify({
          type: "ice-candidate",
          candidate: {
            candidate: event.candidate.candidate,
            sdpMid: event.candidate.sdpMid,
            sdpMLineIndex: event.candidate.sdpMLineIndex,
          },
        }),
      );
    };

    peerConnection.onconnectionstatechange = () => {
      if (peerRef.current !== peerConnection || socketRef.current !== websocket) {
        return;
      }
      const nextState =
        peerConnection.connectionState === "connected"
          ? "Connected"
          : peerConnection.connectionState === "failed"
            ? "Connection failed"
            : peerConnection.connectionState === "connecting"
              ? "Connecting..."
              : peerConnection.connectionState;
      setViewerStatus(nextState);
    };

    websocket.onopen = () => {
      if (socketRef.current !== websocket || viewerAttemptRef.current !== attemptId) {
        return;
      }
      setViewerStatus("Waiting for worker...");
    };

    websocket.onmessage = async (event) => {
      if (socketRef.current !== websocket || peerRef.current !== peerConnection || viewerAttemptRef.current !== attemptId) {
        return;
      }
      const payload = JSON.parse(event.data) as {
        type: string;
        sdp?: string;
        candidate?: { candidate?: string; sdpMid?: string; sdpMLineIndex?: number };
        event?: string;
        detail?: string;
      };

      if (payload.type === "control" && payload.event === "peer-connected") {
        await startNegotiation(peerConnection, websocket);
        return;
      }
      if (payload.type === "control" && payload.event) {
        handleControlMessage(event.data);
        return;
      }
      if (payload.type === "answer" && payload.sdp) {
        await peerConnection.setRemoteDescription({ type: "answer", sdp: payload.sdp });
        return;
      }
      if (payload.type === "ice-candidate" && payload.candidate?.candidate) {
        await peerConnection.addIceCandidate(payload.candidate);
        return;
      }
      if (payload.type === "error") {
        setViewerStatus(payload.detail ?? "Viewer error");
      }
    };

    websocket.onclose = () => {
      if (socketRef.current !== websocket || viewerAttemptRef.current !== attemptId) {
        return;
      }
      setViewerStatus("Disconnected");
      negotiationStartedRef.current = false;
      dataChannelRef.current = null;
      if (!manualDisconnectRef.current && activeSessionRef.current?.session_id === sessionId) {
        reconnectTimerRef.current = window.setTimeout(() => {
          void connectViewer(sessionId, { reconnecting: true });
        }, 1500);
      }
    };
  }

  function handleControlMessage(rawMessage: string) {
    let payload: {
      type: string;
      event?: string;
      payload?: { text?: string };
      detail?: string;
    };
    try {
      payload = JSON.parse(rawMessage) as {
        type: string;
        event?: string;
        payload?: { text?: string };
        detail?: string;
      };
    } catch {
      return;
    }
    if (payload.type === "control" && payload.event === "clipboard-update" && payload.payload?.text) {
      if (navigator.clipboard) {
        void navigator.clipboard.writeText(payload.payload.text).catch(() => undefined);
      }
      setStatusMessage("Remote clipboard copied locally.");
      return;
    }
    if (payload.type === "error") {
      setViewerStatus(payload.detail ?? "Viewer error");
    }
  }

  async function requestRemoteClipboard() {
    sendControl("clipboard-read");
  }

  async function refreshDownloads(sessionId: string) {
    try {
      const response = await listSessionDownloads(sessionId);
      setDownloads(response.items);
    } catch {
      setDownloads([]);
    }
  }

  function queuePointerMove(x: number, y: number) {
    pointerMovePayloadRef.current = { x, y };
    if (pointerMoveFrameRef.current !== null) {
      return;
    }
    pointerMoveFrameRef.current = requestAnimationFrame(() => {
      pointerMoveFrameRef.current = null;
      if (!pointerMovePayloadRef.current) {
        return;
      }
      sendControl("pointer-move", pointerMovePayloadRef.current);
    });
  }

  async function handlePaste(text: string) {
    if (!text) {
      return;
    }
    if (sendControl("clipboard-paste", { text })) {
      setStatusMessage("Clipboard text sent to the remote browser.");
      return;
    }
    if (!activeSessionRef.current) {
      setStatusMessage("No active session is available for clipboard sync.");
      return;
    }
    try {
      const response = await syncSessionClipboard(activeSessionRef.current.session_id, text);
      setStatusMessage(
        response.delivered
          ? "Clipboard text delivered through the API fallback."
          : "Clipboard stored for the session while the worker reconnects.",
      );
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Clipboard sync failed.");
    }
  }

  async function launchSessionWith(
    sessionKind: SessionKind,
    runtimeName: BrowserName | DesktopProfileName,
    presetId: ViewportPresetId,
  ) {
    const preset = viewportPresets.find((item) => item.id === presetId) ?? viewportPresets[0];
    setSelectedSessionKind(sessionKind);
    if (sessionKind === "browser") {
      setSelectedBrowser(runtimeName as BrowserName);
    } else {
      setSelectedDesktopProfile(runtimeName as DesktopProfileName);
    }
    setSelectedPreset(preset.id);
    setSelectedResolution({ width: preset.width, height: preset.height });
    setBusy(true);
    const runtimeTitle =
      sessionKind === "browser"
        ? browserCatalog[runtimeName as BrowserName].label
        : desktopCatalog[runtimeName as DesktopProfileName].label;
    setStatusMessage(
      `Launching ${runtimeTitle} at ${preset.width}x${preset.height}...`,
    );
    try {
      const commonSessionFields = {
        resolution: { width: preset.width, height: preset.height },
        timeout_seconds: defaultSessionRequest.timeout_seconds,
        idle_timeout_seconds: defaultSessionRequest.idle_timeout_seconds,
        allow_file_upload: defaultSessionRequest.allow_file_upload,
      };
      const sessionPayload: SessionCreateRequest =
        sessionKind === "browser"
          ? {
              session_kind: "browser",
              browser: runtimeName as BrowserName,
              target_url: targetUrl,
              ...commonSessionFields,
            }
          : {
              session_kind: "desktop",
              desktop_profile: runtimeName as DesktopProfileName,
              ...commonSessionFields,
            };
      const session = await createSession(sessionPayload);
      activeSessionRef.current = session;
      await refreshSessions();
      await connectViewer(session.session_id);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Failed to create session.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLaunchSession() {
    await launchSessionWith(
      selectedSessionKind,
      selectedSessionKind === "browser" ? selectedBrowser : selectedDesktopProfile,
      selectedPreset,
    );
  }

  async function handleDelete(sessionId: string) {
    setBusy(true);
    setStatusMessage(`Terminating ${sessionId}...`);
    try {
      await deleteSession(sessionId);
      if (activeSessionId === sessionId) {
        closeViewer();
        setActiveSessionId(null);
      }
      await refreshSessions();
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Failed to delete session.");
    } finally {
      setBusy(false);
    }
  }

  async function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !activeSessionRef.current) {
      return;
    }

    setBusy(true);
    setStatusMessage(`Uploading ${file.name}...`);
    try {
      const response = await uploadSessionFile(activeSessionRef.current.session_id, file);
      await refreshDownloads(activeSessionRef.current.session_id);
      setStatusMessage(
        response.delivered
          ? `${response.filename} uploaded and announced to the worker.`
          : `${response.filename} uploaded to ${response.destination_path}.`,
      );
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "File upload failed.");
    } finally {
      event.target.value = "";
      setBusy(false);
    }
  }

  function handleViewerPointerMove(event: PointerEvent<HTMLDivElement>) {
    const video = videoRef.current;
    const resolution = activeSessionRef.current?.resolution;
    if (!video || !resolution) {
      return;
    }
    const projected = projectPointerToSession(event.nativeEvent, video, resolution);
    if (!projected) {
      return;
    }
    queuePointerMove(projected.x, projected.y);
  }

  function handleViewerPointerClick(event: PointerEvent<HTMLDivElement>) {
    const video = videoRef.current;
    const resolution = activeSessionRef.current?.resolution;
    if (!video || !resolution) {
      return;
    }
    const projected = projectPointerToSession(event.nativeEvent, video, resolution);
    if (!projected) {
      return;
    }
    viewerSurfaceRef.current?.focus();
    sendControl("pointer-click", {
      ...projected,
      button: event.button,
    });
  }

  function handleViewerWheel(event: WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    sendControl("wheel", { delta_x: event.deltaX, delta_y: event.deltaY });
  }

  function handleViewerKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    event.preventDefault();

    if (isClipboardShortcut(event.nativeEvent)) {
      if (event.key.toLowerCase() === "v") {
        if (navigator.clipboard) {
          void navigator.clipboard
            .readText()
            .then((text) => handlePaste(text))
            .catch(() => undefined);
        }
        return;
      }

      sendControl("key-press", toKeyPayload(event.nativeEvent));
      window.setTimeout(() => {
        void requestRemoteClipboard();
      }, 150);
      return;
    }

    if (shouldSendAsTextInput(event.nativeEvent)) {
      sendControl("text-input", { text: event.key });
      return;
    }

    sendControl("key-press", toKeyPayload(event.nativeEvent));
  }

  function handleViewerPaste(event: ClipboardEvent<HTMLDivElement>) {
    event.preventDefault();
    void handlePaste(event.clipboardData.getData("text/plain"));
  }

  useEffect(() => {
    if (!activeSessionId) {
      activeSessionRef.current = null;
      setDownloads([]);
      return;
    }
    activeSessionRef.current = sessions.find((session) => session.session_id === activeSessionId) ?? null;
    void refreshDownloads(activeSessionId);
  }, [activeSessionId, sessions]);

  function handleDownload(filename: string) {
    if (!activeSessionRef.current) {
      return;
    }
    const href = buildApiUrl(
      `/api/v1/sessions/${activeSessionRef.current.session_id}/downloads/${encodeURIComponent(filename)}`,
    );
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  }

  const activeSession =
    (activeSessionId ? sessions.find((session) => session.session_id === activeSessionId) : null) ??
    activeSessionRef.current;
  const selectedPresetMeta = viewportPresets.find((preset) => preset.id === selectedPreset) ?? viewportPresets[0];
  const selectedRuntimeLabel =
    selectedSessionKind === "browser"
      ? browserCatalog[selectedBrowser].label
      : desktopCatalog[selectedDesktopProfile].label;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Remote Browser Lab</p>
          <h1>Browserlab</h1>
        </div>
      </header>

      <section className="workspace-grid">
        <aside className="workspace-sidebar">
          <section className="launch-deck">
            <div className="launch-copy">
              <h2>Launch</h2>
              <p>Choose a browser or desktop runtime, set a viewport, and launch a session.</p>
            </div>
            <div className="launch-group">
              <div className="launch-group-header">
                <span>Mode</span>
                <strong>{selectedSessionKind === "browser" ? "Browser" : "Desktop"}</strong>
              </div>
              <div className="preset-grid" role="tablist" aria-label="Session modes">
                <button
                  type="button"
                  className={selectedSessionKind === "browser" ? "preset-chip is-selected" : "preset-chip"}
                  disabled={busy}
                  onClick={() => setSelectedSessionKind("browser")}
                >
                  <span>Browser</span>
                </button>
                <button
                  type="button"
                  className={selectedSessionKind === "desktop" ? "preset-chip is-selected" : "preset-chip"}
                  disabled={busy}
                  onClick={() => setSelectedSessionKind("desktop")}
                >
                  <span>Desktop</span>
                </button>
              </div>
            </div>
            <div className="launch-toolbar">
              {selectedSessionKind === "browser" ? (
                <label className="target-url-field target-url-field-wide">
                  <span>Target URL</span>
                  <input
                    type="url"
                    value={targetUrl}
                    disabled={busy}
                    placeholder="https://example.com"
                    onChange={(event) => setTargetUrl(event.target.value)}
                  />
                </label>
              ) : null}
              <button type="button" className="launch-button" disabled={busy} onClick={() => void handleLaunchSession()}>
                Launch Session
              </button>
            </div>
            <div className="launch-selection-row" aria-label="Current launch settings">
              <div className="launch-selection-pill">
                <span>Mode</span>
                <strong>{selectedSessionKind === "browser" ? "Browser" : "Desktop"}</strong>
              </div>
              <div className="launch-selection-pill">
                <span>Runtime</span>
                <strong>{selectedRuntimeLabel}</strong>
              </div>
              <div className="launch-selection-pill">
                <span>Viewport</span>
                <strong>{selectedPresetMeta.label}</strong>
                <small>{`${selectedResolution.width} x ${selectedResolution.height}`}</small>
              </div>
            </div>
            <div className="launch-controls">
              <div className="launch-group">
                <div className="launch-group-header">
                  <span>{selectedSessionKind === "browser" ? "Choose browser" : "Choose desktop"}</span>
                  <strong>{selectedRuntimeLabel}</strong>
                </div>
                <div className="browser-grid" role="list" aria-label="Runtime choices">
                  {(selectedSessionKind === "browser" ? supportedBrowsers : supportedDesktopProfiles).map((runtime) => {
                    const isBrowserRuntime = selectedSessionKind === "browser";
                    const meta = isBrowserRuntime
                      ? browserCatalog[runtime as BrowserName]
                      : desktopCatalog[runtime as DesktopProfileName];
                    const isSelected = isBrowserRuntime
                      ? runtime === selectedBrowser
                      : runtime === selectedDesktopProfile;
                    return (
                      <button
                        key={runtime}
                        type="button"
                        role="listitem"
                        className={`browser-card ${meta.accentClass}${isSelected ? " is-selected" : ""}`}
                        disabled={busy}
                        onClick={() => {
                          if (isBrowserRuntime) {
                            setSelectedBrowser(runtime as BrowserName);
                          } else {
                            setSelectedDesktopProfile(runtime as DesktopProfileName);
                          }
                        }}
                      >
                        <span className="browser-card-top">
                          <span className="browser-card-title">
                            <span className="browser-mark">
                              {isBrowserRuntime ? (
                                <BrowserMark browser={runtime as BrowserName} />
                              ) : (
                                <DesktopMark profile={runtime as DesktopProfileName} />
                              )}
                            </span>
                            <strong>{meta.label}</strong>
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="launch-group">
                <div className="launch-group-header">
                  <span>Viewport</span>
                  <strong>{selectedPresetMeta.label}</strong>
                </div>
                <div className="preset-grid" role="tablist" aria-label="Viewport presets">
                  {viewportPresets.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      className={preset.id === selectedPreset ? "preset-chip is-selected" : "preset-chip"}
                      disabled={busy}
                      onClick={() => setSelectedPreset(preset.id)}
                    >
                      <span>{preset.label}</span>
                      <small>{`${preset.width} x ${preset.height}`}</small>
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <p className="status-line">{statusMessage}</p>
          </section>

          <div className="sidebar-card">
            <div className="sidebar-header">
              <h2>Sessions</h2>
              <span className="meta-pill meta-pill-muted">{sessions.length}</span>
            </div>
            {sessions.length === 0 ? (
              <p className="empty-state">No live sessions yet.</p>
            ) : (
              <ul className="session-list">
                {sessions.map((session) => (
                  <li
                    key={session.session_id}
                    className={session.session_id === activeSessionId ? "session-item is-active" : "session-item"}
                  >
                    <div className="session-item-copy">
                      <strong>{runtimeLabel(session)}</strong>
                      <span>{session.status}</span>
                      <span className="session-url">
                        {session.session_kind === "browser" ? session.target_url : "Full desktop session"}
                      </span>
                    </div>
                    <div className="session-actions">
                      <button
                        type="button"
                        disabled={busy || session.status === "terminated" || session.status === "expired"}
                        onClick={() => void connectViewer(session.session_id)}
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        className="danger-button"
                        disabled={busy || session.status === "terminated" || session.status === "expired"}
                        onClick={() => void handleDelete(session.session_id)}
                      >
                        End
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        <section className="viewer-stage">
          <div className="browser-frame">
            <div
              ref={viewerSurfaceRef}
              className="viewer-surface"
              tabIndex={0}
              onPointerMove={handleViewerPointerMove}
              onPointerUp={handleViewerPointerClick}
              onWheel={handleViewerWheel}
              onKeyDown={handleViewerKeyDown}
              onPaste={handleViewerPaste}
            >
              <video ref={videoRef} autoPlay playsInline muted className="viewer-video" />
              {!activeSession && (
                <div className="viewer-overlay">
                  <p>Launch a session to start streaming the remote browser or desktop here.</p>
                </div>
              )}
            </div>
          </div>

          <div className="viewer-toolbar">
            <div className="sidebar-card">
              <div className="sidebar-header">
                <h2>Live Controls</h2>
              </div>
              <div className="action-grid">
                <button
                  type="button"
                  disabled={busy || !activeSession?.allow_file_upload}
                  onClick={() => fileInputRef.current?.click()}
                >
                  Upload File
                </button>
                <button
                  type="button"
                  disabled={busy || !activeSessionId}
                  onClick={() => {
                    if (!navigator.clipboard) {
                      setStatusMessage("Local clipboard access is unavailable in this browser.");
                      return;
                    }
                    void navigator.clipboard
                      .readText()
                      .then((text) => handlePaste(text))
                      .catch(() => setStatusMessage("Failed to read local clipboard text."));
                  }}
                >
                  Push Clipboard
                </button>
                <button
                  type="button"
                  disabled={busy || !activeSessionId}
                  onClick={() => {
                    if (!activeSession) {
                      return;
                    }
                    setBusy(true);
                    setStatusMessage("Capturing screenshot...");
                    void captureSessionScreenshot(activeSession.session_id)
                      .then(({ blob, filename }) => {
                        const url = window.URL.createObjectURL(blob);
                        const anchor = document.createElement("a");
                        anchor.href = url;
                        anchor.download = filename;
                        document.body.append(anchor);
                        anchor.click();
                        anchor.remove();
                        window.URL.revokeObjectURL(url);
                        setStatusMessage(`Screenshot saved as ${filename}.`);
                      })
                      .catch((error: Error) => {
                        setStatusMessage(error.message);
                      })
                      .finally(() => {
                        setBusy(false);
                      });
                  }}
                >
                  Screenshot
                </button>
                <button
                  type="button"
                  disabled={busy || !activeSessionId}
                  onClick={() => {
                    if (activeSession) {
                      void refreshDownloads(activeSession.session_id);
                    }
                  }}
                >
                  Refresh Files
                </button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                hidden
                onChange={(event) => void handleFileSelection(event)}
              />
            </div>

            <div className="sidebar-card">
              <div className="sidebar-header">
                <h2>Downloads</h2>
                <span className="meta-pill meta-pill-muted">{downloads.length}</span>
              </div>
              {downloads.length === 0 ? (
                <p className="empty-state">No downloadable files are available yet.</p>
              ) : (
                <ul className="downloads-list">
                  {downloads.map((download) => (
                    <li key={download.filename}>
                      <div>
                        <strong>{download.filename}</strong>
                        <span>{`${download.size_bytes} bytes`}</span>
                      </div>
                      <button type="button" onClick={() => handleDownload(download.filename)}>
                        Download
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

export default App;
