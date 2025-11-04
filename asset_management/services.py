from datetime import timedelta
from django.utils import timezone
from .utils import quantize_amount, get_price_per_gram
from payments.models import (
    Wallet,
    LedgerEntry,
    Balance,
    AssetType,
    SipPlan,
    SipFrequency,
    SipType,
)

from .models import PushToken
from .utils import send_push_notification
from asgiref.sync import async_to_sync
from dateutil.relativedelta import relativedelta

def run_sip_plan(sip: SipPlan,is_initial=False):
    user = sip.user
    try:
        wallet = Wallet.objects.get(user=user)
    except Wallet.DoesNotExist:
        return {"error": "Wallet not found"}

    # Check wallet balance
    if wallet.balance < sip.amount:
        # Fetch user push tokens
        tokens = list(
            PushToken.objects.filter(user=user).values_list("token", flat=True)
        )
        if tokens:
            # Send push notification asynchronously in sync context
            async_to_sync(send_push_notification)(
                tokens,
                title="SIP Failed",
                body=f"Your wallet balance is insufficient for {sip.asset_type} SIP of {sip.amount}.",
            )
        return {"error": "Insufficient wallet balance"}

    # Proceed with normal SIP execution
    price_per_unit = get_price_per_gram(sip.asset_type)['buy']
    quantity = quantize_amount(sip.amount / price_per_unit)

    # Deduct wallet
    transaction_description=f'{sip.asset_type}_purchase'
    wallet.withdraw(sip.amount, payment_intent=None,description=transaction_description)

    # Ledger entry
    LedgerEntry.objects.create(
        user=user,
        asset_type=sip.asset_type,
        quantity=quantity,
        price_per_unit=price_per_unit,
        total_value=sip.amount,
        transaction_type="sip",
        payment_intent=None,
        sip=sip,
    )

    # Update balance
    bal, _ = Balance.objects.get_or_create(user=user)
    if sip.asset_type == AssetType.GOLD:
        bal.gold_quantity = quantize_amount(bal.gold_quantity + quantity)
        bal.gold_invested_amount += sip.amount
    else:
        bal.silver_quantity = quantize_amount(bal.silver_quantity + quantity)
        bal.silver_invested_amount += sip.amount
    bal.save()

    # Update next_run
    if not is_initial:
        today = timezone.now().date()
        if sip.frequency == SipFrequency.DAILY:
            sip.next_run = today + timedelta(days=1)
        elif sip.frequency == SipFrequency.WEEKLY:
            sip.next_run = today + timedelta(weeks=1)
        elif sip.frequency == SipFrequency.MONTHLY:
            sip.next_run = today + relativedelta(months=1)

    # Goal-based SIP: check if goal reached
    if sip.type == SipType.GOAL:
        if (
            sip.target_amount
            and (bal.gold_invested_amount + bal.silver_invested_amount)
            >= sip.target_amount
        ):
            sip.is_active = False
        elif sip.end_date and today >= sip.end_date:
            sip.is_active = False

    sip.save(update_fields=["next_run", "is_active"])
    return {"success": True, "quantity": quantity, "amount": sip.amount}
