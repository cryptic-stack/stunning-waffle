from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.config import Settings


@dataclass(slots=True)
class AuthenticatedUser:
    user_id: str
    email: str | None
    display_name: str | None


def resolve_user(
    settings: Settings,
    user_id: str | None,
    email: str | None,
    display_name: str | None,
) -> AuthenticatedUser:
    if settings.auth_mode == "header":
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user header is required",
            )
        return AuthenticatedUser(
            user_id=user_id,
            email=email,
            display_name=display_name,
        )
    return AuthenticatedUser(
        user_id=user_id or settings.default_user_id,
        email=email or settings.default_user_email,
        display_name=display_name or settings.default_user_display_name,
    )


def auth_headers(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_user_name: str | None = Header(default=None, alias="X-User-Name"),
) -> tuple[str | None, str | None, str | None]:
    return x_user_id, x_user_email, x_user_name


def authorization_header(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str | None:
    return authorization


def resolve_api_key_user(settings: Settings, authorization: str | None) -> AuthenticatedUser:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer API key is required",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization must use the Bearer scheme",
        )

    principal = settings.automation_api_keys().get(token)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Automation API key is invalid",
        )

    return AuthenticatedUser(
        user_id=principal["user_id"] or "automation-client",
        email=principal.get("email"),
        display_name=principal.get("display_name"),
    )
