import {
  isClipboardShortcut,
  projectPointerToSession,
  shouldSendAsTextInput,
  toKeyPayload,
} from "./viewerProtocol";

describe("viewerProtocol", () => {
  it("projects pointer coordinates into the remote session", () => {
    const video = document.createElement("video");
    Object.defineProperty(video, "videoWidth", { value: 1600 });
    Object.defineProperty(video, "videoHeight", { value: 900 });
    video.getBoundingClientRect = () =>
      ({
        left: 0,
        top: 0,
        width: 800,
        height: 450,
        right: 800,
        bottom: 450,
      }) as DOMRect;

    expect(
      projectPointerToSession({ clientX: 400, clientY: 225 } as PointerEvent, video, {
        width: 1600,
        height: 900,
      }),
    ).toEqual({ x: 800, y: 450 });
  });

  it("classifies text and clipboard shortcuts", () => {
    expect(shouldSendAsTextInput({ key: "a", ctrlKey: false, altKey: false, metaKey: false })).toBe(true);
    expect(isClipboardShortcut({ key: "c", ctrlKey: true, metaKey: false, altKey: false })).toBe(true);
    expect(
      toKeyPayload({
        key: "Enter",
        code: "Enter",
        altKey: false,
        ctrlKey: false,
        metaKey: false,
        shiftKey: false,
      }),
    ).toEqual({
      key: "Enter",
      code: "Enter",
      altKey: false,
      ctrlKey: false,
      metaKey: false,
      shiftKey: false,
    });
  });
});
