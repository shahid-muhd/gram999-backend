from .models import PriceAlert
from django.shortcuts import render
from rest_framework import serializers, viewsets
from .models import PriceAlert
from django.db import IntegrityError

# views.py
from rest_framework import generics, permissions, status
from .models import PlatformOptions
from .serializers import PlatformOptionsSerializer, BalanceRetrieveSerializer
from decimal import Decimal, InvalidOperation
from .serializers import (
    PriceAlertSerializer,
    PushTokenSerializer,
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from payments.models import Balance


class PlatformOptionsRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = PlatformOptionsSerializer

    def get_object(self):
        obj, created = PlatformOptions.objects.get_or_create(id=1)
        return obj

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            # Allow any authenticated user to read (GET, HEAD, OPTIONS)
            permission_classes = [permissions.IsAuthenticated]
        else:
            # Allow only admin users to update
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]


class PriceAlertViewSet(viewsets.ModelViewSet):
    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only retrieve alerts for the logged-in user that are not triggered
        return PriceAlert.objects.filter(user=self.request.user, is_triggered=False)

    def perform_create(self, serializer):
        user = self.request.user
        try:
            serializer.save(user=user)
        except IntegrityError:
            raise serializers.ValidationError(
                "You already have an active alert for this condition and price."
            )


from .models import PushToken


class PushTokenViewSet(viewsets.ModelViewSet):
    serializer_class = PushTokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PushToken.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        PushToken.objects.update_or_create(
            user=self.request.user,
            defaults={"token": serializer.validated_data["token"]},
        )


class BalanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BalanceRetrieveSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Balance.objects.all()
        return Balance.objects.filter(user=user)


from decimal import Decimal
import logging
from .utils import quantize_amount, get_price_per_gram
from payments.models import Wallet, LedgerEntry, Balance, AssetType

logger = logging.getLogger(__name__)


class BuyAssetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        POST payload:
        {
            "quantity": 5.0,
            "asset_type": "gold"
        }
        """
        user = request.user
        asset_type = request.data.get("asset_type", "gold").lower()
        quantity = request.data.get("quantity")

        if asset_type not in (AssetType.GOLD, AssetType.SILVER):
            return Response(
                {"error": "Invalid asset type"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Validate quantity
        try:
            quantity = Decimal(quantity)
            if quantity <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid quantity"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 1️⃣ Get wallet
        try:
            wallet = Wallet.objects.get(user=user)
        except Wallet.DoesNotExist:
            return Response(
                {"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # 2️⃣ Calculate total purchase value
        price_per_unit = get_price_per_gram(asset_type)
        total_value = quantize_amount(quantity * price_per_unit)

        # 3️⃣ Check wallet balance
        if wallet.balance < total_value:
            return Response(
                {"error": "Insufficient wallet balance"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Deduct wallet
        transaction_description = f"{asset_type}_purchase"
        wallet.withdraw(
            total_value, payment_intent=None, description=transaction_description
        )

        # 4️⃣ LedgerEntry
        LedgerEntry.objects.create(
            user=user,
            asset_type=asset_type,
            quantity=quantity,
            price_per_unit=price_per_unit,
            total_value=total_value,
            transaction_type="buy",
            payment_intent=None,
        )

        # 5️⃣ Update Balance
        bal, _ = Balance.objects.get_or_create(user=user)
        if asset_type == AssetType.GOLD:
            bal.gold_quantity = quantize_amount(bal.gold_quantity + quantity)
            bal.gold_invested_amount = (bal.gold_invested_amount or 0) + total_value
        else:
            bal.silver_quantity = quantize_amount(bal.silver_quantity + quantity)
            bal.silver_invested_amount = (bal.silver_invested_amount or 0) + total_value

        bal.save()

        logger.info(
            f"Wallet purchase successful: User={user}, Asset={asset_type}, Quantity={quantity}, Total={total_value}"
        )

        return Response(
            {
                "asset_type": asset_type,
                "quantity": quantity,
                "total_value": total_value,
                "wallet_balance": wallet.balance,
            },
            status=status.HTTP_200_OK,
        )


class SellAssetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        POST payload:
        {
            "asset_type": "gold",
            "quantity": 5.0
        }
        """
        user = request.user
        asset_type = request.data.get("asset_type", "gold").lower()
        quantity = request.data.get("quantity")

        if asset_type not in (AssetType.GOLD, AssetType.SILVER):
            return Response(
                {"error": "Invalid asset type"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            quantity = Decimal(str(quantity))
            if quantity <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {"error": "Invalid quantity"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 1️⃣ Get user's balance
        bal, _ = Balance.objects.get_or_create(user=user)
        if asset_type == AssetType.GOLD and bal.gold_quantity < quantity:
            return Response(
                {"error": "Insufficient gold balance"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif asset_type == AssetType.SILVER and bal.silver_quantity < quantity:
            return Response(
                {"error": "Insufficient silver balance"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2️⃣ Calculate sale value
        price_per_unit = get_price_per_gram(asset_type)
        total_value = quantize_amount(quantity * price_per_unit)

        # 3️⃣ Deduct from balance
        if asset_type == AssetType.GOLD:
            bal.gold_quantity = quantize_amount(bal.gold_quantity - quantity)
            bal.gold_invested_amount = max(
                (bal.gold_invested_amount or 0) - total_value, 0
            )
        else:
            bal.silver_quantity = quantize_amount(bal.silver_quantity - quantity)
            bal.silver_invested_amount = max(
                (bal.silver_invested_amount or 0) - total_value, 0
            )
        bal.save()

        # 4️⃣ Create LedgerEntry
        LedgerEntry.objects.create(
            user=user,
            asset_type=asset_type,
            quantity=quantity,
            price_per_unit=price_per_unit,
            total_value=total_value,
            transaction_type="sell",
            payment_intent=None,  # wallet sale
        )

        # 5️⃣ Credit wallet
        wallet, _ = Wallet.objects.get_or_create(user=user)
        transaction_description = f"{asset_type}_sellout"
        wallet.deposit(
            total_value, payment_intent=None, description=transaction_description
        )

        logger.info(
            f"Asset sold: User={user}, Asset={asset_type}, Quantity={quantity}, Credited={total_value}"
        )

        return Response(
            {
                "asset_type": asset_type,
                "quantity_sold": quantity,
                "credited_amount": total_value,
                "wallet_balance": wallet.balance,
            },
            status=status.HTTP_200_OK,
        )


from rest_framework.decorators import action
from payments.models import SipPlan, SipFrequency
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from .serializers import SipPlanSerializer
from .services import run_sip_plan
from django.db.models import Sum
from rest_framework.exceptions import ValidationError


class SipPlanViewSet(viewsets.ModelViewSet):
    serializer_class = SipPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        today = timezone.now().date()
        return SipPlan.objects.filter(
            user=self.request.user, end_date__isnull=True
        ) | SipPlan.objects.filter(user=self.request.user, end_date__gt=today)

    def perform_create(self, serializer):
        user = self.request.user
        today = timezone.now().date()
        sip_amount = serializer.validated_data["amount"]
        freq = serializer.validated_data["frequency"]

        # Check if wallet exists and has enough balance
        try:
            wallet = Wallet.objects.get(user=user)
        except Wallet.DoesNotExist:
            raise ValidationError("Wallet not found. Please add money first.")

        if wallet.balance < sip_amount:
            raise ValidationError(
                f"Insufficient wallet balance. You need AED{sip_amount}, "
           
            )

        # Calculate initial next_run
        if freq == SipFrequency.DAILY:
            next_run = today + timedelta(days=1)
        elif freq == SipFrequency.WEEKLY:
            next_run = today + timedelta(weeks=1)
        else:  # monthly
            next_run = today + timedelta(days=31)

        # Create SIP
        sip = serializer.save(
            user=user,
            next_run=next_run,
            start_date=today,
        )

        # Execute initial SIP transaction
        run_sip_plan(sip)
    

    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        sip = self.get_object()
        sip.is_active = False
        sip.save(update_fields=["is_active"])
        return Response({"status": "SIP disabled"})

    @action(detail=True, methods=["post"])
    def enable(self, request, pk=None):
        sip = self.get_object()
        sip.is_active = True
        sip.save(update_fields=["is_active"])
        return Response({"status": "SIP enabled"})

    @action(detail=True, methods=["post"])
    def terminate(self, request, pk=None):
        """Permanently terminate the SIP"""
        sip = self.get_object()
        sip.is_active = False
        sip.end_date = timezone.now().date()
        sip.save(update_fields=["is_active", "end_date"])
        return Response({"status": "SIP terminated"})

    @action(detail=True, methods=["post"])
    def run_now(self, request, pk=None):
        """Manually trigger SIP execution (useful for testing)"""
        sip = self.get_object()
        result = run_sip_plan(sip)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="details")
    def sip_details(self, request, pk=None):
        """
        Return full SIP details + last 5 ledger entries + total invested amount
        """
        sip = self.get_object()  # already ensures sip belongs to request.user

        # Last 5 ledger entries
        last_ledgers = (
            LedgerEntry.objects.filter(sip=sip)
            .order_by("-created_at")[:5]
            .values(
                "id",
                "asset_type",
                "quantity",
                "price_per_unit",
                "total_value",
                "transaction_type",
                "created_at",
            )
        )

        # Total invested in this SIP (sum of all ledger total_value)
        total_invested = (
            LedgerEntry.objects.filter(sip=sip, transaction_type="sip").aggregate(
                total=Sum("total_value")
            )["total"]
            or 0
        )

        # Serialize SIP
        sip_data = SipPlanSerializer(sip).data

        # Combine response
        response = {
            "sip": sip_data,
            "last_ledgers": list(last_ledgers),
            "total_invested": total_invested,
        }

        return Response(response)


from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from .models import GoldLease, LeasePayout
from .serializers import GoldLeaseSerializer, LeasePayoutSerializer
from decimal import Decimal


class GoldLeaseViewSet(viewsets.ModelViewSet):
    serializer_class = GoldLeaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GoldLease.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def release(self, request):
        release_qty = request.data.get("quantity")
        if release_qty is None:
            return Response({"error": "Quantity is required"}, status=400)

        release_qty = Decimal(str(release_qty))  # convert float to Decimal safely

        lease = GoldLease.objects.get(user=request.user, status="active")

        if release_qty > lease.quantity:
            return Response(
                {"error": "Release quantity cannot be more than leased quantity"},
                status=400,
            )

        lease.quantity -= release_qty
        lease.save(update_fields=["quantity", "updated_at"])

        # Update balance
        balance = Balance.objects.get(user=request.user)
        balance.leased_gold_quantity -= release_qty
        balance.save(update_fields=["leased_gold_quantity", "updated_at"])

        return Response({"status": f"Released {release_qty}g of gold from lease"})


class LeasePayoutViewSet(viewsets.ModelViewSet):
    serializer_class = LeasePayoutSerializer
    permission_classes = [permissions.IsAdminUser]  # Only company should create payouts

    def get_queryset(self):
        return LeasePayout.objects.all()

    def perform_create(self, serializer):
        payout = serializer.save()

        # ✅ Credit payout to wallet
        wallet, _ = Wallet.objects.get_or_create(user=payout.lease.user)
        wallet.deposit(payout.amount)
