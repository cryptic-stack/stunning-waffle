import { fireEvent, render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubFetch(responses?: Array<unknown>) {
    let callCount = 0;
    const payloads = responses ?? [{ items: [] }, { ice_servers: [] }];
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        const index = Math.min(callCount, payloads.length - 1);
        callCount += 1;
        return {
          ok: true,
          json: async () => payloads[index],
        };
      }),
    );
  }

  it("renders the launcher page", async () => {
    stubFetch();

    render(<App />);

    expect(screen.getByRole("heading", { name: /browserlab/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /launch session/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /^browser$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^desktop$/i })).toBeInTheDocument();
    expect(screen.getByText("Brave")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /mobile 390 x 844/i })).toBeInTheDocument();
    expect(screen.getByText("Firefox")).toBeInTheDocument();
    expect(screen.getByDisplayValue("https://example.com")).toBeInTheDocument();
    expect(await screen.findByText(/no live sessions yet/i)).toBeInTheDocument();
  });

  it("hides the target url field in desktop mode", async () => {
    stubFetch();

    render(<App />);
    await screen.findByText(/no live sessions yet/i);

    expect(screen.getByLabelText(/target url/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^desktop$/i }));

    expect(screen.queryByLabelText(/target url/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Ubuntu XFCE").length).toBeGreaterThan(0);
  });

  it("renders desktop sessions with runtime labels", async () => {
    stubFetch([
      {
        items: [
          {
            session_id: "sess_desktop_1",
            session_kind: "desktop",
            status: "active",
            browser: null,
            desktop_profile: "ubuntu-xfce",
            container_id: "container-1",
            signaling_url: "/ws/signaling/sess_desktop_1",
            expires_at: "2026-04-09T22:15:00Z",
            terminated_at: null,
            resolution: { width: 1280, height: 720 },
            timeout_seconds: 1800,
            idle_timeout_seconds: 300,
            allow_file_upload: true,
            target_url: "https://example.com",
          },
        ],
      },
      { ice_servers: [] },
    ]);

    render(<App />);

    expect(await screen.findByText(/ubuntu xfce \| active/i)).toBeInTheDocument();
    expect(screen.getByText(/full desktop session/i)).toBeInTheDocument();
  });
});
