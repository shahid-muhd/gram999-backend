# reports/views.py
from django.db.models import Sum, Avg
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from datetime import datetime
from decimal import Decimal
from payments.models import LedgerEntry  # adjust import path if needed


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
