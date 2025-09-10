# serializers.py
from rest_framework import serializers
from .models import PlatformOptions, AssetTransaction, AssetLedger , PriceAlert ,PushToken


class PlatformOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformOptions
        fields = "__all__"


class AssetTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetTransaction
        fields = "__all__"
        read_only_fields = ["timestamp"]

    def validate(self, data):
        """
        Prevent selling more than owned.
        """
        if data["transaction_type"] == AssetTransaction.SELL:
            ledger = AssetLedger.objects.filter(
                user=data["user"], asset_type=data["asset_type"]
            ).first()

            if not ledger:
                raise serializers.ValidationError("No ledger found for this asset.")
            if data["quantity"] > ledger.quantity_owned:
                raise serializers.ValidationError("Insufficient quantity to sell.")

        return data


class PriceAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceAlert
        fields = '__all__'
    

class PushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushToken
        fields = '__all__'