from __future__ import annotations

import os
import signal
import shutil
import subprocess
import time
from dataclasses import dataclass

from session_agent.config import AgentConfig


CHROMIUM_BROWSER_COMMANDS: dict[str, tuple[str, str]] = {
    "chromium": ("chromium", "chromium-profile"),
    "brave": ("brave-browser", "brave-profile"),
    "edge": ("microsoft-edge-stable", "edge-profile"),
    "vivaldi": ("vivaldi-stable", "vivaldi-profile"),
}

FIREFOX_USER_PREFS = {
    "app.normandy.first_run": False,
    "browser.aboutwelcome.enabled": False,
    "browser.bookmarks.restore_default_bookmarks": False,
    "browser.messaging-system.whatsNewPanel.enabled": False,
    "browser.newtabpage.activity-stream.asrouter.userprefs.cfr.addons": False,
    "browser.newtabpage.activity-stream.asrouter.userprefs.cfr.features": False,
    "browser.newtabpage.activity-stream.feeds.section.topstories": False,
    "browser.newtabpage.activity-stream.showSponsored": False,
    "browser.newtabpage.activity-stream.showSponsoredTopSites": False,
    "browser.proton.onboarding.enabled": False,
    "browser.shell.checkDefaultBrowser": False,
    "browser.startup.firstrunSkipsHomepage": False,
    "browser.startup.homepage_override.mstone": "ignore",
    "browser.tabs.firefox-view": False,
    "datareporting.healthreport.uploadEnabled": False,
    "datareporting.policy.firstRunURL": "",
    "datareporting.policy.dataSubmissionEnabled": False,
    "default-browser-agent.enabled": False,
    "startup.homepage_welcome_url": "",
    "startup.homepage_welcome_url.additional": "",
}


@dataclass(slots=True)
class SessionRuntime:
    xvfb: subprocess.Popen | None
    processes: list[subprocess.Popen]

    def stop(self) -> None:
        for process in [*reversed(self.processes), self.xvfb]:
            if process is None or process.poll() is not None:
                continue
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


BrowserRuntime = SessionRuntime


def start_browser_runtime(config: AgentConfig) -> SessionRuntime:
    env = os.environ.copy()
    env["DISPLAY"] = config.display
    env["HOME"] = os.environ.get("HOME", "/home/browserlab")
    env["XDG_RUNTIME_DIR"] = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
    env["ICEAUTHORITY"] = os.environ.get("ICEAUTHORITY", f"{env['XDG_RUNTIME_DIR']}/.ICEauthority")
    os.makedirs(env["XDG_RUNTIME_DIR"], exist_ok=True)
    _seed_runtime_profile(env)
    firefox_profile_dir = os.path.join(env["HOME"], ".config", "firefox-profile")
    firefox_cache_dir = os.path.join(env["HOME"], ".cache", "mozilla")
    firefox_legacy_dir = os.path.join(env["HOME"], ".mozilla", "firefox")

    xvfb = subprocess.Popen(
        [
            "Xvfb",
            config.display,
            "-screen",
            "0",
            f"{config.resolution_width}x{config.resolution_height}x24",
            "-ac",
            "+extension",
            "RANDR",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)

    processes: list[subprocess.Popen] = []
    if config.session_kind == "desktop":
        processes.append(_start_desktop_session(config, env))
        return SessionRuntime(xvfb=xvfb, processes=processes)

    browser_name = config.browser or "chromium"
    if browser_name in CHROMIUM_BROWSER_COMMANDS:
        executable, profile_name = CHROMIUM_BROWSER_COMMANDS[browser_name]
        profile_dir = f"/home/browserlab/.config/{profile_name}"
        os.makedirs(profile_dir, exist_ok=True)
        processes.append(
            subprocess.Popen(
                [
                    executable,
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-renderer-backgrounding",
                    "--disable-features=Translate,BackForwardCache,MediaRouter,OptimizationHints,AutofillServerCommunication,PasswordManagerOnboarding",
                    "--disable-search-engine-choice-screen",
                    "--homepage=about:blank",
                    "--no-service-autorun",
                    "--password-store=basic",
                    "--window-position=0,0",
                    f"--user-data-dir={profile_dir}",
                    f"--window-size={config.resolution_width},{config.resolution_height}",
                    config.homepage_url,
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        return SessionRuntime(xvfb=xvfb, processes=processes)

    if browser_name == "firefox":
        os.makedirs(firefox_profile_dir, exist_ok=True)
        os.makedirs(firefox_cache_dir, exist_ok=True)
        os.makedirs(firefox_legacy_dir, exist_ok=True)
        _write_firefox_prefs(firefox_profile_dir)
        processes.append(
            subprocess.Popen(
                [
                    "firefox-esr",
                    "--display",
                    config.display,
                    "--new-instance",
                    "--width",
                    str(config.resolution_width),
                    "--height",
                    str(config.resolution_height),
                    "--profile",
                    firefox_profile_dir,
                    config.homepage_url,
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        return SessionRuntime(xvfb=xvfb, processes=processes)

    return SessionRuntime(xvfb=xvfb, processes=processes)


def _start_desktop_session(config: AgentConfig, env: dict[str, str]) -> subprocess.Popen:
    desktop_dir = os.path.join(env["HOME"], "Desktop")
    downloads_dir = os.path.join(env["HOME"], "Downloads")
    os.makedirs(desktop_dir, exist_ok=True)
    os.makedirs(downloads_dir, exist_ok=True)
    with open(env["ICEAUTHORITY"], "a", encoding="utf-8"):
        pass
    return subprocess.Popen(
        [
            "dbus-launch",
            "--exit-with-session",
            "startxfce4",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _write_firefox_prefs(profile_dir: str) -> None:
    prefs_path = os.path.join(profile_dir, "user.js")
    with open(prefs_path, "w", encoding="utf-8") as prefs_file:
        for key, value in FIREFOX_USER_PREFS.items():
            prefs_file.write(f'user_pref("{key}", {_to_firefox_pref(value)});\n')


def _to_firefox_pref(value: bool | str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return f'"{value}"'


def _seed_runtime_profile(env: dict[str, str]) -> None:
    seed_dir = os.environ.get("SESSION_PROFILE_SEED_DIR")
    allowlist = {
        part.strip()
        for part in os.environ.get("SESSION_PROFILE_SEED_ALLOWLIST", "").split(",")
        if part.strip()
    }
    home_dir = env["HOME"]
    if not seed_dir or not os.path.isdir(seed_dir):
        return
    for root, dirnames, filenames in os.walk(seed_dir):
        relative_root = os.path.relpath(root, seed_dir)
        if allowlist and relative_root != ".":
            top_level = relative_root.split(os.sep, 1)[0]
            if top_level not in allowlist:
                dirnames[:] = []
                continue
        target_root = home_dir if relative_root == "." else os.path.join(home_dir, relative_root)
        if relative_root != "." or not allowlist:
            os.makedirs(target_root, exist_ok=True)
        for dirname in dirnames:
            if relative_root == "." and allowlist and dirname not in allowlist:
                continue
            os.makedirs(os.path.join(target_root, dirname), exist_ok=True)
        for filename in filenames:
            if relative_root == "." and allowlist:
                continue
            source_path = os.path.join(root, filename)
            target_path = os.path.join(target_root, filename)
            shutil.copy2(source_path, target_path)
