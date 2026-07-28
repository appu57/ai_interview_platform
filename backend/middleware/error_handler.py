import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.core.security import get_settings

logger = logging.getLogger(__name__)

SAFE_ERROR_MESSAGES = {
    400: "Bad request",
    401: "Invalid credentials",
    403: "Access denied",
    404: "Resource not found",
    405: "Method not allowed",
    409: "Conflict",
    422: "Validation error",
    429: "Too many requests",
    500: "Internal server error",
    502: "Bad gateway",
    503: "Service unavailable",
    504: "Gateway timeout",
}


def _is_production() -> bool:
    settings = get_settings()
    environment = getattr(settings, "environment", "development")
    return str(environment).strip().lower() == "production"


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _sanitize_error_detail(
    status_code: int,
    detail: Any,
    is_production: bool,
) -> Any:

    if isinstance(detail, dict):
        return detail

    if not is_production:
        if isinstance(detail, str):
            return detail
        return str(detail)

    if isinstance(detail, str):
        safe_prefixes = (
            "Missing",
            "Invalid",
            "Unknown provider",
            "Unknown model",
            "No data",
            "No URLs",
            "Portal adapter",
            "preferred_provider is required",
        )
        if any(detail.startswith(prefix) for prefix in safe_prefixes):
            return detail

    return SAFE_ERROR_MESSAGES.get(status_code, "An error occurred")


def _build_error_response(
    status_code: int,
    detail: Any,
    request_id: str,
    errors: Optional[list[dict[str, Any]]] = None,
    wrap_detail: bool = True,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "detail": detail,
    }

    if not isinstance(detail, dict):
        response["status_code"] = status_code
        response["request_id"] = request_id
        if errors:
            response["errors"] = errors

    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:

    request_id = _get_request_id(request)
    is_production = _is_production()

    logger.warning(
        "HTTP exception",
        extra={
            "event": "http_exception",
            "request_id": request_id,
            "status_code": exc.status_code,
            "detail": str(exc.detail),
            "path": request.url.path,
            "method": request.method,
        },
    )

    # Sanitize the detail for response
    sanitized_detail = _sanitize_error_detail(
        exc.status_code,
        exc.detail,
        is_production,
    )

    response_body = _build_error_response(
        status_code=exc.status_code,
        detail=sanitized_detail,
        request_id=request_id,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response_body,
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    request_id = _get_request_id(request)

    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
        )

    logger.warning(
        "Validation error",
        extra={
            "event": "validation_error",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "error_count": len(errors),
        },
    )

    response_body = _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Validation error",
        request_id=request_id,
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response_body,
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _get_request_id(request)
    is_production = _is_production()

    logger.error(
        "Unhandled exception",
        extra={
            "event": "unhandled_exception",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        },
        exc_info=True,
    )

    if is_production:
        detail = SAFE_ERROR_MESSAGES[500]
    else:
        detail = f"{type(exc).__name__}: {str(exc)}"

    response_body = _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
        request_id=request_id,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_body,
    )


def add_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, general_exception_handler)
    logger.info("Centralized error handlers added to application")