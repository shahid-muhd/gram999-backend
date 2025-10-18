from django.db.models import Sum, Avg
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from datetime import datetime
from decimal import Decimal
from payments.models import LedgerEntry, SipPlan, AssetType
from django.db.models import Count, Sum
from django.contrib.auth import get_user_model
from rest_framework import status


User = get_user_model()


class SalesSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        # --- optional date range filters ---
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        filters = {}
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
                filters["created_at__range"] = (start, end)
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
                )

        # --- function to calculate summary per asset type ---
        def get_asset_summary(asset_type):
            qs = LedgerEntry.objects.filter(asset_type=asset_type, **filters)

            # Total Bought
            bought = qs.filter(transaction_type="buy").aggregate(
                total_quantity=Sum("quantity"),
                total_value=Sum("total_value"),
                avg_price=Avg("price_per_unit"),
            )

            # Total Sold
            sold = qs.filter(transaction_type="sell").aggregate(
                total_quantity=Sum("quantity"),
                total_value=Sum("total_value"),
                avg_price=Avg("price_per_unit"),
            )

            # Profit/Loss Calculation
            avg_buy_price = bought["avg_price"] or Decimal(0)
            avg_sell_price = sold["avg_price"] or Decimal(0)
            total_sold_grams = sold["total_quantity"] or Decimal(0)

            profit_loss_per_gram = avg_sell_price - avg_buy_price
            total_profit_loss = profit_loss_per_gram * total_sold_grams

            # Total Transactions
            total_transactions = qs.filter(transaction_type__in=["buy", "sell"]).count()

            return {
                "total_bought": {
                    "grams": bought["total_quantity"] or Decimal(0),
                    "value": bought["total_value"] or Decimal(0),
                },
                "total_sold": {
                    "grams": sold["total_quantity"] or Decimal(0),
                    "value": sold["total_value"] or Decimal(0),
                },
                "profit_loss": {
                    "per_gram": round(profit_loss_per_gram, 2),
                    "total": round(total_profit_loss, 2),
                },
                "total_transactions": total_transactions,
            }

        # --- Build Response for both assets ---
        data = {
            "gold": get_asset_summary("gold"),
            "silver": get_asset_summary("silver"),
        }

        return Response(data)


class ActiveSIPPlansView(APIView):
    """
    Get all active SIP plans with user and plan details
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        active_sips = SipPlan.objects.filter(is_active=True).select_related("user")

        data = []
        for sip in active_sips:
            data.append(
                {
                    "id": sip.id,
                    "user_id": sip.user.id,
                    "username": sip.user.first_name + " " + sip.user.last_name,
                    "email": getattr(sip.user, "email", ""),
                    "asset_type": sip.get_asset_type_display(),
                    "amount": str(sip.amount),
                    "frequency": sip.get_frequency_display(),
                    "type": sip.get_type_display(),
                    "start_date": sip.start_date,
                    "next_run": sip.next_run,
                    "goal_name": sip.goal_name,
                    "target_amount": (
                        str(sip.target_amount) if sip.target_amount else None
                    ),
                    "end_date": sip.end_date,
                    "created_at": sip.created_at,
                }
            )

        return Response(
            {"count": len(data), "results": data}, status=status.HTTP_200_OK
        )


class SIPInstallmentHistoryView(APIView):
    """
    Get SIP installment history from ledger entries
    Optionally filter by user_id
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        user_id = request.query_params.get("user_id", None)

        # Base query for SIP transactions
        queryset = LedgerEntry.objects.filter(transaction_type="sip").select_related(
            "user", "payment_intent"
        )

        # Filter by user if provided
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Order by most recent first
        queryset = queryset.order_by("-created_at")

        data = []
        for entry in queryset:
            data.append(
                {
                    "id": entry.id,
                    "user_id": entry.user.id,
                    "username": entry.user.username,
                    "email": getattr(entry.user, "email", ""),
                    "asset_type": entry.get_asset_type_display(),
                    "quantity": str(entry.quantity),
                    "price_per_unit": str(entry.price_per_unit),
                    "total_value": str(entry.total_value),
                    "payment_intent_id": (
                        entry.payment_intent.payment_intent_id
                        if entry.payment_intent
                        else None
                    ),
                    "payment_status": (
                        entry.payment_intent.status if entry.payment_intent else None
                    ),
                    "created_at": entry.created_at,
                }
            )

        return Response(
            {"count": len(data), "user_id": user_id, "results": data},
            status=status.HTTP_200_OK,
        )


class SIPOverviewView(APIView):
    """
    Get basic SIP overview statistics:
    - Total active SIP users
    - Total gold accumulated via SIP
    - Total silver accumulated via SIP
    - Total active SIP plans
    - Total SIP investment amount
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        # Total active SIP plans
        active_sips_count = SipPlan.objects.filter(is_active=True).count()

        # Total unique users with active SIPs
        active_sip_users = (
            SipPlan.objects.filter(is_active=True).values("user").distinct().count()
        )

        # Gold accumulated via SIP
        gold_sip_data = LedgerEntry.objects.filter(
            transaction_type="sip", asset_type=AssetType.GOLD
        ).aggregate(total_quantity=Sum("quantity"), total_value=Sum("total_value"))

        # Silver accumulated via SIP
        silver_sip_data = LedgerEntry.objects.filter(
            transaction_type="sip", asset_type=AssetType.SILVER
        ).aggregate(total_quantity=Sum("quantity"), total_value=Sum("total_value"))

        # Breakdown by SIP type
        sip_type_breakdown = (
            SipPlan.objects.filter(is_active=True)
            .values("type")
            .annotate(count=Count("id"))
        )

        # Breakdown by frequency
        sip_frequency_breakdown = (
            SipPlan.objects.filter(is_active=True)
            .values("frequency")
            .annotate(count=Count("id"))
        )

        return Response(
            {
                "active_sip_plans": active_sips_count,
                "active_sip_users": active_sip_users,
                "gold_accumulated": {
                    "quantity_grams": str(
                        gold_sip_data["total_quantity"] or Decimal("0")
                    ),
                    "total_investment": str(
                        gold_sip_data["total_value"] or Decimal("0")
                    ),
                },
                "silver_accumulated": {
                    "quantity_grams": str(
                        silver_sip_data["total_quantity"] or Decimal("0")
                    ),
                    "total_investment": str(
                        silver_sip_data["total_value"] or Decimal("0")
                    ),
                },
                "sip_type_breakdown": list(sip_type_breakdown),
                "sip_frequency_breakdown": list(sip_frequency_breakdown),
            },
            status=status.HTTP_200_OK,
        )


class UserSIPDetailsView(APIView):
    """
    Get detailed SIP information for a specific user
    """

    permission_classes = [IsAdminUser]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # User's active SIPs
        active_sips = SipPlan.objects.filter(user_id=user_id, is_active=True)
        sip_data = []
        for sip in active_sips:
            sip_data.append(
                {
                    "id": sip.id,
                    "asset_type": sip.get_asset_type_display(),
                    "amount": str(sip.amount),
                    "frequency": sip.get_frequency_display(),
                    "type": sip.get_type_display(),
                    "start_date": sip.start_date,
                    "next_run": sip.next_run,
                    "goal_name": sip.goal_name,
                    "target_amount": (
                        str(sip.target_amount) if sip.target_amount else None
                    ),
                    "end_date": sip.end_date,
                }
            )

        # SIP transaction history
        sip_transactions = LedgerEntry.objects.filter(
            user_id=user_id, transaction_type="sip"
        ).order_by("-created_at")

        transaction_data = []
        for entry in sip_transactions:
            transaction_data.append(
                {
                    "id": entry.id,
                    "asset_type": entry.get_asset_type_display(),
                    "quantity": str(entry.quantity),
                    "price_per_unit": str(entry.price_per_unit),
                    "total_value": str(entry.total_value),
                    "created_at": entry.created_at,
                }
            )

        # Aggregate stats
        gold_stats = LedgerEntry.objects.filter(
            user_id=user_id, transaction_type="sip", asset_type=AssetType.GOLD
        ).aggregate(
            total_quantity=Sum("quantity"),
            total_value=Sum("total_value"),
            count=Count("id"),
        )

        silver_stats = LedgerEntry.objects.filter(
            user_id=user_id, transaction_type="sip", asset_type=AssetType.SILVER
        ).aggregate(
            total_quantity=Sum("quantity"),
            total_value=Sum("total_value"),
            count=Count("id"),
        )

        return Response(
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": getattr(user, "email", ""),
                },
                "active_sips": sip_data,
                "total_sip_installments": len(transaction_data),
                "gold_stats": {
                    "total_quantity": str(gold_stats["total_quantity"] or Decimal("0")),
                    "total_invested": str(gold_stats["total_value"] or Decimal("0")),
                    "installments_count": gold_stats["count"],
                },
                "silver_stats": {
                    "total_quantity": str(
                        silver_stats["total_quantity"] or Decimal("0")
                    ),
                    "total_invested": str(silver_stats["total_value"] or Decimal("0")),
                    "installments_count": silver_stats["count"],
                },
                "recent_transactions": transaction_data[:10],  # Last 10 transactions
            },
            status=status.HTTP_200_OK,
        )
