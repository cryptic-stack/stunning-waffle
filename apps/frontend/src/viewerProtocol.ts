import type { SessionResolution } from "@foss-browserlab/shared-types";

export interface PointerPayload {
  x: number;
  y: number;
}

export interface KeyPayload {
  key: string;
  code: string;
  altKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
}

function getRenderedVideoRect(video: HTMLVideoElement): DOMRect {
  const bounds = video.getBoundingClientRect();
  const sourceWidth = video.videoWidth || bounds.width || 1;
  const sourceHeight = video.videoHeight || bounds.height || 1;
  const sourceRatio = sourceWidth / sourceHeight;
  const elementRatio = bounds.width / Math.max(bounds.height, 1);

  let renderedWidth = bounds.width;
  let renderedHeight = bounds.height;

  if (elementRatio > sourceRatio) {
    renderedHeight = bounds.height;
    renderedWidth = renderedHeight * sourceRatio;
  } else {
    renderedWidth = bounds.width;
    renderedHeight = renderedWidth / sourceRatio;
  }

  const left = bounds.left + (bounds.width - renderedWidth) / 2;
  const top = bounds.top + (bounds.height - renderedHeight) / 2;
  return new DOMRect(left, top, renderedWidth, renderedHeight);
}

export function projectPointerToSession(
  event: Pick<PointerEvent, "clientX" | "clientY">,
  video: HTMLVideoElement,
  resolution: SessionResolution,
): PointerPayload | null {
  const rect = getRenderedVideoRect(video);
  if (event.clientX < rect.left || event.clientX > rect.right) {
    return null;
  }
  if (event.clientY < rect.top || event.clientY > rect.bottom) {
    return null;
  }

  const relativeX = (event.clientX - rect.left) / Math.max(rect.width, 1);
  const relativeY = (event.clientY - rect.top) / Math.max(rect.height, 1);

  return {
    x: Math.max(0, Math.min(resolution.width - 1, Math.round(relativeX * resolution.width))),
    y: Math.max(0, Math.min(resolution.height - 1, Math.round(relativeY * resolution.height))),
  };
}

export function shouldSendAsTextInput(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "altKey" | "metaKey">) {
  return event.key.length === 1 && !event.ctrlKey && !event.altKey && !event.metaKey;
}

export function toKeyPayload(
  event: Pick<KeyboardEvent, "key" | "code" | "altKey" | "ctrlKey" | "metaKey" | "shiftKey">,
): KeyPayload {
  return {
    key: event.key,
    code: event.code,
    altKey: event.altKey,
    ctrlKey: event.ctrlKey,
    metaKey: event.metaKey,
    shiftKey: event.shiftKey,
  };
}

export function isClipboardShortcut(
  event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey">,
): boolean {
  if (event.altKey || (!event.ctrlKey && !event.metaKey)) {
    return false;
  }
  return ["c", "x", "v"].includes(event.key.toLowerCase());
}
