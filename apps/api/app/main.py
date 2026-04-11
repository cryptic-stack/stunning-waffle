from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from redis import Redis

from app.api.routes.automation import router as automation_router
from app.api.routes.health import router as health_router
from app.api.routes.rtc import router as rtc_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.signaling import router as signaling_router
from app.config import Settings, get_settings
from app.db import create_engine_and_factory, init_db
from app.launcher import DockerSessionLauncher, StubSessionLauncher, WorkerDefinition
from app.logging import configure_logging
from app.middleware import CorrelationIdMiddleware
from app.redis_store import RedisSessionStore
from app.services.sweeper import SessionSweeper
from app.signaling import SignalingRegistry


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings: Settings = application.state.settings
    configure_logging(settings.log_level)

    engine, session_factory = create_engine_and_factory(settings)
    init_db(engine)

    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    application.state.redis_store = RedisSessionStore(
        client=application.state.redis_client,
        namespace=settings.redis_namespace,
    )
    application.state.signaling_registry = SignalingRegistry()
    application.state.launcher = (
        DockerSessionLauncher(
            worker_definitions={
                "chromium": WorkerDefinition(
                    image=settings.worker_image,
                    build_context=settings.worker_build_context,
                    dockerfile=settings.worker_dockerfile,
                ),
                "firefox": WorkerDefinition(
                    image=settings.firefox_worker_image,
                    build_context=(
                        settings.firefox_worker_build_context or settings.worker_build_context
                    ),
                    dockerfile=settings.firefox_worker_dockerfile,
                ),
                "brave": WorkerDefinition(
                    image=settings.brave_worker_image,
                    build_context=(
                        settings.brave_worker_build_context or settings.worker_build_context
                    ),
                    dockerfile=settings.brave_worker_dockerfile,
                ),
                "edge": WorkerDefinition(
                    image=settings.edge_worker_image,
                    build_context=(
                        settings.edge_worker_build_context or settings.worker_build_context
                    ),
                    dockerfile=settings.edge_worker_dockerfile,
                ),
                "vivaldi": WorkerDefinition(
                    image=settings.vivaldi_worker_image,
                    build_context=(
                        settings.vivaldi_worker_build_context or settings.worker_build_context
                    ),
                    dockerfile=settings.vivaldi_worker_dockerfile,
                ),
                "ubuntu-xfce": WorkerDefinition(
                    image=settings.ubuntu_xfce_worker_image,
                    build_context=(
                        settings.ubuntu_xfce_worker_build_context or settings.worker_build_context
                    ),
                    dockerfile=settings.ubuntu_xfce_worker_dockerfile,
                ),
                "kali-xfce": WorkerDefinition(
                    image=settings.kali_xfce_worker_image,
                    build_context=(
                        settings.kali_xfce_worker_build_context or settings.worker_build_context
                    ),
                    dockerfile=settings.kali_xfce_worker_dockerfile,
                ),
            },
            command=settings.worker_command,
            network=settings.worker_network,
            turn_public_host=settings.turn_public_host,
            turn_internal_host=settings.turn_internal_host,
            turn_username=settings.turn_username,
            turn_password=settings.turn_password,
            turn_tls_enabled=settings.turn_tls_enabled,
            cpu_limit=settings.worker_cpu_limit,
            memory_limit=settings.worker_memory_limit,
            pids_limit=settings.worker_pids_limit,
            read_only_rootfs=settings.worker_read_only_rootfs,
            tmpfs_size_mb=settings.worker_tmpfs_size_mb,
            allow_outbound_network=settings.worker_allow_outbound_network,
            host_gateway_alias=(
                settings.host_gateway_alias if settings.enable_host_local_targets else None
            ),
            allow_runtime_image_resolution=settings.worker_allow_runtime_image_resolution,
        )
        if settings.session_launch_mode == "docker"
        else StubSessionLauncher()
    )
    if (
        settings.session_launch_mode == "docker"
        and settings.worker_verify_images_on_startup
        and isinstance(application.state.launcher, DockerSessionLauncher)
    ):
        application.state.launcher.validate_worker_images()
    application.state.sweeper = SessionSweeper(
        session_factory=session_factory,
        redis_store=application.state.redis_store,
        launcher=application.state.launcher,
        settings=settings,
    )

    async def run_sweeper() -> None:
        while True:
            await asyncio.to_thread(application.state.sweeper.sweep_once)
            await asyncio.sleep(settings.sweeper_interval_seconds)

    sweeper_task = asyncio.create_task(run_sweeper())
    try:
        yield
    finally:
        sweeper_task.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper_task
        application.state.redis_client.close()
        engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    application = FastAPI(
        title="foss-browserlab API",
        version="0.1.0",
        summary="Control plane for browser session orchestration and signaling",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.add_middleware(CorrelationIdMiddleware, settings=resolved_settings)
    application.include_router(health_router)
    application.include_router(automation_router)
    application.include_router(rtc_router)
    application.include_router(sessions_router)
    application.include_router(signaling_router)

    return application


app = create_app()
