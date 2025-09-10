import os
import json
import hmac
import hashlib
from decimal import Decimal, ROUND_DOWN
from datetime import date
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .models import LeanCustomer, PaymentIntent, PaymentDestination, LedgerEntry, Balance, SipPlan, AssetType
from .serializers import PaymentIntentSerializer
from .utils import lean_post
from .lean_auth import LeanCustomerToken

# ----- helper: price service -----
# Replace this with a real market price integration (e.g., metal APIs).
# For now it returns a mocked price per gram.
def get_price_per_gram(asset_type: str) -> Decimal:
    if asset_type == AssetType.GOLD:
        # example: 7000 AED per gram (replace with real feed)
        return Decimal('7000.00')
    if asset_type == AssetType.SILVER:
        return Decimal('90.00')
    raise ValueError('unknown asset')


def quantize_amount(d: Decimal) -> Decimal:
    return d.quantize(Decimal('0.0001'), rounding=ROUND_DOWN)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_customer_token(request):
    try:
        lean_customer = request.user.leancustomer
    except LeanCustomer.DoesNotExist:
        return Response({"error": "Lean customer not found"}, status=400)

    token = LeanCustomerToken.get_customer_token(lean_customer.lean_customer_id)
    return Response(token)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_lean_customer(request):
    user = request.user
    lc, _ = LeanCustomer.objects.get_or_create(user=user)
    if lc.lean_customer_id:
        return Response({'customer_id': lc.lean_customer_id})

    payload = {'app_user_id': f"user_{user.id}"}
    try:
        resp = lean_post('/customers/v1/', json=payload)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

    lc.lean_customer_id = resp.get('customer_id') or resp.get('id')
    lc.save()
    return Response({'customer_id': lc.lean_customer_id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment_intent(request):
    user = request.user
    lc = LeanCustomer.objects.filter(user=user).first()
    if not lc or not lc.lean_customer_id:
        return Response({'error': 'customer_not_found'}, status=400)

    amount = Decimal(str(request.data.get('amount')))
    currency = request.data.get('currency', 'AED')
    asset_type = request.data.get('asset_type', 'gold')
    description = request.data.get('description', '')

    payload = {
        'amount': float(amount),
        'currency': currency,
        'customer_id': lc.lean_customer_id,
        'description': description[:128],
    }

    try:
        resp = lean_post('/payments/v1/intents', json=payload)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

    payment_intent_id = (
        resp.get('payment_intent_id')
        or resp.get('intent_id')
        or resp.get('id')
    )

    p, _ = PaymentIntent.objects.update_or_create(
        payment_intent_id=payment_intent_id,
        defaults={
            'customer': lc,
            'amount': amount,
            'currency': currency,
            'status': resp.get('status', 'CREATED'),
            'metadata': resp,
        },
    )
    # store asset_type in metadata for later ledger creation
    p.metadata['asset_type'] = asset_type
    p.save()

    return Response({'payment_intent_id': payment_intent_id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_payment_sources(request):
    # Placeholder: you can implement a call to Lean to list payment sources for customer.
    lc = get_object_or_404(LeanCustomer, user=request.user)
    try:
        resp = lean_post(
            f"/customers/v1/{lc.lean_customer_id}/payment-sources/list",
            json={},
        )
    except Exception:
        resp = {}
    return Response(resp)


@csrf_exempt
def lean_webhook(request):
    body = request.body
    header_sig = (
        request.META.get('HTTP_LEAN_SIGNATURE')
        or request.headers.get('lean-signature')
    )
    if not header_sig:
        return Response(
            {'error': 'missing_signature'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    secret = os.getenv('LEAN_WEBHOOK_SECRET', '')
    computed = 'sha512=' + hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()

    if not hmac.compare_digest(computed, header_sig):
        return Response(
            {'error': 'invalid_signature'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = json.loads(body)
    event_type = data.get('type')
    payload = data.get('payload') or data

    # Handle payment events
    if event_type in (
        'payment.created',
        'payment.updated',
        'payment.succeeded',
        'payment.failed',
    ) or payload.get('event') in ('payment.created',):
        # Extract intent id and status
        intent_id = (
            payload.get('intent_id')
            or payload.get('payment_intent_id')
            or payload.get('id')
        )
        status_str = (
            payload.get('status')
            or payload.get('payment_status')
            or data.get('status')
        )
        try:
            pi = PaymentIntent.objects.get(payment_intent_id=intent_id)
            pi.status = status_str or pi.status
            pi.metadata.update(payload)
            pi.save()

            # If payment succeeded, create ledger entry and update balance
            if (status_str or '').upper() in ('SUCCEEDED', 'SUCCESS', 'COMPLETED'):
                # asset_type stored earlier in metadata
                asset_type = pi.metadata.get('asset_type', 'gold')
                price = get_price_per_gram(asset_type)
                quantity = quantize_amount(Decimal(pi.amount) / price)
                total_value = Decimal(pi.amount)
                tx_type = 'buy'  # for incoming payments, assume buy — change logic if needed

                LedgerEntry.objects.create(
                    user=pi.customer.user,
                    asset_type=asset_type,
                    quantity=quantity,
                    price_per_unit=price,
                    total_value=total_value,
                    transaction_type=tx_type,
                    payment_intent=pi,
                )

                # update Balance
                bal, _ = Balance.objects.get_or_create(user=pi.customer.user)
                if asset_type == AssetType.GOLD:
                    bal.gold_quantity = quantize_amount(bal.gold_quantity + quantity)
                else:
                    bal.silver_quantity = quantize_amount(bal.silver_quantity + quantity)
                bal.save()
        except PaymentIntent.DoesNotExist:
            # optionally log: unknown intent
            pass

    # Handle beneficiary / payment source events (e.g., beneficiary.created -> READY)
    if event_type in (
        'payment_source.beneficiary.created',
        'payment_source.beneficiary.updated',
    ):
        # update your records: map to LeanCustomer by customer_id
        customer_id = payload.get('customer_id')
        if customer_id:
            try:
                lc = LeanCustomer.objects.get(lean_customer_id=customer_id)
                # example: save payment sources or beneficiary status in lc.metadata if you add such field
            except LeanCustomer.DoesNotExist:
                pass

    # always 200
    return Response({'ok': True})


