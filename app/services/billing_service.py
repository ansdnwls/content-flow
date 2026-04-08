"""Stripe billing integration for subscription management."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.core.db import get_supabase
from app.core.stripe_client import stripe

PLAN_PRICE_MAP: dict[str, dict[str, str]] = {}


def _init_price_map() -> dict[str, dict[str, str]]:
    """Lazily build plan→price mapping from settings."""
    if PLAN_PRICE_MAP:
        return PLAN_PRICE_MAP
    s = get_settings()
    PLAN_PRICE_MAP.update({
        "build": {
            "monthly": s.stripe_price_build_monthly,
            "yearly": s.stripe_price_build_yearly,
        },
        "scale": {
            "monthly": s.stripe_price_scale_monthly,
            "yearly": s.stripe_price_scale_yearly,
        },
        "enterprise": {
            "monthly": s.stripe_price_enterprise_monthly,
            "yearly": s.stripe_price_enterprise_yearly,
        },
    })
    return PLAN_PRICE_MAP


def _get_stripe() -> None:
    """Configure the stripe module with the secret key."""
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key


def _resolve_price_id(plan: str, interval: str) -> str:
    prices = _init_price_map()
    plan_prices = prices.get(plan)
    if not plan_prices:
        msg = f"No Stripe price mapping for plan '{plan}'"
        raise ValueError(msg)
    price_id = plan_prices.get(interval)
    if not price_id:
        msg = f"No Stripe price for plan '{plan}' interval '{interval}'"
        raise ValueError(msg)
    return price_id


async def create_customer(user_id: str, email: str) -> str:
    """Create a Stripe customer and store the ID on the user row."""
    _get_stripe()
    customer = stripe.Customer.create(email=email, metadata={"user_id": user_id})

    sb = get_supabase()
    sb.table("users").update(
        {"stripe_customer_id": customer.id},
    ).eq("id", user_id).execute()

    return customer.id


async def _ensure_customer(user_id: str) -> str:
    """Return existing stripe_customer_id or create one."""
    sb = get_supabase()
    user = (
        sb.table("users")
        .select("stripe_customer_id, email")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]
    return await create_customer(user_id, user["email"])


async def create_checkout_session(
    user_id: str,
    plan: str,
    interval: str = "monthly",
) -> str:
    """Create a Stripe Checkout session and return its URL."""
    _get_stripe()
    customer_id = await _ensure_customer(user_id)
    price_id = _resolve_price_id(plan, interval)
    settings = get_settings()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
        metadata={"user_id": user_id, "plan": plan},
    )
    return session.url


async def create_portal_session(user_id: str) -> str:
    """Create a Stripe Customer Portal session and return its URL."""
    _get_stripe()
    customer_id = await _ensure_customer(user_id)
    session = stripe.billing_portal.Session.create(customer=customer_id)
    return session.url


async def get_subscription_status(user_id: str) -> dict[str, Any]:
    """Return current subscription info from DB."""
    sb = get_supabase()
    user = (
        sb.table("users")
        .select(
            "plan, subscription_status, stripe_subscription_id, "
            "current_period_end, cancel_at_period_end"
        )
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    return {
        "plan": user["plan"],
        "status": user.get("subscription_status") or "none",
        "subscription_id": user.get("stripe_subscription_id"),
        "current_period_end": user.get("current_period_end"),
        "cancel_at_period_end": user.get("cancel_at_period_end", False),
    }


async def cancel_subscription(user_id: str) -> dict[str, Any]:
    """Cancel subscription at period end."""
    _get_stripe()
    sb = get_supabase()
    user = (
        sb.table("users")
        .select("stripe_subscription_id, plan")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    sub_id = user.get("stripe_subscription_id")
    if not sub_id:
        return {"status": "no_subscription"}

    updated = stripe.Subscription.modify(sub_id, cancel_at_period_end=True)

    sb.table("users").update({
        "cancel_at_period_end": True,
    }).eq("id", user_id).execute()

    sb.table("subscription_events").insert({
        "user_id": user_id,
        "event_type": "subscription.cancel_requested",
        "from_plan": user["plan"],
        "to_plan": "free",
        "metadata": {"subscription_id": sub_id},
    }).execute()

    return {
        "status": updated.status,
        "cancel_at_period_end": True,
    }


async def change_plan(
    user_id: str,
    new_plan: str,
    interval: str = "monthly",
) -> dict[str, Any]:
    """Change the user's subscription to a different plan."""
    _get_stripe()
    sb = get_supabase()
    user = (
        sb.table("users")
        .select("stripe_subscription_id, plan")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    sub_id = user.get("stripe_subscription_id")
    if not sub_id:
        return {"error": "No active subscription. Create a checkout session first."}

    new_price_id = _resolve_price_id(new_plan, interval)
    subscription = stripe.Subscription.retrieve(sub_id)
    item_id = subscription["items"]["data"][0]["id"]

    updated = stripe.Subscription.modify(
        sub_id,
        items=[{"id": item_id, "price": new_price_id}],
        proration_behavior="create_prorations",
    )

    old_plan = user["plan"]
    sb.table("users").update({
        "plan": new_plan,
        "cancel_at_period_end": False,
    }).eq("id", user_id).execute()

    sb.table("subscription_events").insert({
        "user_id": user_id,
        "event_type": "subscription.plan_changed",
        "from_plan": old_plan,
        "to_plan": new_plan,
        "metadata": {"subscription_id": sub_id},
    }).execute()

    return {
        "status": updated.status,
        "plan": new_plan,
        "from_plan": old_plan,
    }
