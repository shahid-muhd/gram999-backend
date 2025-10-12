import logging
from ..models import (
    PaymentIntent,
    Wallet,
    LeanCustomer,
    LeanEntity,
    AssetType,
)
from decimal import Decimal, ROUND_DOWN
from asset_management.utils import get_price_per_gram

logger = logging.getLogger(__name__)


# def handle_payment_event(event_type, payload, data):
#     """Handle Lean payment.* events."""
#     intent_id = payload.get("intent_id") or payload.get("payment_intent_id")
#     status_str = payload.get("status") or payload.get("payment_status")
#     if not intent_id:
#         logger.warning("Payment event without intent_id: %s", payload)
#         return

#     try:
#         pi = PaymentIntent.objects.get(payment_intent_id=intent_id)
#         pi.status = status_str or pi.status
#         pi.metadata.update(payload)
#         pi.save()

#         print("payload incomming>>>", payload)
#         # If payment succeeded, create ledger entry and update balance
#         if (status_str or "").upper() in (
#             "SUCCESS",
#             "COMPLETED",
#             "ACCEPTED_BY_BANK",
#         ):
#             asset_type = pi.metadata.get("asset_type", "gold")
#             price = get_price_per_gram(asset_type)
#             quantity = quantize_amount(Decimal(pi.amount) / price)
#             total_value = Decimal(pi.amount)
#             tx_type = "buy"

#             LedgerEntry.objects.create(
#                 user=pi.customer.user,
#                 asset_type=asset_type,
#                 quantity=quantity,
#                 price_per_unit=price,
#                 total_value=total_value,
#                 transaction_type=tx_type,
#                 payment_intent=pi,
#             )

#             # update Balance
#             bal, _ = Balance.objects.get_or_create(user=pi.customer.user)
#             if asset_type == AssetType.GOLD:
#                 bal.gold_quantity = quantize_amount(bal.gold_quantity + quantity)
#                 bal.gold_invested_amount = (bal.gold_invested_amount or 0) + total_value
#             else:
#                 bal.silver_quantity = quantize_amount(bal.silver_quantity + quantity)
#                 bal.silver_invested_amount = (
#                     bal.silver_invested_amount or 0
#                 ) + total_value

#             bal.save()

#     except PaymentIntent.DoesNotExist:
#         logger.warning("Unknown PaymentIntent %s", intent_id)


def handle_payment_event(event_type, payload, data):
    """Handle Lean payment."""
    intent_id = payload.get("intent_id") or payload.get("payment_intent_id")
    status_str = payload.get("status") or payload.get("payment_status")

    if not intent_id:
        logger.warning("Payment event without intent_id: %s", payload)
        return

    try:
        pi = PaymentIntent.objects.get(payment_intent_id=intent_id)
        pi.status = status_str or pi.status
        pi.metadata.update(payload)
        pi.save()

        print("incoming payment payload >>>", payload)

        # If payment succeeded → update wallet
        if (status_str or "").upper() in ("SUCCESS", "COMPLETED", "ACCEPTED_BY_BANK"):
            wallet, _ = Wallet.objects.get_or_create(user=pi.customer.user)

            wallet.deposit(
                Decimal(pi.amount),
                payment_intent=pi,
                description="bank_transfer",
            )

    except PaymentIntent.DoesNotExist:
        logger.warning("Unknown PaymentIntent %s", intent_id)


def handle_payment_source_event(event_type, payload):
    """Handle Lean payment_source.* events."""
    customer_id = payload.get("customer_id")
    if not customer_id:
        return
    try:
        lc = LeanCustomer.objects.get(lean_customer_id=customer_id)
        # Extend: store beneficiary or payment source status if needed
        logger.info("Payment source update for %s", lc.user)
    except LeanCustomer.DoesNotExist:
        logger.warning("Payment source for unknown customer %s", customer_id)


def handle_entity_event(event_type, payload):
    """Handle Lean entity.* events."""
    print("payload enitiy >>", payload)
    if event_type == "entity.created":
        entity_id = payload.get("id")
        customer_id = payload.get("customer_id")

        if not (entity_id and customer_id):
            return

        try:
            lc = LeanCustomer.objects.get(lean_customer_id=customer_id)
            LeanEntity.objects.get_or_create(
                lean_customer=lc,
                entity_id=entity_id,
                defaults={
                    "provider": payload.get("bank_details", {}).get("name"),
                },
            )
            logger.info("Entity created for %s: %s", lc.user, entity_id)
        except LeanCustomer.DoesNotExist:
            logger.warning("Entity for unknown customer %s", customer_id)
