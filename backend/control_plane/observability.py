from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from .contracts import SCHEMA_VERSION


_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
LOGGER = logging.getLogger("agency.control_plane")


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(message)s")


def correlation_id_for(request: Request) -> str:
    supplied = request.headers.get("X-Correlation-ID")
    if supplied and _CORRELATION_ID.fullmatch(supplied):
        return supplied
    return "corr-{}".format(uuid.uuid4().hex)


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started = time.perf_counter()
    correlation_id = correlation_id_for(request)
    request.state.correlation_id = correlation_id
    status_code = 500
    try:
        try:
            response = await call_next(request)
        except Exception as error:
            LOGGER.error(
                json.dumps(
                    {
                        "event": "unhandled_exception",
                        "correlation_id": correlation_id,
                        "exception_type": type(error).__name__,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "schema_version": SCHEMA_VERSION,
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "The control plane could not complete the request",
                        "correlation_id": correlation_id,
                        "details": {},
                    },
                },
            )
        status_code = response.status_code
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
            "form-action 'self'; img-src 'self' data:; font-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'"
        )
        return response
    finally:
        record = {
            "event": "http_request",
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        tenant_id = getattr(request.state, "tenant_id", None)
        principal_id = getattr(request.state, "principal_id", None)
        run_id = request.path_params.get("run_id")
        if tenant_id is not None:
            record["tenant_id"] = tenant_id
        if principal_id is not None:
            record["principal_id"] = principal_id
        if run_id is not None:
            record["run_id"] = run_id
        LOGGER.info(
            json.dumps(
                record,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
