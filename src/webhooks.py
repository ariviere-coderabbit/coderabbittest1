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
        """Raise ValueError if event_type is not in EVENT_TYPES."""
        if self.event_type not in EVENT_TYPES:
            raise ValueError(
                f"Unknown event type {self.event_type!r}. "
                f"Valid types: {sorted(EVENT_TYPES)}"
            )


def _generate_event_id() -> str:
    """Return an event ID prefixed with ``evt_`` followed by a UUID4 hex string."""
    import uuid
    return f"evt_{uuid.uuid4().hex}"


def format_event_payload(event: WebhookEvent) -> bytes:
    """Serialize a WebhookEvent to a UTF-8 JSON body suitable for HTTP dispatch.

    Include the event and subscription/user IDs, type, ISO-formatted timestamp,
    and payload as ``data``. Values unsupported by JSON are converted with str.

    Raises:
        TypeError: If a dictionary key is unsupported by JSON.
        ValueError: If the payload contains a circular reference.
    """
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
        """Copy the endpoint list and set the timeout for blocking URL operations.

        timeout_seconds applies to each delivery attempt, not the entire dispatch.
        Endpoint URLs are not validated here.

        Raises:
            ValueError: If endpoints is empty.
        """
        if not endpoints:
            raise ValueError("WebhookDispatcher requires at least one endpoint URL")
        self.endpoints = list(endpoints)
        self.timeout_seconds = timeout_seconds

    def dispatch(self, event: WebhookEvent) -> list[DispatchResult]:
        """Dispatch to all registered endpoints, returning one result per endpoint.

        Send once per endpoint, sequentially in registration order. Delivery
        exceptions become failed results; HTTP errors include their status code.
        Payload serialization and request construction errors propagate, aborting
        dispatch before later endpoints are processed.
        """
        return [self._send_to_endpoint(event, url) for url in self.endpoints]

    def dispatch_with_retry(self, event: WebhookEvent) -> list[DispatchResult]:
        """Dispatch with exponential backoff retry (up to MAX_RETRIES attempts).

        Process endpoints sequentially, returning one result per endpoint in
        registration order. Stop retrying on success or an HTTP 4xx error; retry
        other delivery exceptions. With the default constants, make at most three
        total attempts per endpoint, sleeping for two then four seconds between
        attempts. Results include the attempt count and any final error; a failed
        result retains the most recent HTTP error status, if any.

        Payload serialization and request construction errors propagate, aborting
        dispatch before later endpoints are processed.
        """
        return [self._send_with_retry(event, url) for url in self.endpoints]

    def _send_to_endpoint(self, event: WebhookEvent, url: str) -> DispatchResult:
        """POST the event as JSON to url and return a result with one attempt.

        Delivery exceptions become failed results with an error message and,
        for HTTP errors, a status code. Payload serialization and request
        construction errors propagate instead.
        """
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
        """POST to url up to MAX_RETRIES times, stopping on success or HTTP 4xx.

        Retry other delivery exceptions after sleeping BASE_BACKOFF_SECONDS
        raised to the completed attempt number, in seconds. Return the attempt
        count and response status on success; on failure, return the last error
        and most recent HTTP error status, even if a later error was non-HTTP.
        Payload serialization and request construction errors propagate instead.
        """
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
