export const supportedBrowsers = ["chromium", "firefox", "brave", "edge", "vivaldi"] as const;
export const supportedDesktopProfiles = ["ubuntu-xfce", "kali-xfce"] as const;
export const supportedSessionKinds = ["browser", "desktop"] as const;

export type BrowserName = (typeof supportedBrowsers)[number];
export type DesktopProfileName = (typeof supportedDesktopProfiles)[number];
export type SessionKind = (typeof supportedSessionKinds)[number];
export type SessionStatus = "starting" | "active" | "expired" | "terminated";

export interface SessionResolution {
  width: number;
  height: number;
}

export interface BrowserSessionCreateRequest {
  session_kind?: "browser";
  browser: BrowserName;
  desktop_profile?: never;
  resolution: SessionResolution;
  timeout_seconds: number;
  idle_timeout_seconds: number;
  allow_file_upload: boolean;
  target_url?: string;
}

export interface DesktopSessionCreateRequest {
  session_kind: "desktop";
  browser?: never;
  desktop_profile: DesktopProfileName;
  resolution: SessionResolution;
  timeout_seconds: number;
  idle_timeout_seconds: number;
  allow_file_upload: boolean;
  target_url?: string;
}

export type SessionCreateRequest = BrowserSessionCreateRequest | DesktopSessionCreateRequest;

export interface SessionResponse {
  session_id: string;
  session_kind: SessionKind;
  status: SessionStatus;
  browser: BrowserName | null;
  desktop_profile: DesktopProfileName | null;
  container_id: string | null;
  signaling_url: string;
  expires_at: string;
  terminated_at: string | null;
  resolution: SessionResolution;
  timeout_seconds: number;
  idle_timeout_seconds: number;
  allow_file_upload: boolean;
  target_url: string;
}

export interface AutomationSessionBootstrapResponse {
  session: SessionResponse;
  viewer_token: string;
  session_api_url: string;
  signaling_websocket_url: string;
  rtc_config: RtcConfigResponse;
}

export interface SessionListResponse {
  items: SessionResponse[];
}

export interface HealthResponse {
  status: "ok";
  service: string;
}

export interface IceServerConfig {
  urls: string[];
  username?: string | null;
  credential?: string | null;
}

export interface RtcConfigResponse {
  ice_servers: IceServerConfig[];
}

export interface ClipboardSyncResponse {
  session_id: string;
  delivered: boolean;
  text_length: number;
}

export interface FileUploadResponse {
  session_id: string;
  filename: string;
  destination_path: string;
  size_bytes: number;
  delivered: boolean;
}

export interface DownloadItem {
  filename: string;
  destination_path: string;
  size_bytes: number;
}

export interface DownloadListResponse {
  session_id: string;
  items: DownloadItem[];
}

export const defaultSessionRequest: SessionCreateRequest = {
  session_kind: "browser",
  browser: "chromium",
  resolution: {
    width: 1600,
    height: 900,
  },
  timeout_seconds: 1800,
  idle_timeout_seconds: 300,
  allow_file_upload: true,
  target_url: "https://example.com",
};
