import type {
  AutomationSessionBootstrapResponse,
  ClipboardSyncResponse,
  DownloadListResponse,
  FileUploadResponse,
  HealthResponse,
  RtcConfigResponse,
  SessionCreateRequest,
  SessionListResponse,
  SessionResponse,
} from "@foss-browserlab/shared-types";

export function buildApiUrl(pathname: string, baseUrl?: string): string {
  const viteEnv = (import.meta as ImportMeta & { env?: { VITE_API_BASE_URL?: string } }).env;
  const resolvedBase =
    baseUrl ??
    (typeof window === "undefined"
      ? "http://localhost:8000"
      : viteEnv?.VITE_API_BASE_URL ?? "");
  return new URL(pathname, resolvedBase || window.location.origin).toString();
}

export function buildWebSocketUrl(pathname: string, baseUrl?: string): string {
  const httpUrl = new URL(buildApiUrl(pathname, baseUrl));
  httpUrl.protocol = httpUrl.protocol === "https:" ? "wss:" : "ws:";
  return httpUrl.toString();
}

export async function fetchHealthz(baseUrl?: string): Promise<HealthResponse> {
  const response = await fetch(buildApiUrl("/healthz", baseUrl));

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  return (await response.json()) as HealthResponse;
}

export async function fetchRtcConfig(baseUrl?: string): Promise<RtcConfigResponse> {
  const response = await fetch(buildApiUrl("/api/v1/rtc/config", baseUrl));

  if (!response.ok) {
    throw new Error(`RTC config fetch failed with status ${response.status}`);
  }

  return (await response.json()) as RtcConfigResponse;
}

export async function listSessions(baseUrl?: string): Promise<SessionListResponse> {
  const response = await fetch(buildApiUrl("/api/v1/sessions", baseUrl));

  if (!response.ok) {
    throw new Error(`Listing sessions failed with status ${response.status}`);
  }

  return (await response.json()) as SessionListResponse;
}

export async function createSession(
  payload: SessionCreateRequest,
  baseUrl?: string,
): Promise<SessionResponse> {
  const response = await fetch(buildApiUrl("/api/v1/sessions", baseUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Create session failed with status ${response.status}`);
  }

  return (await response.json()) as SessionResponse;
}

export async function createAutomationSession(
  payload: SessionCreateRequest,
  apiKey: string,
  baseUrl?: string,
): Promise<AutomationSessionBootstrapResponse> {
  const response = await fetch(buildApiUrl("/api/v1/automation/sessions", baseUrl), {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Create automation session failed with status ${response.status}`);
  }

  return (await response.json()) as AutomationSessionBootstrapResponse;
}

export async function getAutomationSession(
  sessionId: string,
  apiKey: string,
  baseUrl?: string,
): Promise<SessionResponse> {
  const response = await fetch(buildApiUrl(`/api/v1/automation/sessions/${sessionId}`, baseUrl), {
    headers: { Authorization: `Bearer ${apiKey}` },
  });

  if (!response.ok) {
    throw new Error(`Automation session fetch failed with status ${response.status}`);
  }

  return (await response.json()) as SessionResponse;
}

export async function getAutomationBootstrap(
  sessionId: string,
  apiKey: string,
  baseUrl?: string,
): Promise<AutomationSessionBootstrapResponse> {
  const response = await fetch(
    buildApiUrl(`/api/v1/automation/sessions/${sessionId}/bootstrap`, baseUrl),
    {
      headers: { Authorization: `Bearer ${apiKey}` },
    },
  );

  if (!response.ok) {
    throw new Error(`Automation bootstrap fetch failed with status ${response.status}`);
  }

  return (await response.json()) as AutomationSessionBootstrapResponse;
}

export async function deleteSession(
  sessionId: string,
  baseUrl?: string,
): Promise<SessionResponse> {
  const response = await fetch(buildApiUrl(`/api/v1/sessions/${sessionId}`, baseUrl), {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Delete session failed with status ${response.status}`);
  }

  return (await response.json()) as SessionResponse;
}

export async function syncSessionClipboard(
  sessionId: string,
  text: string,
  baseUrl?: string,
): Promise<ClipboardSyncResponse> {
  const response = await fetch(buildApiUrl(`/api/v1/sessions/${sessionId}/clipboard`, baseUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error(`Clipboard sync failed with status ${response.status}`);
  }

  return (await response.json()) as ClipboardSyncResponse;
}

export async function uploadSessionFile(
  sessionId: string,
  file: File,
  baseUrl?: string,
): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("upload", file);

  const response = await fetch(buildApiUrl(`/api/v1/sessions/${sessionId}/file-upload`, baseUrl), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`File upload failed with status ${response.status}`);
  }

  return (await response.json()) as FileUploadResponse;
}

export async function listSessionDownloads(
  sessionId: string,
  baseUrl?: string,
): Promise<DownloadListResponse> {
  const response = await fetch(buildApiUrl(`/api/v1/sessions/${sessionId}/downloads`, baseUrl));

  if (!response.ok) {
    throw new Error(`Download listing failed with status ${response.status}`);
  }

  return (await response.json()) as DownloadListResponse;
}

export async function captureSessionScreenshot(
  sessionId: string,
  baseUrl?: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(buildApiUrl(`/api/v1/sessions/${sessionId}/screenshot`, baseUrl));

  if (!response.ok) {
    throw new Error(`Screenshot capture failed with status ${response.status}`);
  }

  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/i);
  return {
    blob: await response.blob(),
    filename: match?.[1] ?? `${sessionId}-screenshot.png`,
  };
}
