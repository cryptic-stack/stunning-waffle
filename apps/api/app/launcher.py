from __future__ import annotations

import base64
import contextlib
import shlex
import socket
import time
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

import docker

BrowserName = Literal["chromium", "firefox", "brave", "edge", "vivaldi"]
DesktopProfileName = Literal["ubuntu-xfce", "kali-xfce"]
RuntimeName = Literal[
    "chromium",
    "firefox",
    "brave",
    "edge",
    "vivaldi",
    "ubuntu-xfce",
    "kali-xfce",
]
CHROMIUM_FAMILY_BROWSERS = {"chromium", "brave", "edge", "vivaldi"}
BROWSERLAB_UID = 1000
BROWSERLAB_GID = 1000


@dataclass(slots=True)
class LaunchResult:
    container_id: str | None
    metadata: dict


@dataclass(slots=True)
class WorkerDefinition:
    image: str
    build_context: str | None
    dockerfile: str | None


@dataclass(slots=True)
class UploadResult:
    filename: str
    destination_path: str
    size_bytes: int


@dataclass(slots=True)
class DownloadEntry:
    filename: str
    destination_path: str
    size_bytes: int


@dataclass(slots=True)
class DownloadContent:
    filename: str
    destination_path: str
    size_bytes: int
    content: bytes


@dataclass(slots=True)
class ScreenshotResult:
    filename: str
    content_type: str
    size_bytes: int
    content: bytes


class SessionLauncher:
    def launch(
        self,
        session_id: str,
        user_id: str,
        session_kind: str,
        runtime_name: str,
        worker_token: str,
        resolution_width: int,
        resolution_height: int,
        target_url: str,
    ) -> LaunchResult:
        raise NotImplementedError

    def terminate(self, container_id: str | None) -> None:
        raise NotImplementedError

    def cleanup_orphans(self, active_session_ids: set[str]) -> None:
        return None

    def is_container_running(self, container_id: str | None) -> bool | None:
        return None

    def upload_file(self, container_id: str | None, filename: str, content: bytes) -> UploadResult:
        raise NotImplementedError

    def list_downloads(self, container_id: str | None) -> list[DownloadEntry]:
        raise NotImplementedError

    def read_download(self, container_id: str | None, filename: str) -> DownloadContent:
        raise NotImplementedError

    def capture_screenshot(
        self,
        container_id: str | None,
        session_id: str,
        resolution_width: int,
        resolution_height: int,
    ) -> ScreenshotResult:
        raise NotImplementedError


class StubSessionLauncher(SessionLauncher):
    stub_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0ioAAAAASUVORK5CYII="
    )

    def __init__(self) -> None:
        self.launched: list[dict] = []
        self.terminated: list[str | None] = []
        self.uploaded_files: list[dict] = []
        self.download_contents: dict[str, dict[str, bytes]] = {}
        self.container_homes: dict[str, PurePosixPath] = {}

    def launch(
        self,
        session_id: str,
        user_id: str,
        session_kind: str,
        runtime_name: str,
        worker_token: str,
        resolution_width: int,
        resolution_height: int,
        target_url: str,
    ) -> LaunchResult:
        container_id = f"stub-{session_id}"
        home_dir = _runtime_home_dir(runtime_name)
        self.download_contents[container_id] = {}
        self.container_homes[container_id] = home_dir
        self.launched.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "session_kind": session_kind,
                "runtime_name": runtime_name,
                "browser": runtime_name if session_kind == "browser" else None,
                "desktop_profile": runtime_name if session_kind == "desktop" else None,
                "worker_token": worker_token,
                "container_id": container_id,
                "resolution_width": resolution_width,
                "resolution_height": resolution_height,
                "target_url": target_url,
            }
        )
        return LaunchResult(container_id=container_id, metadata={"mode": "stub"})

    def terminate(self, container_id: str | None) -> None:
        self.terminated.append(container_id)

    def upload_file(self, container_id: str | None, filename: str, content: bytes) -> UploadResult:
        if container_id is None:
            raise ValueError("Container is unavailable for file upload")
        home_dir = self.container_homes.get(container_id, PurePosixPath("/home/browserlab"))
        destination_path = f"{home_dir}/Downloads/{filename}"
        self.download_contents.setdefault(container_id, {})[filename] = content
        self.uploaded_files.append(
            {
                "container_id": container_id,
                "filename": filename,
                "destination_path": destination_path,
                "size_bytes": len(content),
            }
        )
        return UploadResult(
            filename=filename,
            destination_path=destination_path,
            size_bytes=len(content),
        )

    def list_downloads(self, container_id: str | None) -> list[DownloadEntry]:
        if container_id is None:
            raise ValueError("Container is unavailable for download listing")
        files = self.download_contents.get(container_id, {})
        home_dir = self.container_homes.get(container_id, PurePosixPath("/home/browserlab"))
        return [
            DownloadEntry(
                filename=filename,
                destination_path=f"{home_dir}/Downloads/{filename}",
                size_bytes=len(content),
            )
            for filename, content in sorted(files.items())
        ]

    def read_download(self, container_id: str | None, filename: str) -> DownloadContent:
        if container_id is None:
            raise ValueError("Container is unavailable for download retrieval")
        content = self.download_contents.get(container_id, {}).get(filename)
        if content is None:
            raise FileNotFoundError(filename)
        home_dir = self.container_homes.get(container_id, PurePosixPath("/home/browserlab"))
        return DownloadContent(
            filename=filename,
            destination_path=f"{home_dir}/Downloads/{filename}",
            size_bytes=len(content),
            content=content,
        )

    def capture_screenshot(
        self,
        container_id: str | None,
        session_id: str,
        resolution_width: int,
        resolution_height: int,
    ) -> ScreenshotResult:
        return ScreenshotResult(
            filename=f"{session_id}-screenshot.png",
            content_type="image/png",
            size_bytes=len(self.stub_png),
            content=self.stub_png,
        )


class DockerSessionLauncher(SessionLauncher):

    def __init__(
        self,
        worker_definitions: dict[str, WorkerDefinition],
        command: str | None,
        network: str | None,
        turn_public_host: str,
        turn_internal_host: str,
        turn_username: str,
        turn_password: str,
        turn_tls_enabled: bool = False,
        cpu_limit: float = 1.0,
        memory_limit: str = "2g",
        pids_limit: int = 256,
        read_only_rootfs: bool = True,
        tmpfs_size_mb: int = 512,
        allow_outbound_network: bool = True,
        host_gateway_alias: str | None = None,
        allow_runtime_image_resolution: bool = False,
    ) -> None:
        self.client = docker.from_env()
        self.worker_definitions = worker_definitions
        self.command = command
        self.network = network
        self.turn_public_host = turn_public_host
        self.turn_internal_host = turn_internal_host
        self.turn_username = turn_username
        self.turn_password = turn_password
        self.turn_tls_enabled = turn_tls_enabled
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.pids_limit = pids_limit
        self.read_only_rootfs = read_only_rootfs
        self.tmpfs_size_mb = tmpfs_size_mb
        self.allow_outbound_network = allow_outbound_network
        self.host_gateway_alias = host_gateway_alias
        self.allow_runtime_image_resolution = allow_runtime_image_resolution

    def launch(
        self,
        session_id: str,
        user_id: str,
        session_kind: str,
        runtime_name: str,
        worker_token: str,
        resolution_width: int,
        resolution_height: int,
        target_url: str,
    ) -> LaunchResult:
        worker_definition = self._worker_definition(runtime_name)
        self._ensure_image(worker_definition)
        security_options = self._security_options(runtime_name)
        home_dir = _runtime_home_dir(runtime_name)
        downloads_dir = home_dir / "Downloads"
        runtime_user = _runtime_user(runtime_name)
        runtime_uid, runtime_gid = _runtime_uid_gid(runtime_name)
        runtime_dir = f"/run/user/{runtime_uid}"
        container = self.client.containers.run(
            worker_definition.image,
            command=self.command or None,
            detach=True,
            name=f"browserlab-session-{session_id}",
            labels={
                "browserlab.managed": "true",
                "browserlab.session_id": session_id,
                "browserlab.user_id": user_id,
                "browserlab.session_kind": session_kind,
                "browserlab.runtime": runtime_name,
                "browserlab.browser": runtime_name if session_kind == "browser" else "",
                "browserlab.home_dir": str(home_dir),
            },
            network=self.network,
            nano_cpus=max(1, int(self.cpu_limit * 1_000_000_000)),
            mem_limit=self.memory_limit,
            pids_limit=self.pids_limit,
            read_only=self.read_only_rootfs,
            tmpfs=self._tmpfs_mounts(home_dir, runtime_uid, runtime_gid),
            cap_drop=["ALL"],
            cap_add=self._cap_additions(runtime_name),
            security_opt=security_options,
            init=True,
            user=runtime_user,
            extra_hosts=(
                {self.host_gateway_alias: "host-gateway"}
                if self.host_gateway_alias
                else None
            ),
            environment={
                "SESSION_ID": session_id,
                "SESSION_OWNER_ID": user_id,
                "SESSION_KIND": session_kind,
                "SESSION_RUNTIME": runtime_name,
                "SESSION_BROWSER": runtime_name if session_kind == "browser" else "",
                "SESSION_DESKTOP_PROFILE": runtime_name if session_kind == "desktop" else "",
                "SESSION_WORKER_TOKEN": worker_token,
                "SESSION_WIDTH": str(resolution_width),
                "SESSION_HEIGHT": str(resolution_height),
                "SESSION_HOMEPAGE_URL": target_url,
                "API_BASE_URL": "http://api:8000",
                "HOME": str(home_dir),
                "XDG_RUNTIME_DIR": runtime_dir,
                "ICEAUTHORITY": f"{runtime_dir}/.ICEauthority",
                "SESSION_DOWNLOADS_DIR": str(downloads_dir),
                "SESSION_PROFILE_SEED_DIR": _runtime_profile_seed_dir(runtime_name),
                "SESSION_PROFILE_SEED_ALLOWLIST": _runtime_profile_seed_allowlist(runtime_name),
                "TURN_PUBLIC_HOST": self.turn_public_host,
                "TURN_INTERNAL_HOST": self.turn_internal_host,
                "TURN_USERNAME": self.turn_username,
                "TURN_PASSWORD": self.turn_password,
                "TURN_TLS_ENABLED": str(self.turn_tls_enabled).lower(),
            },
            network_disabled=not self.allow_outbound_network,
        )
        return LaunchResult(
            container_id=container.id,
            metadata={"mode": "docker", "image": worker_definition.image},
        )

    def validate_worker_images(self) -> None:
        for worker_definition in self.worker_definitions.values():
            self._ensure_image(worker_definition)

    def terminate(self, container_id: str | None) -> None:
        if not container_id:
            return
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            return
        container.stop(timeout=2)
        container.remove(force=True)

    def cleanup_orphans(self, active_session_ids: set[str]) -> None:
        containers = self.client.containers.list(
            all=True,
            filters={"label": "browserlab.managed=true"},
        )
        for container in containers:
            session_id = container.labels.get("browserlab.session_id")
            if session_id in active_session_ids:
                continue
            try:
                container.stop(timeout=2)
            except docker.errors.APIError:
                pass
            container.remove(force=True)

    def is_container_running(self, container_id: str | None) -> bool | None:
        if not container_id:
            return None
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            return False
        container.reload()
        return container.status == "running"

    def upload_file(self, container_id: str | None, filename: str, content: bytes) -> UploadResult:
        if not container_id:
            raise ValueError("Container is unavailable for file upload")
        container = self.client.containers.get(container_id)
        destination_dir = self._downloads_dir_for_container(container)
        destination_path = destination_dir / filename
        upload_command = (
            f"mkdir -p {shlex.quote(str(destination_dir))} "
            f"&& cat > {shlex.quote(str(destination_path))}"
        )
        exec_id = self.client.api.exec_create(
            container.id,
            cmd=[
                "sh",
                "-lc",
                upload_command,
            ],
            stdin=True,
        )["Id"]
        exec_socket = self.client.api.exec_start(
            exec_id,
            detach=False,
            tty=False,
            socket=True,
        )
        try:
            raw_socket = getattr(exec_socket, "_sock", exec_socket)
            if hasattr(exec_socket, "sendall"):
                exec_socket.sendall(content)
            elif hasattr(raw_socket, "sendall"):
                raw_socket.sendall(content)
            elif hasattr(exec_socket, "write"):
                exec_socket.write(content)
                if hasattr(exec_socket, "flush"):
                    exec_socket.flush()
            else:  # pragma: no cover - defensive guard
                raise RuntimeError("Docker exec socket does not support writes")
            if hasattr(raw_socket, "shutdown"):
                with contextlib.suppress(OSError):
                    raw_socket.shutdown(socket.SHUT_WR)
        finally:
            exec_socket.close()
        exec_result = self.client.api.exec_inspect(exec_id)
        for _ in range(20):
            if exec_result.get("Running") is False or exec_result.get("ExitCode") is not None:
                break
            time.sleep(0.1)
            exec_result = self.client.api.exec_inspect(exec_id)
        if exec_result.get("ExitCode") != 0:
            raise RuntimeError("Worker container rejected the uploaded file")
        return UploadResult(
            filename=filename,
            destination_path=str(destination_path),
            size_bytes=len(content),
        )

    def list_downloads(self, container_id: str | None) -> list[DownloadEntry]:
        if not container_id:
            raise ValueError("Container is unavailable for download listing")
        container = self.client.containers.get(container_id)
        downloads_dir = self._downloads_dir_for_container(container)
        command = (
            f"if [ ! -d {shlex.quote(str(downloads_dir))} ]; then exit 0; fi; "
            f"for file in {shlex.quote(str(downloads_dir))}/*; do "
            "[ -f \"$file\" ] || continue; "
            "name=$(basename \"$file\"); "
            "size=$(wc -c < \"$file\" | tr -d '[:space:]'); "
            "printf '%s\\t%s\\n' \"$name\" \"$size\"; "
            "done"
        )
        exit_code, output = self._exec_run(container, ["sh", "-lc", command])
        if exit_code != 0:
            raise RuntimeError("Worker container rejected the downloads listing request")

        entries: list[DownloadEntry] = []
        for line in output.decode("utf-8").splitlines():
            if not line.strip():
                continue
            filename, size = line.split("\t", maxsplit=1)
            entries.append(
                DownloadEntry(
                    filename=filename,
                    destination_path=str(downloads_dir / filename),
                    size_bytes=int(size),
                )
            )
        return entries

    def read_download(self, container_id: str | None, filename: str) -> DownloadContent:
        if not container_id:
            raise ValueError("Container is unavailable for download retrieval")
        container = self.client.containers.get(container_id)
        destination_path = self._downloads_dir_for_container(container) / filename
        command = (
            f"if [ ! -f {shlex.quote(str(destination_path))} ]; then exit 4; fi; "
            f"cat {shlex.quote(str(destination_path))}"
        )
        exit_code, output = self._exec_run(container, ["sh", "-lc", command])
        if exit_code == 4:
            raise FileNotFoundError(filename)
        if exit_code != 0:
            raise RuntimeError("Worker container rejected the download retrieval request")
        return DownloadContent(
            filename=filename,
            destination_path=str(destination_path),
            size_bytes=len(output),
            content=output,
        )

    def capture_screenshot(
        self,
        container_id: str | None,
        session_id: str,
        resolution_width: int,
        resolution_height: int,
    ) -> ScreenshotResult:
        if not container_id:
            raise ValueError("Container is unavailable for screenshot capture")
        container = self.client.containers.get(container_id)
        runtime_name = container.labels.get("browserlab.runtime") or container.labels.get(
            "browserlab.browser",
            "runtime",
        )
        exit_code, output = self._exec_run(
            container,
            [
                "browserlab-session-screenshot",
                str(resolution_width),
                str(resolution_height),
                session_id,
                runtime_name,
            ],
        )
        if exit_code != 0:
            raise RuntimeError("Worker container rejected the screenshot request")
        return ScreenshotResult(
            filename=f"{session_id}-screenshot.png",
            content_type="image/png",
            size_bytes=len(output),
            content=output,
        )

    def _ensure_image(self, worker_definition: WorkerDefinition) -> None:
        try:
            self.client.images.get(worker_definition.image)
            return
        except docker.errors.ImageNotFound:
            pass

        if not self.allow_runtime_image_resolution:
            raise RuntimeError(
                "Missing worker image "
                f"{worker_definition.image}. Prebuild worker images before starting the API."
            )

        if worker_definition.build_context and worker_definition.dockerfile:
            self.client.images.build(
                path=worker_definition.build_context,
                dockerfile=worker_definition.dockerfile,
                tag=worker_definition.image,
                rm=True,
            )
            return

        self.client.images.pull(worker_definition.image)

    def _worker_definition(self, runtime_name: str) -> WorkerDefinition:
        definition = self.worker_definitions.get(runtime_name)
        if definition is None:
            raise ValueError(f"Unsupported worker runtime: {runtime_name}")
        return definition

    def _tmpfs_mounts(
        self,
        home_dir: PurePosixPath,
        runtime_uid: int,
        runtime_gid: int,
    ) -> dict[str, str]:
        user_owned = f"uid={runtime_uid},gid={runtime_gid}"
        return {
            "/tmp": f"rw,noexec,nosuid,nodev,size={self.tmpfs_size_mb}m,mode=1777",
            str(home_dir / ".cache"): (
                f"rw,nosuid,nodev,size={self.tmpfs_size_mb}m,{user_owned},mode=700"
            ),
            str(home_dir / ".config"): f"rw,nosuid,nodev,size=256m,{user_owned},mode=700",
            str(home_dir / ".local/share"): f"rw,nosuid,nodev,size=256m,{user_owned},mode=700",
            str(home_dir / ".mozilla"): f"rw,nosuid,nodev,size=128m,{user_owned},mode=700",
            str(home_dir / "Desktop"): f"rw,nosuid,nodev,size=64m,{user_owned},mode=755",
            str(home_dir / "Downloads"): f"rw,nosuid,nodev,size=256m,{user_owned},mode=755",
            f"/run/user/{runtime_uid}": f"rw,nosuid,nodev,size=32m,{user_owned},mode=700",
        }

    @staticmethod
    def _downloads_dir_for_container(container) -> PurePosixPath:
        home_dir = PurePosixPath(container.labels.get("browserlab.home_dir", "/home/browserlab"))
        return home_dir / "Downloads"

    @staticmethod
    def _security_options(runtime_name: str) -> list[str]:
        # Chromium's own Linux sandbox requires namespace syscalls that Docker's default
        # seccomp profile blocks. Run Chromium-family workers with a relaxed container seccomp
        # policy so the browser sandbox can stay enabled, and keep no-new-privileges for
        # the other worker types that don't depend on the setuid sandbox helper.
        if runtime_name in CHROMIUM_FAMILY_BROWSERS:
            return ["seccomp=unconfined"]
        if runtime_name == "kali-xfce":
            return []
        return ["no-new-privileges:true"]

    @staticmethod
    def _cap_additions(runtime_name: str) -> list[str]:
        if runtime_name == "kali-xfce":
            return ["SETUID", "SETGID", "AUDIT_WRITE", "NET_RAW"]
        return []

    @staticmethod
    def _exec_run(container, command: list[str]) -> tuple[int, bytes]:
        result = container.exec_run(command)
        if hasattr(result, "exit_code") and hasattr(result, "output"):
            return result.exit_code, result.output
        return result[0], result[1]


def _runtime_home_dir(runtime_name: str) -> PurePosixPath:
    return PurePosixPath("/home/browserlab")


def _runtime_user(runtime_name: str) -> str:
    return "browserlab"


def _runtime_uid_gid(runtime_name: str) -> tuple[int, int]:
    if runtime_name == "ubuntu-xfce":
        return (1001, 1001)
    return (BROWSERLAB_UID, BROWSERLAB_GID)


def _runtime_profile_seed_dir(runtime_name: str) -> str:
    return ""


def _runtime_profile_seed_allowlist(runtime_name: str) -> str:
    return ""
