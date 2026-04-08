"""Shared OpenAPI error response schemas for all API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Standard error envelope returned by all error responses."""

    detail: str = Field(description="Human-readable error message.")


# -- Reusable `responses` dicts for FastAPI route decorators ----------------

AUTH_ERRORS: dict = {
    401: {
        "model": ErrorDetail,
        "description": "Missing or invalid API key.",
        "content": {
            "application/json": {
                "example": {"detail": "Invalid or missing API key"},
            },
        },
    },
}

RATE_LIMIT_ERROR: dict = {
    429: {
        "model": ErrorDetail,
        "description": "Rate limit exceeded. Check `Retry-After` header.",
        "content": {
            "application/json": {
                "example": {"detail": "Rate limit exceeded"},
            },
        },
    },
}

NOT_FOUND_ERROR: dict = {
    404: {
        "model": ErrorDetail,
        "description": "Requested resource not found.",
        "content": {
            "application/json": {
                "example": {"detail": "Resource 'abc-123' not found"},
            },
        },
    },
}

CONFLICT_ERROR: dict = {
    409: {
        "model": ErrorDetail,
        "description": "Action conflicts with the current resource state.",
        "content": {
            "application/json": {
                "example": {"detail": "Cannot perform action on current state"},
            },
        },
    },
}

BILLING_ERROR: dict = {
    402: {
        "model": ErrorDetail,
        "description": "Plan limit exceeded. Upgrade for higher limits.",
        "content": {
            "application/json": {
                "example": {"detail": "Monthly post limit reached (20)."},
            },
        },
    },
}

# -- Common combinations ---------------------------------------------------

COMMON_RESPONSES: dict = {**AUTH_ERRORS, **RATE_LIMIT_ERROR}
