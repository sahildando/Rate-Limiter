"""Application-wide exception types and handlers."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error with HTTP status and machine-readable code."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", *, code: str = "NOT_FOUND") -> None:
        super().__init__(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


class AuthenticationError(AppError):
    def __init__(
        self,
        message: str = "Authentication failed",
        *,
        code: str = "AUTHENTICATION_FAILED",
    ) -> None:
        super().__init__(message, code=code, status_code=status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(AppError):
    def __init__(
        self,
        message: str = "Access denied",
        *,
        code: str = "AUTHORIZATION_FAILED",
    ) -> None:
        super().__init__(message, code=code, status_code=status.HTTP_403_FORBIDDEN)


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Resource conflict",
        *,
        code: str = "CONFLICT",
    ) -> None:
        super().__init__(message, code=code, status_code=status.HTTP_409_CONFLICT)


class SSRFValidationError(AppError):
    def __init__(
        self,
        message: str = "URL is not allowed",
        *,
        code: str = "SSRF_BLOCKED",
    ) -> None:
        super().__init__(message, code=code, status_code=status.HTTP_400_BAD_REQUEST)


class RateLimitExceededError(AppError):
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        code: str = "RATE_LIMIT_EXCEEDED",
    ) -> None:
        super().__init__(message, code=code, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


class ServiceUnavailableError(AppError):
    def __init__(
        self,
        message: str = "Service unavailable",
        *,
        code: str = "SERVICE_UNAVAILABLE",
    ) -> None:
        super().__init__(message, code=code, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        body: dict[str, Any] = {
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        }
        if exc.details:
            body["error"]["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )
