import type {
  AutomationSessionBootstrapResponse,
  ClipboardSyncResponse,
  DownloadListResponse,
  FileUploadResponse,
  HealthResponse,
  RtcConfigResponse,
  SessionBootstrapResponse,
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

function buildAuthHeaders(): HeadersInit {
  const viteEnv = (
    import.meta as ImportMeta & {
      env?: {
        VITE_AUTH_USER_ID?: string;
        VITE_AUTH_USER_EMAIL?: string;
        VITE_AUTH_USER_NAME?: string;
      };
    }
  ).env;
  const headers: Record<string, string> = {};
  if (viteEnv?.VITE_AUTH_USER_ID) {
    headers["X-User-Id"] = viteEnv.VITE_AUTH_USER_ID;
  }
  if (viteEnv?.VITE_AUTH_USER_EMAIL) {
    headers["X-User-Email"] = viteEnv.VITE_AUTH_USER_EMAIL;
  }
  if (viteEnv?.VITE_AUTH_USER_NAME) {
    headers["X-User-Name"] = viteEnv.VITE_AUTH_USER_NAME;
  }
  return headers;
}

function mergeHeaders(...sources: Array<HeadersInit | undefined>): Headers {
  const headers = new Headers();
  for (const source of sources) {
    if (!source) {
      continue;
    }
    new Headers(source).forEach((value, key) => headers.set(key, value));
  }
  return headers;
}

async function apiFetch(pathname: string, init?: RequestInit, baseUrl?: string): Promise<Response> {
  return fetch(buildApiUrl(pathname, baseUrl), {
    ...init,
    headers: mergeHeaders(buildAuthHeaders(), init?.headers),
  });
}

export async function fetchHealthz(baseUrl?: string): Promise<HealthResponse> {
  const response = await apiFetch("/healthz", undefined, baseUrl);

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  return (await response.json()) as HealthResponse;
}

export async function fetchRtcConfig(baseUrl?: string): Promise<RtcConfigResponse> {
  const response = await apiFetch("/api/v1/rtc/config", undefined, baseUrl);

  if (!response.ok) {
    throw new Error(`RTC config fetch failed with status ${response.status}`);
  }

  return (await response.json()) as RtcConfigResponse;
}

export async function listSessions(baseUrl?: string): Promise<SessionListResponse> {
  const response = await apiFetch("/api/v1/sessions", undefined, baseUrl);

  if (!response.ok) {
    throw new Error(`Listing sessions failed with status ${response.status}`);
  }

  return (await response.json()) as SessionListResponse;
}

export async function createSession(
  payload: SessionCreateRequest,
  baseUrl?: string,
): Promise<SessionResponse> {
  const response = await apiFetch(
    "/api/v1/sessions",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    baseUrl,
  );

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
  const response = await apiFetch(
    "/api/v1/automation/sessions",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
    baseUrl,
  );

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
  const response = await apiFetch(
    `/api/v1/automation/sessions/${sessionId}`,
    {
      headers: { Authorization: `Bearer ${apiKey}` },
    },
    baseUrl,
  );

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
  const response = await apiFetch(
    `/api/v1/automation/sessions/${sessionId}/bootstrap`,
    {
      headers: { Authorization: `Bearer ${apiKey}` },
    },
    baseUrl,
  );

  if (!response.ok) {
    throw new Error(`Automation bootstrap fetch failed with status ${response.status}`);
  }

  return (await response.json()) as AutomationSessionBootstrapResponse;
}

export async function getSessionBootstrap(
  sessionId: string,
  baseUrl?: string,
): Promise<SessionBootstrapResponse> {
  const response = await apiFetch(`/api/v1/sessions/${sessionId}/bootstrap`, undefined, baseUrl);

  if (!response.ok) {
    throw new Error(`Session bootstrap failed with status ${response.status}`);
  }

  return (await response.json()) as SessionBootstrapResponse;
}

export async function deleteSession(
  sessionId: string,
  baseUrl?: string,
): Promise<SessionResponse> {
  const response = await apiFetch(
    `/api/v1/sessions/${sessionId}`,
    {
      method: "DELETE",
    },
    baseUrl,
  );

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
  const response = await apiFetch(
    `/api/v1/sessions/${sessionId}/clipboard`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    },
    baseUrl,
  );

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

  const response = await apiFetch(
    `/api/v1/sessions/${sessionId}/file-upload`,
    {
      method: "POST",
      body: formData,
    },
    baseUrl,
  );

  if (!response.ok) {
    throw new Error(`File upload failed with status ${response.status}`);
  }

  return (await response.json()) as FileUploadResponse;
}

export async function listSessionDownloads(
  sessionId: string,
  baseUrl?: string,
): Promise<DownloadListResponse> {
  const response = await apiFetch(`/api/v1/sessions/${sessionId}/downloads`, undefined, baseUrl);

  if (!response.ok) {
    throw new Error(`Download listing failed with status ${response.status}`);
  }

  return (await response.json()) as DownloadListResponse;
}

export async function captureSessionScreenshot(
  sessionId: string,
  baseUrl?: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await apiFetch(`/api/v1/sessions/${sessionId}/screenshot`, undefined, baseUrl);

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

export async function downloadSessionFile(
  sessionId: string,
  filename: string,
  baseUrl?: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await apiFetch(
    `/api/v1/sessions/${sessionId}/downloads/${encodeURIComponent(filename)}`,
    undefined,
    baseUrl,
  );

  if (!response.ok) {
    throw new Error(`Download failed with status ${response.status}`);
  }

  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/i);
  return {
    blob: await response.blob(),
    filename: match?.[1] ?? filename,
  };
}
