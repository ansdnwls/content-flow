"""Stripe webhook handler — processes subscription lifecycle events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from app.core.db import get_supabase
from app.core.stripe_client import stripe

router = APIRouter(prefix="/api/webhooks", tags=["Stripe Webhooks"])

HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
    "invoice.payment_succeeded",
}


def _verify_signature(payload: bytes, sig_header: str) -> Any:
    settings = get_settings()
    try:
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret,
        )
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc


def _find_user_by_customer(customer_id: str) -> dict | None:
    sb = get_supabase()
    result = (
        sb.table("users")
        .select("id, plan")
        .eq("stripe_customer_id", customer_id)
        .maybe_single()
        .execute()
    )
    return result.data


def _handle_checkout_completed(session: dict) -> None:
    """Payment complete — activate the plan."""
    customer_id = session.get("customer")
    user = _find_user_by_customer(customer_id)
    if not user:
        return

    plan = (session.get("metadata") or {}).get("plan", "build")
    subscription_id = session.get("subscription")

    sb = get_supabase()
    sb.table("users").update({
        "plan": plan,
        "stripe_subscription_id": subscription_id,
        "subscription_status": "active",
    }).eq("id", user["id"]).execute()

    sb.table("subscription_events").insert({
        "user_id": user["id"],
        "event_type": "checkout.completed",
        "from_plan": user["plan"],
        "to_plan": plan,
        "metadata": {"subscription_id": subscription_id},
    }).execute()


def _handle_subscription_updated(subscription: dict) -> None:
    """Subscription changed — sync status."""
    customer_id = subscription.get("customer")
    user = _find_user_by_customer(customer_id)
    if not user:
        return

    period_end = subscription.get("current_period_end")
    period_end_iso = (
        datetime.fromtimestamp(period_end, tz=UTC).isoformat()
        if period_end
        else None
    )

    sb = get_supabase()
    sb.table("users").update({
        "subscription_status": subscription.get("status", "active"),
        "current_period_end": period_end_iso,
        "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
    }).eq("id", user["id"]).execute()


def _handle_subscription_deleted(subscription: dict) -> None:
    """Subscription cancelled — downgrade to free."""
    customer_id = subscription.get("customer")
    user = _find_user_by_customer(customer_id)
    if not user:
        return

    sb = get_supabase()
    old_plan = user["plan"]
    sb.table("users").update({
        "plan": "free",
        "subscription_status": "canceled",
        "stripe_subscription_id": None,
        "cancel_at_period_end": False,
    }).eq("id", user["id"]).execute()

    sb.table("subscription_events").insert({
        "user_id": user["id"],
        "event_type": "subscription.deleted",
        "from_plan": old_plan,
        "to_plan": "free",
    }).execute()


def _handle_payment_failed(invoice: dict) -> None:
    """Payment failed — mark subscription as past_due."""
    customer_id = invoice.get("customer")
    user = _find_user_by_customer(customer_id)
    if not user:
        return

    sb = get_supabase()
    sb.table("users").update({
        "subscription_status": "past_due",
    }).eq("id", user["id"]).execute()

    sb.table("subscription_events").insert({
        "user_id": user["id"],
        "event_type": "invoice.payment_failed",
        "from_plan": user["plan"],
        "to_plan": user["plan"],
        "metadata": {"invoice_id": invoice.get("id")},
    }).execute()


def _handle_payment_succeeded(invoice: dict) -> None:
    """Payment succeeded — record payment and confirm active status."""
    customer_id = invoice.get("customer")
    user = _find_user_by_customer(customer_id)
    if not user:
        return

    sb = get_supabase()
    sb.table("users").update({
        "subscription_status": "active",
    }).eq("id", user["id"]).execute()

    sb.table("payments").insert({
        "user_id": user["id"],
        "stripe_invoice_id": invoice.get("id"),
        "amount": invoice.get("amount_paid", 0),
        "currency": invoice.get("currency", "usd"),
        "status": "paid",
        "paid_at": datetime.now(UTC).isoformat(),
    }).execute()


def _extract_object(data: Any) -> dict:
    """Extract the event data object from either a dict or namespace."""
    if isinstance(data, dict):
        return data["object"]
    return data.object


def _on_checkout(data: Any) -> None:
    _handle_checkout_completed(_extract_object(data))


def _on_sub_updated(data: Any) -> None:
    _handle_subscription_updated(_extract_object(data))


def _on_sub_deleted(data: Any) -> None:
    _handle_subscription_deleted(_extract_object(data))


def _on_pay_failed(data: Any) -> None:
    _handle_payment_failed(_extract_object(data))


def _on_pay_succeeded(data: Any) -> None:
    _handle_payment_succeeded(_extract_object(data))


_HANDLERS: dict[str, Any] = {
    "checkout.session.completed": _on_checkout,
    "customer.subscription.updated": _on_sub_updated,
    "customer.subscription.deleted": _on_sub_deleted,
    "invoice.payment_failed": _on_pay_failed,
    "invoice.payment_succeeded": _on_pay_succeeded,
}


@router.post(
    "/stripe",
    status_code=200,
    summary="Stripe Webhook",
    description="Receives and processes Stripe webhook events.",
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
) -> dict[str, str]:
    payload = await request.body()
    event = _verify_signature(payload, stripe_signature)

    handler = _HANDLERS.get(event.type)
    if handler:
        handler(event.data)

    return {"status": "ok"}
