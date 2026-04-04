"""
Stripe integration for Vessence Relay subscription ($5/month).
Requires STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET environment variables.
"""

import logging
import os

import stripe

log = logging.getLogger("relay.stripe")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def create_checkout_session(user_id: str, email: str) -> str:
    """Create a Stripe Checkout session for $5/month relay subscription."""
    if not stripe.api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not configured")

    session = stripe.checkout.Session.create(
        customer_email=email,
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Vessence Relay Service"},
                "unit_amount": 500,  # $5.00
                "recurring": {"interval": "month"},
            },
            "quantity": 1,
        }],
        mode="subscription",
        success_url="https://vessences.com/relay-success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://vessences.com/relay-cancel",
        metadata={"user_id": user_id},
    )
    return session.url


def verify_subscription(user_id: str) -> bool:
    """Check if user has an active relay subscription.

    For MVP, returns True as a placeholder. Full implementation would:
    1. Look up the Stripe customer by user_id metadata
    2. Check their subscription status
    3. Return True only if status is 'active' or 'trialing'
    """
    if not stripe.api_key:
        # No Stripe configured — allow access (development mode)
        return True
    # TODO: Query Stripe for customer subscription status by user_id
    return True


def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
    """Process a Stripe webhook event.

    Returns a dict with event type and relevant data.
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET not configured")

    event = stripe.Webhook.construct_event(
        payload, sig_header, STRIPE_WEBHOOK_SECRET
    )

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id", "")
        customer_id = data.get("customer", "")
        log.info("Checkout completed for user %s, customer %s", user_id, customer_id)
        return {
            "event": "subscription_created",
            "user_id": user_id,
            "customer_id": customer_id,
        }

    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer", "")
        log.info("Subscription cancelled for customer %s", customer_id)
        return {
            "event": "subscription_cancelled",
            "customer_id": customer_id,
        }

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer", "")
        log.warning("Payment failed for customer %s", customer_id)
        return {
            "event": "payment_failed",
            "customer_id": customer_id,
        }

    return {"event": event_type, "handled": False}
