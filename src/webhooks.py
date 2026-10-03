import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


EVENT_TYPES = frozenset({
    "payment.success",
    "payment.failed",
    "subscription.canceled",
    "subscription.renewed",
    "subscription.upgraded",
    "subscription.downgraded",
})

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2


@dataclass
class WebhookEvent:
    event_type: str
    subscription_id: str
    user_id: str
    payload: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: _generate_event_id())

    def __post_init__(self):
        if self.event_type not in EVENT_TYPES:
            raise ValueError(
                f"Unknown event type {self.event_type!r}. "
                f"Valid types: {sorted(EVENT_TYPES)}"
            )


def _generate_event_id() -> str:
    import uuid
    return f"evt_{uuid.uuid4().hex}"


def format_event_payload(event: WebhookEvent) -> bytes:
    """Serialize a WebhookEvent to a UTF-8 JSON body suitable for HTTP dispatch."""
    body = {
        "id": event.event_id,
        "type": event.event_type,
        "subscription_id": event.subscription_id,
        "user_id": event.user_id,
        "timestamp": event.timestamp.isoformat(),
        "data": event.payload,
    }
    return json.dumps(body, default=str).encode("utf-8")


@dataclass
class DispatchResult:
    endpoint: str
    success: bool
    attempts: int
    status_code: Optional[int] = None
    error: Optional[str] = None


class WebhookDispatcher:
    """Dispatch WebhookEvents to one or more HTTP endpoints with retry logic."""

    def __init__(self, endpoints: list[str], timeout_seconds: int = 10):
        if not endpoints:
            raise ValueError("WebhookDispatcher requires at least one endpoint URL")
        self.endpoints = list(endpoints)
        self.timeout_seconds = timeout_seconds

    def dispatch(self, event: WebhookEvent) -> list[DispatchResult]:
        """Dispatch to all registered endpoints, returning one result per endpoint."""
        return [self._send_to_endpoint(event, url) for url in self.endpoints]

    def dispatch_with_retry(self, event: WebhookEvent) -> list[DispatchResult]:
        """Dispatch with exponential backoff retry (up to MAX_RETRIES attempts)."""
        return [self._send_with_retry(event, url) for url in self.endpoints]

    def _send_to_endpoint(self, event: WebhookEvent, url: str) -> DispatchResult:
        body = format_event_payload(event)
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Event": event.event_type,
                "X-Webhook-ID": event.event_id,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                return DispatchResult(
                    endpoint=url,
                    success=True,
                    attempts=1,
                    status_code=resp.status,
                )
        except urllib.error.HTTPError as e:
            return DispatchResult(
                endpoint=url,
                success=False,
                attempts=1,
                status_code=e.code,
                error=str(e),
            )
        except Exception as e:
            return DispatchResult(
                endpoint=url,
                success=False,
                attempts=1,
                error=str(e),
            )

    def _send_with_retry(self, event: WebhookEvent, url: str) -> DispatchResult:
        body = format_event_payload(event)
        last_error: Optional[str] = None
        last_status: Optional[int] = None

        for attempt in range(1, MAX_RETRIES + 1):
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Event": event.event_type,
                    "X-Webhook-ID": event.event_id,
                    "X-Webhook-Attempt": str(attempt),
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    return DispatchResult(
                        endpoint=url,
                        success=True,
                        attempts=attempt,
                        status_code=resp.status,
                    )
            except urllib.error.HTTPError as e:
                last_status = e.code
                last_error = str(e)
                # Don't retry 4xx errors — they indicate a client problem
                if 400 <= e.code < 500:
                    break
            except Exception as e:
                last_error = str(e)

            if attempt < MAX_RETRIES:
                time.sleep(BASE_BACKOFF_SECONDS ** attempt)

        return DispatchResult(
            endpoint=url,
            success=False,
            attempts=attempt,
            status_code=last_status,
            error=last_error,
        )
