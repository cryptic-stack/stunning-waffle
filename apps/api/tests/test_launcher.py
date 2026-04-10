from __future__ import annotations

import app.launcher as launcher_module
from app.launcher import DockerSessionLauncher, WorkerDefinition


class DummySocket:
    def __init__(self) -> None:
        self.payload = b""
        self.closed = False

    def write(self, payload: bytes) -> None:
        self.payload += payload

    def close(self) -> None:
        self.closed = True


class DummyApi:
    def __init__(self) -> None:
        self.exec_create_calls: list[dict] = []
        self.exec_start_calls: list[dict] = []
        self.exec_inspect_calls: list[str] = []
        self.socket = DummySocket()

    def exec_create(self, container_id: str, cmd: list[str], stdin: bool) -> dict[str, str]:
        self.exec_create_calls.append(
            {
                "container_id": container_id,
                "cmd": cmd,
                "stdin": stdin,
            }
        )
        return {"Id": "exec-1"}

    def exec_start(self, exec_id: str, detach: bool, tty: bool, socket: bool) -> DummySocket:
        self.exec_start_calls.append(
            {
                "exec_id": exec_id,
                "detach": detach,
                "tty": tty,
                "socket": socket,
            }
        )
        return self.socket

    def exec_inspect(self, exec_id: str) -> dict[str, int]:
        self.exec_inspect_calls.append(exec_id)
        return {"ExitCode": 0}


class DummyContainer:
    id = "container-1"
    labels = {"browserlab.runtime": "chromium", "browserlab.browser": "chromium"}

    def __init__(self) -> None:
        self.exec_run_calls: list[list[str]] = []

    def exec_run(self, command: list[str]):
        self.exec_run_calls.append(command)
        shell_command = command[-1]
        if command[0] == "browserlab-session-screenshot":
            return 0, b"\x89PNG\r\n\x1a\nstub"
        if "wc -c" in shell_command:
            return 0, b"notes.txt\t11\nreport.pdf\t4\n"
        if "cat /home/browserlab/Downloads/notes.txt" in shell_command:
            return 0, b"hello world"
        if "missing.txt" in shell_command:
            return 4, b""
        return 0, b""


class DummyContainers:
    def __init__(self) -> None:
        self.run_calls: list[dict] = []
        self.container = DummyContainer()

    def get(self, _container_id: str) -> DummyContainer:
        return self.container

    def run(self, image: str, **kwargs) -> DummyContainer:
        self.run_calls.append({"image": image, **kwargs})
        return DummyContainer()


class DummyDockerClient:
    def __init__(self) -> None:
        self.api = DummyApi()
        self.containers = DummyContainers()


def test_upload_file_streams_content_into_exec(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "chromium": WorkerDefinition(
                image="worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network=None,
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
    )

    result = launcher.upload_file("container-1", "notes.txt", b"hello world")

    assert result.destination_path == "/home/browserlab/Downloads/notes.txt"
    assert result.size_bytes == 11
    assert client.api.socket.payload == b"hello world"
    assert client.api.socket.closed is True
    assert client.api.exec_create_calls == [
        {
            "container_id": "container-1",
            "cmd": [
                "sh",
                "-lc",
                "mkdir -p /home/browserlab/Downloads && cat > /home/browserlab/Downloads/notes.txt",
            ],
            "stdin": True,
        }
    ]
    assert client.api.exec_start_calls == [
        {
            "exec_id": "exec-1",
            "detach": False,
            "tty": False,
            "socket": True,
        }
    ]
    assert client.api.exec_inspect_calls == ["exec-1"]


def test_launch_adds_host_gateway_alias(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "chromium": WorkerDefinition(
                image="worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network="browserlab",
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
        host_gateway_alias="host.docker.internal",
    )

    launcher._ensure_image = lambda _definition: None
    result = launcher.launch(
        session_id="sess_test",
        user_id="user-1",
        session_kind="browser",
        runtime_name="chromium",
        worker_token="token-1",
        resolution_width=1280,
        resolution_height=720,
        target_url="http://host.docker.internal:3000/",
    )

    assert result.container_id == "container-1"
    assert client.containers.run_calls[0]["extra_hosts"] == {"host.docker.internal": "host-gateway"}
    assert client.containers.run_calls[0]["environment"]["SESSION_HOMEPAGE_URL"] == (
        "http://host.docker.internal:3000/"
    )
    assert client.containers.run_calls[0]["environment"]["SESSION_KIND"] == "browser"
    assert client.containers.run_calls[0]["environment"]["SESSION_RUNTIME"] == "chromium"
    assert (
        client.containers.run_calls[0]["environment"]["ICEAUTHORITY"]
        == "/run/user/1000/.ICEauthority"
    )
    assert client.containers.run_calls[0]["environment"]["TURN_INTERNAL_HOST"] == "coturn"
    assert client.containers.run_calls[0]["security_opt"] == ["seccomp=unconfined"]
    assert "uid=1000,gid=1000" in client.containers.run_calls[0]["tmpfs"]["/run/user/1000"]


def test_non_chromium_workers_keep_no_new_privileges(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "firefox": WorkerDefinition(
                image="worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network="browserlab",
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
    )

    launcher._ensure_image = lambda _definition: None
    launcher.launch(
        session_id="sess_test",
        user_id="user-1",
        session_kind="browser",
        runtime_name="firefox",
        worker_token="token-1",
        resolution_width=1280,
        resolution_height=720,
        target_url="https://example.com/",
    )

    assert client.containers.run_calls[0]["security_opt"] == ["no-new-privileges:true"]
    assert "/home/browserlab/.mozilla" in client.containers.run_calls[0]["tmpfs"]


def test_chromium_family_workers_keep_relaxed_seccomp(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "brave": WorkerDefinition(
                image="worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network="browserlab",
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
    )

    launcher._ensure_image = lambda _definition: None
    launcher.launch(
        session_id="sess_test",
        user_id="user-1",
        session_kind="browser",
        runtime_name="brave",
        worker_token="token-1",
        resolution_width=1280,
        resolution_height=720,
        target_url="https://example.com/",
    )

    assert client.containers.run_calls[0]["security_opt"] == ["seccomp=unconfined"]


def test_desktop_workers_keep_no_new_privileges_and_desktop_state(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "ubuntu-xfce": WorkerDefinition(
                image="desktop-worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network="browserlab",
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
    )

    launcher._ensure_image = lambda _definition: None
    launcher.launch(
        session_id="sess_test",
        user_id="user-1",
        session_kind="desktop",
        runtime_name="ubuntu-xfce",
        worker_token="token-1",
        resolution_width=1280,
        resolution_height=720,
        target_url="https://ignored.example/",
    )

    assert client.containers.run_calls[0]["security_opt"] == ["no-new-privileges:true"]
    assert client.containers.run_calls[0]["environment"]["SESSION_KIND"] == "desktop"
    assert client.containers.run_calls[0]["environment"]["SESSION_RUNTIME"] == "ubuntu-xfce"
    assert client.containers.run_calls[0]["environment"]["SESSION_DESKTOP_PROFILE"] == "ubuntu-xfce"
    assert (
        client.containers.run_calls[0]["environment"]["ICEAUTHORITY"]
        == "/run/user/1000/.ICEauthority"
    )
    assert "/home/browserlab/.local/share" in client.containers.run_calls[0]["tmpfs"]
    assert (
        "uid=1000,gid=1000"
        in client.containers.run_calls[0]["tmpfs"]["/home/browserlab/Desktop"]
    )


def test_kali_desktop_workers_use_browserlab_home_contract(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "kali-xfce": WorkerDefinition(
                image="desktop-worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network="browserlab",
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
    )

    launcher._ensure_image = lambda _definition: None
    launcher.launch(
        session_id="sess_test",
        user_id="user-1",
        session_kind="desktop",
        runtime_name="kali-xfce",
        worker_token="token-1",
        resolution_width=1365,
        resolution_height=768,
        target_url="https://ignored.example/",
    )

    run_call = client.containers.run_calls[0]
    assert run_call["user"] == "browserlab"
    assert run_call["security_opt"] == []
    assert run_call["cap_add"] == ["SETUID", "SETGID", "AUDIT_WRITE"]
    assert run_call["labels"]["browserlab.home_dir"] == "/home/browserlab"
    assert run_call["environment"]["HOME"] == "/home/browserlab"
    assert run_call["environment"]["SESSION_PROFILE_SEED_DIR"] == ""
    assert run_call["environment"]["SESSION_PROFILE_SEED_ALLOWLIST"] == ""
    assert "/home/browserlab/.config" in run_call["tmpfs"]
    assert "/home/browserlab/Desktop" in run_call["tmpfs"]
    assert "/home/browserlab/.mozilla" in run_call["tmpfs"]
    assert "uid=1000,gid=1000" in run_call["tmpfs"]["/home/browserlab/.config"]


def test_ubuntu_desktop_workers_keep_no_new_privileges(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "ubuntu-xfce": WorkerDefinition(
                image="desktop-worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network="browserlab",
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
    )

    launcher._ensure_image = lambda _definition: None
    launcher.launch(
        session_id="sess_test",
        user_id="user-1",
        session_kind="desktop",
        runtime_name="ubuntu-xfce",
        worker_token="token-1",
        resolution_width=1280,
        resolution_height=720,
        target_url="https://ignored.example/",
    )

    assert client.containers.run_calls[0]["security_opt"] == ["no-new-privileges:true"]
    assert client.containers.run_calls[0]["cap_add"] == []


def test_list_and_read_downloads(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "chromium": WorkerDefinition(
                image="worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network=None,
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
    )

    downloads = launcher.list_downloads("container-1")
    download = launcher.read_download("container-1", "notes.txt")

    assert [item.filename for item in downloads] == ["notes.txt", "report.pdf"]
    assert download.filename == "notes.txt"
    assert download.content == b"hello world"


def test_missing_download_raises_not_found(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "chromium": WorkerDefinition(
                image="worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network=None,
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
    )

    try:
        launcher.read_download("container-1", "missing.txt")
    except FileNotFoundError:
        pass
    else:  # pragma: no cover - explicit assertion
        raise AssertionError("Expected FileNotFoundError for missing download")


def test_capture_screenshot_returns_png_bytes(monkeypatch) -> None:
    client = DummyDockerClient()
    monkeypatch.setattr(launcher_module.docker, "from_env", lambda: client)

    launcher = DockerSessionLauncher(
        worker_definitions={
            "chromium": WorkerDefinition(
                image="worker:latest",
                build_context=None,
                dockerfile=None,
            )
        },
        command=None,
        network=None,
        turn_public_host="localhost",
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
    )

    screenshot = launcher.capture_screenshot("container-1", "sess_test", 1280, 720)

    assert screenshot.filename == "sess_test-screenshot.png"
    assert screenshot.content_type == "image/png"
    assert screenshot.content.startswith(b"\x89PNG\r\n\x1a\n")
