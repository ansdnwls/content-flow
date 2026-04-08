"""Compatibility wrapper for the Stripe SDK."""

from __future__ import annotations

from types import SimpleNamespace


class StripeNotInstalledError(RuntimeError):
    """Raised when billing code is used without the Stripe SDK installed."""


def _missing(*_args, **_kwargs):
    raise StripeNotInstalledError(
        "Stripe SDK is not installed. Add `stripe` to the environment to use billing features."
    )


try:
    import stripe as stripe  # type: ignore[no-redef]
except ModuleNotFoundError:
    stripe = SimpleNamespace(
        api_key=None,
        Customer=SimpleNamespace(create=_missing),
        Subscription=SimpleNamespace(modify=_missing, retrieve=_missing),
        Webhook=SimpleNamespace(construct_event=_missing),
        checkout=SimpleNamespace(Session=SimpleNamespace(create=_missing)),
        billing_portal=SimpleNamespace(Session=SimpleNamespace(create=_missing)),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
        Event=object,
    )
