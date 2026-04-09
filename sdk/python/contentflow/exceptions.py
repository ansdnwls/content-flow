"""ContentFlow SDK exceptions."""

from __future__ import annotations


class ContentFlowError(Exception):
    """Base exception for all ContentFlow SDK errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class APIError(ContentFlowError):
    """Non-2xx response from the ContentFlow API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: object = None,
    ) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(message)

    def __str__(self) -> str:
        return f"HTTP {self.status_code}: {self.message}"


class AuthenticationError(APIError):
    """401 Unauthorized — invalid or missing API key."""

    def __init__(self, body: object = None) -> None:
        super().__init__(
            "Invalid or missing API key",
            status_code=401,
            body=body,
        )


class RateLimitError(APIError):
    """429 Too Many Requests — rate limit exceeded."""

    def __init__(
        self,
        *,
        retry_after: str | None = None,
        body: object = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(
            "Rate limit exceeded",
            status_code=429,
            body=body,
        )


class NotFoundError(APIError):
    """404 Not Found — resource does not exist."""

    def __init__(self, resource: str = "Resource", body: object = None) -> None:
        super().__init__(
            f"{resource} not found",
            status_code=404,
            body=body,
        )


class ValidationError(APIError):
    """422 Unprocessable Entity — request body validation failed."""

    def __init__(self, message: str = "Validation error", body: object = None) -> None:
        super().__init__(message, status_code=422, body=body)


class WebhookVerificationError(ContentFlowError):
    """Webhook signature verification failed."""

    def __init__(self) -> None:
        super().__init__("Webhook signature verification failed")
