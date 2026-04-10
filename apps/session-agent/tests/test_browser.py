from __future__ import annotations

from pathlib import Path

from session_agent.browser import FIREFOX_USER_PREFS, start_browser_runtime
from session_agent.config import AgentConfig


class DummyProcess:
    def poll(self) -> None:
        return None


def make_config(browser: str, homepage_url: str = "https://example.com/") -> AgentConfig:
    return AgentConfig(
        session_id="sess_test",
        worker_token="worker-token",
        api_base_url="http://api:8000",
        session_kind="browser",
        browser=browser,
        desktop_profile=None,
        resolution_width=1280,
        resolution_height=720,
        homepage_url=homepage_url,
        display=":99",
        heartbeat_interval_seconds=5,
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
        turn_tls_enabled=False,
    )


def test_chromium_family_launch_disables_first_run_surfaces(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_popen(command: list[str], **_kwargs) -> DummyProcess:
        commands.append(command)
        return DummyProcess()

    monkeypatch.setattr("session_agent.browser.subprocess.Popen", fake_popen)
    monkeypatch.setattr("session_agent.browser.time.sleep", lambda _seconds: None)
    monkeypatch.setenv("HOME", str(tmp_path))

    runtime = start_browser_runtime(make_config("chromium"))

    assert runtime.processes
    chromium_command = commands[1]
    assert "--no-first-run" in chromium_command
    assert "--no-default-browser-check" in chromium_command
    assert "--disable-search-engine-choice-screen" in chromium_command
    assert "--no-service-autorun" in chromium_command
    assert "--password-store=basic" in chromium_command
    assert "--window-position=0,0" in chromium_command
    assert "--start-maximized" not in chromium_command
    assert "--window-size=1280,720" in chromium_command
    assert any(item.startswith("--user-data-dir=") for item in chromium_command)
    assert chromium_command[-1] == "https://example.com/"


def test_desktop_runtime_starts_xfce_session(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_popen(command: list[str], **_kwargs) -> DummyProcess:
        commands.append(command)
        return DummyProcess()

    monkeypatch.setattr("session_agent.browser.subprocess.Popen", fake_popen)
    monkeypatch.setattr("session_agent.browser.time.sleep", lambda _seconds: None)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    seed_dir = tmp_path / "seed"
    (seed_dir / ".config" / "xfce4").mkdir(parents=True, exist_ok=True)
    (seed_dir / ".config" / "xfce4" / "xfconf.xml").write_text("kasm-seed", encoding="utf-8")
    (seed_dir / ".pki" / "nssdb").mkdir(parents=True, exist_ok=True)
    (seed_dir / ".pki" / "nssdb" / "cert9.db").write_text("skip-me", encoding="utf-8")
    monkeypatch.setenv("SESSION_PROFILE_SEED_DIR", str(seed_dir))
    monkeypatch.setenv("SESSION_PROFILE_SEED_ALLOWLIST", ".config,Desktop")

    runtime = start_browser_runtime(
        AgentConfig(
            session_id="sess_desktop",
            worker_token="worker-token",
            api_base_url="http://api:8000",
            session_kind="desktop",
            browser=None,
            desktop_profile="ubuntu-xfce",
            resolution_width=1280,
            resolution_height=720,
            homepage_url="https://ignored.example/",
            display=":99",
            heartbeat_interval_seconds=5,
            turn_internal_host="coturn",
            turn_username="browserlab",
            turn_password="change-me",
            turn_tls_enabled=False,
        )
    )

    assert runtime.processes
    assert commands[1] == ["dbus-launch", "--exit-with-session", "startxfce4"]
    assert (tmp_path / "Desktop").exists()
    assert (tmp_path / "Downloads").exists()
    assert (tmp_path / "run" / ".ICEauthority").exists()
    assert (tmp_path / ".config" / "xfce4" / "xfconf.xml").read_text(encoding="utf-8") == "kasm-seed"
    assert not (tmp_path / ".pki").exists()


def test_firefox_profile_writes_first_run_suppression_prefs(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_popen(command: list[str], **_kwargs) -> DummyProcess:
        commands.append(command)
        return DummyProcess()

    monkeypatch.setattr("session_agent.browser.subprocess.Popen", fake_popen)
    monkeypatch.setattr("session_agent.browser.time.sleep", lambda _seconds: None)
    monkeypatch.setenv("HOME", str(tmp_path))

    runtime = start_browser_runtime(make_config("firefox", homepage_url="https://mozilla.org/"))

    assert runtime.processes
    firefox_command = commands[1]
    assert "--profile" in firefox_command
    assert firefox_command[-1] == "https://mozilla.org/"

    prefs_path = tmp_path / ".config" / "firefox-profile" / "user.js"
    prefs_text = prefs_path.read_text(encoding="utf-8")

    assert 'user_pref("browser.aboutwelcome.enabled", false);' in prefs_text
    assert 'user_pref("browser.shell.checkDefaultBrowser", false);' in prefs_text
    assert 'user_pref("startup.homepage_welcome_url", "");' in prefs_text
    for pref_name in FIREFOX_USER_PREFS:
        assert f'user_pref("{pref_name}",' in prefs_text
