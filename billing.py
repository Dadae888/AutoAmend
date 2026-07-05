import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from db import get_session
from models import Device
from status import get_or_create_device

router = APIRouter()

stripe.api_key = settings.stripe_secret_key


class CheckoutRequest(BaseModel):
    device_id: str


@router.post("/api/checkout")
def create_checkout(body: CheckoutRequest, session: Session = Depends(get_session)) -> dict:
    if not settings.stripe_secret_key or not settings.stripe_price_id:
        raise HTTPException(status_code=503, detail="Payments are not configured yet.")

    get_or_create_device(session, body.device_id)

    checkout_session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        client_reference_id=body.device_id,
        success_url=f"{settings.public_app_url}/success",
        cancel_url=f"{settings.public_app_url}/cancel",
    )
    return {"url": checkout_session.url}


@router.get("/success", response_class=HTMLResponse)
def success_page() -> str:
    return (
        "<html><body style='font-family:sans-serif;text-align:center;padding:4rem'>"
        "<h1>Merci !</h1>"
        "<p>Votre abonnement AutoAmend AI Pro est en cours d'activation.</p>"
        "<p>Revenez dans l'application AutoAmend AI et cliquez sur "
        "<strong>&laquo;&nbsp;Rafraîchir mon statut&nbsp;&raquo;</strong>.</p>"
        "</body></html>"
    )


@router.get("/cancel", response_class=HTMLResponse)
def cancel_page() -> str:
    return (
        "<html><body style='font-family:sans-serif;text-align:center;padding:4rem'>"
        "<h1>Paiement annulé</h1>"
        "<p>Vous pouvez revenir dans AutoAmend AI et réessayer à tout moment.</p>"
        "</body></html>"
    )


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request, session: Session = Depends(get_session)) -> dict:
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Payments are not configured yet.")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {exc}") from exc

    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        device_id = obj.get("client_reference_id")
        customer_id = obj.get("customer")
        if device_id and customer_id:
            device = get_or_create_device(session, device_id)
            device.stripe_customer_id = customer_id
            device.subscription_status = "active"
            session.commit()

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_id = obj.get("customer")
        stripe_status = obj.get("status")  # active, past_due, canceled, ...
        device = session.scalar(select(Device).where(Device.stripe_customer_id == customer_id))
        if device is not None:
            device.subscription_status = (
                "canceled" if event_type == "customer.subscription.deleted" else stripe_status
            )
            session.commit()

    return {"received": True}
