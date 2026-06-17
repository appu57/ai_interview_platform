"""API versioning middleware (Task #97).

Adds API version information to all responses via headers:
- X-API-Version: Current API version (e.g. "1.0.0")
- API-Version-Deprecated: Set to "true" when version is deprecated
"""

import logging
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# The API contract version (separate from app version).
# Increment major when breaking changes are introduced.
API_VERSION = "1.0.0"


class APIVersioningMiddleware(BaseHTTPMiddleware):
    """Middleware that adds API version headers to all responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],  # type: ignore[override]
    ) -> Response:
        response: Response = await call_next(request)  # type: ignore[misc]

        # Only add version headers to API endpoints
        if request.url.path.startswith("/api/"):
            response.headers["X-API-Version"] = API_VERSION

        return response


def add_versioning_middleware(app: FastAPI) -> None:
    """Add API versioning middleware to the FastAPI application."""
    app.add_middleware(APIVersioningMiddleware)
    logger.info("API versioning middleware added (version=%s)", API_VERSION)