import logging
import os
from typing import Awaitable, Callable

from fastapi import Request, Response, FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class CsrfMiddleware(BaseHTTPMiddleware):  
    """
    For state-changing requests (POST, PUT, DELETE, PATCH):
    1. Reads csrf_token from cookies
    2. Validates X-CSRF-Token header matches the cookie
    3. Returns 403 Forbidden if validation fails
    """
    EXCLUDED_PREFIXES = (
        "/api/v1/auth/oauth/",  # OAuth callbacks use GET
    )
    EXEMPT_ENDPOINTS = ["/login", "/signup", "/refresh"]

    async def dispatch(self, request, call_next:Callable[[Request], Awaitable[Response]])-> Response:
        env = os.getenv("ENVIRONMENT","").lower()
        if env != 'production' or request.method == 'GET' or request.url.path in self.EXCLUDED_PREFIXES:
            return await call_next(request) #because in non production environments we skip csrf
        
        cookie_token = request.cookies.get("csrf_token")
        # Get CSRF token from header
        header_token = request.headers.get("X-CSRF-Token")
        #cookie token and header token should match
        if not cookie_token or not header_token:
            logger.warning(
                "csrf_validation_failed",
                extra={
                    "event": "csrf_validation_failed",
                    "reason": "missing_token",
                    "path": request.url.path,
                    "method": request.method,
                    "has_cookie": bool(cookie_token),
                    "has_header": bool(header_token),
                },
            )
            return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing"},
            )
    
        if cookie_token != header_token:
            logger.warning(
                "csrf_validation_failed",
                extra={
                    "event": "csrf_validation_failed",
                    "reason": "token_mismatch",
                    "path": request.url.path,
                    "method": request.method,
                },
            )

            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token mismatch"},
            )
        
        return await call_next(request)
    

def add_csrf_middleware(app:FastAPI) -> None:
    """Add CSRF middleware to the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(CsrfMiddleware)
    logger.info("CSRF middleware added to application")

def add_cors_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        
    )