from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import Counter, defaultdict
from typing import Dict, Mapping, Optional, Tuple

from .version import VERSION


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
HTTP_DURATION_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)
HTTP_LOGGER = logging.getLogger("agency_runtime.http")
HTTP_LOGGER.setLevel(logging.INFO)


def request_id_from_header(value: Optional[str]) -> str:
    """Accept bounded correlation IDs or generate an opaque replacement."""
    if value and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return "req-{}".format(uuid.uuid4().hex)


def structured_http_log(
    *,
    request_id: str,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
    tenant_id: str = "",
) -> None:
    event: Dict[str, object] = {
        "event": "http_request_completed",
        "request_id": request_id,
        "method": method,
        "route": route,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 3),
    }
    if tenant_id:
        event["tenant_id"] = tenant_id
    HTTP_LOGGER.info(
        json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _bucket_label(value: float) -> str:
    return "{:g}".format(value)


def _labels(values: Mapping[str, str]) -> str:
    content = ",".join(
        '{}="{}"'.format(key, _escape_label(value))
        for key, value in sorted(values.items())
    )
    return "{" + content + "}"


class RuntimeMetrics:
    """Low-cardinality Prometheus metrics with no tenant or content labels."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._requests: Counter[Tuple[str, str, str]] = Counter()
        self._duration_sum: Dict[Tuple[str, str], float] = defaultdict(float)
        self._duration_count: Counter[Tuple[str, str]] = Counter()
        self._duration_buckets: Counter[Tuple[str, str, float]] = Counter()
        self._runs_started = 0
        self._greenlights: Counter[str] = Counter()
        self._sessions: Counter[str] = Counter()
        self._authentication: Counter[str] = Counter()
        self._security_denials: Counter[str] = Counter()

    def record_http(
        self,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        method_label = method.upper()
        route_label = route or "unmatched"
        status_label = str(status_code)
        with self._lock:
            self._requests[(method_label, route_label, status_label)] += 1
            observed_duration = max(0.0, duration_seconds)
            self._duration_sum[(method_label, route_label)] += observed_duration
            self._duration_count[(method_label, route_label)] += 1
            for boundary in HTTP_DURATION_BUCKETS:
                if observed_duration <= boundary:
                    self._duration_buckets[(method_label, route_label, boundary)] += 1

    def run_started(self) -> None:
        with self._lock:
            self._runs_started += 1

    def greenlight_decided(self, decision: str) -> None:
        with self._lock:
            self._greenlights[decision] += 1

    def session_changed(self, action: str) -> None:
        with self._lock:
            self._sessions[action] += 1

    def authentication_attempt(self, outcome: str) -> None:
        if outcome not in {"succeeded", "failed", "rate_limited"}:
            raise ValueError("unsupported authentication outcome")
        with self._lock:
            self._authentication[outcome] += 1

    def security_denial(self, reason: str) -> None:
        if reason not in {"authorization", "csrf"}:
            raise ValueError("unsupported security denial reason")
        with self._lock:
            self._security_denials[reason] += 1

    def render(self) -> str:
        with self._lock:
            requests = dict(self._requests)
            duration_sum = dict(self._duration_sum)
            duration_count = dict(self._duration_count)
            duration_buckets = dict(self._duration_buckets)
            runs_started = self._runs_started
            greenlights = dict(self._greenlights)
            sessions = dict(self._sessions)
            authentication = dict(self._authentication)
            security_denials = dict(self._security_denials)

        lines = [
            "# HELP agency_runtime_info Static runtime build information.",
            "# TYPE agency_runtime_info gauge",
            'agency_runtime_info{{mode="deterministic_sandbox",version="{}"}} 1'.format(
                VERSION
            ),
            "# HELP agency_http_requests_total HTTP requests by method, route template, and status.",
            "# TYPE agency_http_requests_total counter",
        ]
        for (method, route, status_code), value in sorted(requests.items()):
            lines.append(
                "agency_http_requests_total{} {}".format(
                    _labels(
                        {
                            "method": method,
                            "route": route,
                            "status": status_code,
                        }
                    ),
                    value,
                )
            )
        lines.extend(
            [
                "# HELP agency_http_request_duration_seconds HTTP request duration histogram.",
                "# TYPE agency_http_request_duration_seconds histogram",
            ]
        )
        for method, route in sorted(duration_count):
            for boundary in HTTP_DURATION_BUCKETS:
                lines.append(
                    "agency_http_request_duration_seconds_bucket{} {}".format(
                        _labels(
                            {
                                "le": _bucket_label(boundary),
                                "method": method,
                                "route": route,
                            }
                        ),
                        duration_buckets.get((method, route, boundary), 0),
                    )
                )
            lines.append(
                "agency_http_request_duration_seconds_bucket{} {}".format(
                    _labels({"le": "+Inf", "method": method, "route": route}),
                    duration_count[(method, route)],
                )
            )
            lines.append(
                "agency_http_request_duration_seconds_sum{} {:.9f}".format(
                    _labels({"method": method, "route": route}),
                    duration_sum[(method, route)],
                )
            )
            lines.append(
                "agency_http_request_duration_seconds_count{} {}".format(
                    _labels({"method": method, "route": route}),
                    duration_count[(method, route)],
                )
            )
        lines.extend(
            [
                "# HELP agency_runs_started_total Tenant-scoped agency runs persisted successfully.",
                "# TYPE agency_runs_started_total counter",
                "agency_runs_started_total {}".format(runs_started),
                "# HELP agency_greenlight_decisions_total Durable Greenlight decisions by outcome.",
                "# TYPE agency_greenlight_decisions_total counter",
            ]
        )
        for decision, value in sorted(greenlights.items()):
            lines.append(
                "agency_greenlight_decisions_total{} {}".format(
                    _labels({"decision": decision}), value
                )
            )
        lines.extend(
            [
                "# HELP agency_browser_sessions_total Browser session lifecycle events.",
                "# TYPE agency_browser_sessions_total counter",
            ]
        )
        for action, value in sorted(sessions.items()):
            lines.append(
                "agency_browser_sessions_total{} {}".format(
                    _labels({"action": action}), value
                )
            )
        lines.extend(
            [
                "# HELP agency_authentication_attempts_total Authentication results without identity labels.",
                "# TYPE agency_authentication_attempts_total counter",
            ]
        )
        for outcome, value in sorted(authentication.items()):
            lines.append(
                "agency_authentication_attempts_total{} {}".format(
                    _labels({"outcome": outcome}), value
                )
            )
        lines.extend(
            [
                "# HELP agency_security_denials_total Authenticated security denials by bounded reason.",
                "# TYPE agency_security_denials_total counter",
            ]
        )
        for reason, value in sorted(security_denials.items()):
            lines.append(
                "agency_security_denials_total{} {}".format(
                    _labels({"reason": reason}), value
                )
            )
        return "\n".join(lines) + "\n"


class RequestTimer:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    def elapsed_seconds(self) -> float:
        return max(0.0, time.perf_counter() - self.started)
