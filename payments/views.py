import os
import json
import hmac
import hashlib
from decimal import Decimal
from datetime import date
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from accounts.models import CustomUser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .models import Wallet, WalletTransaction
from .models import (
    LeanCustomer,
    PaymentIntent,
)

from .utils.lean_requests import lean_post
from .lean_auth import LeanCustomerToken
from django.http import JsonResponse


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_customer_token(request):
    try:
        lean_customer = request.user.leancustomer
    except LeanCustomer.DoesNotExist:
        return Response({"error": "Lean customer not found"}, status=400)

    token = LeanCustomerToken.get_customer_token(lean_customer.lean_customer_id)
    return Response(token)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_lean_customer(request):
    user = request.user
    lc, _ = LeanCustomer.objects.get_or_create(user=user)
    if lc.lean_customer_id:
        return Response({"customer_id": lc.lean_customer_id})

    payload = {"app_user_id": f"user_{user.id}"}
    try:
        resp = lean_post("/customers/v1/", json=payload)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

    lc.lean_customer_id = resp.get("customer_id") or resp.get("id")
    lc.save()
    return Response({"customer_id": lc.lean_customer_id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_payment_intent(request):
    user = request.user

    if user.kyc_status != "accepted":
        return Response({"error": "Customer KYC not verified."}, status=403)

    lc = LeanCustomer.objects.filter(user=user).first()
    if not lc or not lc.lean_customer_id:
        return Response({"error": "customer_not_found"}, status=400)

    amount = Decimal(str(request.data.get("amount")))
    currency = request.data.get("currency", "AED")
    asset_type = request.data.get("asset_type", "gold")
    description = request.data.get("description", "sample payment")

    payload = {
        "amount": float(amount),
        "currency": currency,
        "customer_id": lc.lean_customer_id,
        "payment_destination_id": "e575dab0-bf79-423c-a90e-a008215e8438",
        "description": description[:32],
    }

    try:
        response = lean_post("/payments/v1/intents", json=payload)
    except Exception as e:
        print("Error while creating payment intent:", e)
        return Response({"error": str(e)}, status=500)

    payment_intent_id = (
        response.get("payment_intent_id")
        or response.get("intent_id")
        or response.get("id")
    )

    p, _ = PaymentIntent.objects.update_or_create(
        payment_intent_id=payment_intent_id,
        defaults={
            "customer": lc,
            "amount": amount,
            "currency": currency,
            "status": response.get("status", "CREATED"),
            "metadata": response,
        },
    )
    # store asset_type in metadata for later ledger creation
    p.metadata["asset_type"] = asset_type
    p.save()

    return Response({"payment_intent_id": payment_intent_id})


@api_view(["GET"])
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


from .utils.lean_client import lean_get_accounts


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bank_accounts(request):
    user = request.user
    try:
        lc = LeanCustomer.objects.get(user=user)
    except LeanCustomer.DoesNotExist:
        return JsonResponse({"accounts": []})

    accounts = []
    for entity in lc.entities.all():
        try:
            lean_accounts = lean_get_accounts(entity.entity_id)
            for acc in lean_accounts:
                acc["provider"] = entity.provider
            accounts.extend(lean_accounts)
            print("lean accounts >>>", lean_accounts)
        except Exception as e:
            # log error and continue
            print(f"Error fetching accounts for {entity.entity_id}: {e}")

    return JsonResponse({"accounts": accounts})


from .utils.lean_webhook_handles import (
    handle_payment_event,
    handle_payment_source_event,
    handle_entity_event,
)


@csrf_exempt
def lean_webhook(request):
    body = request.body
    header_sig = request.META.get("HTTP_LEAN_SIGNATURE") or request.headers.get(
        "lean-signature"
    )
    if not header_sig:
        return JsonResponse({"error": "missing_signature"}, status=400)

    secret = os.getenv("LEAN_WEBHOOK_SECRET", "")
    computed = "sha512=" + hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()

    if not hmac.compare_digest(computed, header_sig):
        return JsonResponse({"error": "invalid_signature"}, status=400)

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    event_type = data.get("type")
    payload = data.get("payload") or data

    # Dispatch by category
    if event_type.startswith("payment."):
        handle_payment_event(event_type, payload, data)
    elif event_type.startswith("payment_source."):
        handle_payment_source_event(event_type, payload)
    elif event_type.startswith("entity."):
        handle_entity_event(event_type, payload)
    else:
        # Optional: log unsupported events
        print(f"Unhandled Lean event: {event_type}")

    return JsonResponse({"status": "ok"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_wallet(request):
    """
    Get wallet details of the authenticated user.
    Admins can optionally specify ?user_id=<id> to view another user's wallet.
    """
    user = request.user
    user_id = request.query_params.get("user_id")

    #  Allow admins to view any user's wallet
    if user.is_staff and user_id:
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )

    wallet, _ = Wallet.objects.get_or_create(user=user)
    return Response(
        {"user_id": user.id, "wallet_balance": wallet.balance},
        status=status.HTTP_200_OK,
    )


from rest_framework.settings import api_settings 

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_wallet_transactions(request):
    """
    Get wallet transactions for the authenticated user.
    Admins can use ?user_id=<id> to fetch another user's transactions.
    Uses global pagination settings.
    """
    user = request.user
    user_id = request.query_params.get("user_id")

    if user.is_staff and user_id:
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )

    wallet, _ = Wallet.objects.get_or_create(user=user)

    queryset = WalletTransaction.objects.filter(wallet=wallet).order_by("-created_at")

    # ✅ Use the global pagination class from DRF settings
    paginator_class = api_settings.DEFAULT_PAGINATION_CLASS
    paginator = paginator_class()

    # Paginate queryset (respects ?page= query param)
    page = paginator.paginate_queryset(queryset, request)

    data = [
        {
            "id": tx.id,
            "amount": tx.amount,
            "type": tx.transaction_type,
            "payment_intent_id": (
                tx.payment_intent.payment_intent_id if tx.payment_intent else None
            ),
            "created_at": tx.created_at,
            "description": tx.get_description_display(),
        }
        for tx in page
    ]

    # ✅ Return paginated response using global pagination format
    return paginator.get_paginated_response(data)

from rest_framework import viewsets, permissions
from .models import LedgerEntry
from .serializers import LedgerEntrySerializer
from ecommerce.models import Order
from ecommerce.serializers import OrderListSerializer
class UserLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Returns combined ledger entries and orders for the logged-in user.
    """
    serializer_class = LedgerEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return LedgerEntry.objects.filter(user=user).order_by("-created_at")
    
    def list(self, request, *args, **kwargs):
        # Get ledger entries
        ledger_queryset = self.get_queryset()
        ledger_serializer = LedgerEntrySerializer(ledger_queryset, many=True)
        
        # Get orders
        orders_queryset = Order.objects.filter(user=request.user).order_by("-created_at")
        orders_serializer = OrderListSerializer(orders_queryset, many=True)
        
        # Combine both lists
        combined_data = ledger_serializer.data + orders_serializer.data
        
        # Sort by created_at in descending order
        combined_data.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Paginate if needed
        page = self.paginate_queryset(combined_data)
        if page is not None:
            return self.get_paginated_response(page)
        
        return Response(combined_data)
    
    def retrieve(self, request, *args, **kwargs):
        # Try to get from ledger first
        try:
            ledger_entry = LedgerEntry.objects.get(
                id=kwargs['pk'], 
                user=request.user
            )
            serializer = LedgerEntrySerializer(ledger_entry)
            return Response(serializer.data)
        except LedgerEntry.DoesNotExist:
            pass
        
        # If not found in ledger, try orders
        try:
            order = Order.objects.get(
                id=kwargs['pk'], 
                user=request.user
            )
            serializer = OrderListSerializer(order)
            return Response(serializer.data)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )