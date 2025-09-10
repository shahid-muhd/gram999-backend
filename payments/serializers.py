from rest_framework import serializers
from .models import LeanCustomer, PaymentIntent, LedgerEntry, Balance, SipPlan


class LeanCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeanCustomer
        fields = ["lean_customer_id"]


class PaymentIntentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentIntent
        fields = ["payment_intent_id", "amount", "currency", "status", "created_at"]


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = "__all__"


class BalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balance
        fields = ["gold_quantity", "silver_quantity", "updated_at"]


class SIPPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SipPlan
        fields = "__all__"
