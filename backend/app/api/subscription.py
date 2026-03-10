"""Subscription API — Stripe Checkout, webhooks, and customer portal."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import stripe

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.models import User, UserTier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["subscription"])
settings = get_settings()

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Map Stripe Price IDs → tiers
PRICE_TO_TIER = {}
if settings.STRIPE_PRO_PRICE_ID:
    PRICE_TO_TIER[settings.STRIPE_PRO_PRICE_ID] = UserTier.PRO
if settings.STRIPE_ENTERPRISE_PRICE_ID:
    PRICE_TO_TIER[settings.STRIPE_ENTERPRISE_PRICE_ID] = UserTier.ENTERPRISE

TIER_TO_PRICE = {v: k for k, v in PRICE_TO_TIER.items()}


# ── Tier guard dependency (used by other modules) ──

TIER_ORDER = {UserTier.FREE: 0, UserTier.PRO: 1, UserTier.ENTERPRISE: 2}


def require_tier(min_tier: UserTier):
    """Dependency factory: reject requests from users below min_tier."""

    async def _check(
        user_id: str = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
    ):
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_level = TIER_ORDER.get(user.tier, 0)
        required_level = TIER_ORDER.get(min_tier, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires a {min_tier.value.upper()} subscription. "
                       f"Your current plan: {user.tier.value.upper()}.",
            )
        return user

    return _check


# ── Schemas ──

class SubscriptionStatus(BaseModel):
    tier: str
    expires_at: Optional[datetime]
    features: list[str]
    has_payment_method: bool = False
    stripe_subscription_id: Optional[str] = None

    class Config:
        from_attributes = True


class CheckoutRequest(BaseModel):
    target_tier: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class UpgradeRequest(BaseModel):
    target_tier: str


# ── Feature lists ──

TIER_FEATURES = {
    "free": [
        "LLM Cost Calculator",
        "Multi-cloud comparison",
        "API provider comparison",
        "Model browsing",
    ],
    "pro": [
        "Everything in Free",
        "No-code Model Builder",
        "LoRA adapter support",
        "Model merging (SLERP, TIES, DARE)",
        "Quantization configuration",
        "Self-deploy wizard (IaC generation)",
        "ZIP config bundle download",
        "Version history",
    ],
    "enterprise": [
        "Everything in Pro",
        "Managed cloud deployment",
        "Cloud credential management",
        "Auto-scaling",
        "Monitoring dashboard",
        "Cost alerts & budgets",
        "Priority support",
    ],
}


# ── Helpers ──

async def _get_or_create_stripe_customer(user: User, db: AsyncSession) -> str:
    """Get existing Stripe customer or create one."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        name=user.full_name or user.email,
        metadata={"user_id": user.id},
    )
    user.stripe_customer_id = customer.id
    await db.flush()
    return customer.id


def _is_stripe_configured() -> bool:
    """Check if Stripe keys are properly configured."""
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRO_PRICE_ID)


# ── Endpoints ──

@router.get("/status", response_model=SubscriptionStatus)
async def get_subscription_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tier_name = user.tier.value if user.tier else "free"
    return SubscriptionStatus(
        tier=tier_name,
        expires_at=user.subscription_expires_at,
        features=TIER_FEATURES.get(tier_name, TIER_FEATURES["free"]),
        has_payment_method=bool(user.stripe_subscription_id),
        stripe_subscription_id=user.stripe_subscription_id,
    )


@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    req: CheckoutRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for subscription upgrade."""
    if not _is_stripe_configured():
        raise HTTPException(status_code=503, detail="Payment system not configured. Contact admin.")

    target = req.target_tier.lower()
    target_tier = UserTier.PRO if target == "pro" else UserTier.ENTERPRISE if target == "enterprise" else None
    if not target_tier:
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'pro' or 'enterprise'.")

    price_id = TIER_TO_PRICE.get(target_tier)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"No Stripe price configured for {target} tier.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Don't allow checkout if already on same or higher tier
    if TIER_ORDER.get(user.tier, 0) >= TIER_ORDER.get(target_tier, 0):
        raise HTTPException(status_code=400, detail=f"Already on {user.tier.value.upper()} or higher.")

    customer_id = await _get_or_create_stripe_customer(user, db)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/subscription/cancel",
        metadata={"user_id": user.id, "target_tier": target},
        allow_promotion_codes=True,
        billing_address_collection="auto",
    )

    return CheckoutResponse(checkout_url=session.url)


@router.post("/create-portal", response_model=PortalResponse)
async def create_portal_session(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Customer Portal session for managing subscription."""
    if not _is_stripe_configured():
        raise HTTPException(status_code=503, detail="Payment system not configured.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found. Subscribe first.")

    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/pricing",
    )

    return PortalResponse(portal_url=session.url)


@router.post("/upgrade")
async def upgrade_subscription(
    req: UpgradeRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Upgrade tier. With Stripe configured, redirects to checkout.
    Without Stripe (dev mode), directly upgrades the tier."""
    target = req.target_tier.lower()
    if target not in ("pro", "enterprise"):
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'pro' or 'enterprise'.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # If Stripe is configured, require checkout flow
    if _is_stripe_configured():
        raise HTTPException(
            status_code=400,
            detail="Use /subscription/create-checkout for paid upgrades.",
        )

    # Dev mode: direct upgrade (no payment)
    user.tier = UserTier(target)
    await db.flush()

    tier_name = user.tier.value
    return {
        "message": f"Upgraded to {tier_name.upper()} plan (dev mode).",
        "tier": tier_name,
        "features": TIER_FEATURES.get(tier_name, []),
    }


# ── Stripe Webhook ──

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events. This endpoint is unauthenticated —
    Stripe sends events directly. We verify the signature instead."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET,
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    else:
        # Dev mode: parse without signature verification
        import json
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, db)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, db)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data, db)

    return {"status": "ok"}


async def _handle_checkout_completed(session: dict, db: AsyncSession):
    """A checkout session completed — activate the subscription."""
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    user_id = session.get("metadata", {}).get("user_id")
    target_tier = session.get("metadata", {}).get("target_tier")

    if not user_id or not target_tier:
        logger.warning("Checkout completed but missing metadata")
        return

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        logger.warning(f"User {user_id} not found for checkout")
        return

    user.tier = UserTier(target_tier)
    user.stripe_customer_id = customer_id
    user.stripe_subscription_id = subscription_id

    # Get subscription details for expiry
    if subscription_id:
        sub = stripe.Subscription.retrieve(subscription_id)
        user.subscription_expires_at = datetime.fromtimestamp(
            sub.current_period_end, tz=timezone.utc
        )

    await db.flush()
    logger.info(f"User {user_id} upgraded to {target_tier} via checkout")


async def _handle_subscription_updated(subscription: dict, db: AsyncSession):
    """Subscription updated — could be plan change, renewal, etc."""
    sub_id = subscription.get("id")
    customer_id = subscription.get("customer")
    status_val = subscription.get("status")

    result = await db.execute(
        select(User).where(User.stripe_subscription_id == sub_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        # Try by customer ID
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
    if not user:
        logger.warning(f"No user found for subscription {sub_id}")
        return

    user.stripe_subscription_id = sub_id

    if status_val in ("active", "trialing"):
        # Determine tier from price
        items = subscription.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            new_tier = PRICE_TO_TIER.get(price_id)
            if new_tier:
                user.tier = new_tier

        user.subscription_expires_at = datetime.fromtimestamp(
            subscription["current_period_end"], tz=timezone.utc
        )
    elif status_val in ("past_due", "unpaid"):
        logger.warning(f"Subscription {sub_id} is {status_val}")
    elif status_val == "canceled":
        user.tier = UserTier.FREE
        user.stripe_subscription_id = None
        user.subscription_expires_at = None

    await db.flush()
    logger.info(f"Subscription {sub_id} updated: status={status_val}, tier={user.tier.value}")


async def _handle_subscription_deleted(subscription: dict, db: AsyncSession):
    """Subscription canceled/deleted — downgrade to free."""
    sub_id = subscription.get("id")

    result = await db.execute(
        select(User).where(User.stripe_subscription_id == sub_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    user.tier = UserTier.FREE
    user.stripe_subscription_id = None
    user.subscription_expires_at = None
    await db.flush()
    logger.info(f"Subscription {sub_id} deleted, user downgraded to FREE")


async def _handle_payment_failed(invoice: dict, db: AsyncSession):
    """Payment failed — log warning, Stripe will retry."""
    customer_id = invoice.get("customer")
    sub_id = invoice.get("subscription")
    logger.warning(f"Payment failed for customer {customer_id}, subscription {sub_id}")
