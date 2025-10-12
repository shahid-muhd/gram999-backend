from django.utils import timezone
from django.db.models import Sum

# serializers.py
from rest_framework import serializers
from .models import (
    PlatformOptions,
    PriceAlert,
    GoldLease,
    LeasePayout,
    PushToken,
)

from payments.models import Balance
from dateutil.relativedelta import relativedelta


class PlatformOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformOptions
        fields = "__all__"


class PriceAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceAlert
        fields = ["id", "asset", "condition", "target_price", "is_triggered"]
        read_only_fields = ["id", "is_triggered"]


class PushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushToken
        fields = "__all__"
        read_only_fields = ["user", "created_at"]


class BalanceRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balance
        fields = "__all__"
        read_only_fields = (
            "id",
            "user",
            "gold_quantity",
            "silver_quantity",
            "updated_at",
        )


from payments.models import SipPlan


class SipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SipPlan
        fields = "__all__"
        read_only_fields = ("user", "created_at", "next_run", "is_active", "start_date")

    def validate(self, data):
        print("data>>>", data)
        if data["type"] == "goal":
            if not data.get("target_amount") and not data.get("end_date"):
                raise serializers.ValidationError(
                    "Goal-based SIP must have either target_amount or end_date."
                )
        return data


class LeasePayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeasePayout
        fields = "__all__"
        read_only_fields = ("lease", "created_at")


class GoldLeaseSerializer(serializers.ModelSerializer):
    # 👇 only for input, not stored in DB
    leasePeriod = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = GoldLease
        fields = "__all__"
        read_only_fields = ("user", "status", "created_at", "start_date", "end_date")

    def create(self, validated_data):
        user = self.context["request"].user
        lease_period = validated_data.pop("leasePeriod")  # in years

        start_date = timezone.now().date()
        end_date = start_date + relativedelta(years=lease_period)

        # ✅ Balance check
        balance = Balance.objects.get(user=user)
        total_owned = balance.gold_quantity

        leased_out = (
            GoldLease.objects.filter(user=user, status="active").aggregate(
                total=Sum("quantity")
            )["total"]
            or 0
        )
        available = total_owned - leased_out

        if validated_data["quantity"] > available:
            raise serializers.ValidationError(
                {"quantity": "Not enough gold available for leasing."}
            )

        # ✅ Check if user already has an active lease
        lease, created = GoldLease.objects.get_or_create(
            user=user,
            status="active",
            defaults={
                **validated_data,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        if not created:
            # If lease exists, update the quantity + extend end_date if needed
            lease.quantity += validated_data["quantity"]
            lease.end_date = max(lease.end_date, end_date)  # extend if longer
            lease.save(update_fields=["quantity", "end_date", "updated_at"])

        # ✅ Update leased_gold_quantity in Balance
        balance.leased_gold_quantity = leased_out + validated_data["quantity"]
        balance.save(update_fields=["leased_gold_quantity", "updated_at"])

        return lease
