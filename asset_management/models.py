from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from accounts.models import CustomUser


class PlatformOptions(models.Model):
    gold_margin = models.DecimalField(
        default=0, max_digits=10, decimal_places=3, verbose_name="Gold Margin (%)"
    )
    silver_margin = models.DecimalField(
        default=0, max_digits=10, decimal_places=3, verbose_name="Silver Margin (%)"
    )
    gold_appreciation = models.DecimalField(
        max_digits=10, decimal_places=3, default=0, verbose_name="Gold Appreciation (%)"
    )
    silver_appreciation = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name="Silver Appreciation (%)",
    )

    def save(self, *args, **kwargs):
        self.id = 1  # Always force ID = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Platform Options"


class AssetLedger(models.Model):
    GOLD = "Gold"
    SILVER = "Silver"

    ASSET_CHOICES = [
        (GOLD, "Gold"),
        (SILVER, "Silver"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="asset_ledgers"
    )
    asset_type = models.CharField(max_length=100, choices=ASSET_CHOICES)
    quantity_owned = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    total_purchased_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    total_sold_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )

    class Meta:
        unique_together = ("user", "asset_type")  # One Gold + one Silver per user

    def __str__(self):
        return f"{self.user.username} - {self.asset_name} Ledger"


class AssetTransaction(models.Model):
    BUY = "BUY"
    SELL = "SELL"
    TRANSACTION_TYPES = [
        (BUY, "Buy"),
        (SELL, "Sell"),
    ]

    GOLD = "Gold"
    SILVER = "Silver"

    ASSET_CHOICES = [
        (GOLD, "Gold"),
        (SILVER, "Silver"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions"
    )
    transaction_type = models.CharField(max_length=4, choices=TRANSACTION_TYPES)
    asset_type = models.CharField(max_length=100, choices=ASSET_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    amount = models.DecimalField(max_digits=20, decimal_places=3)
    price_per_unit = models.DecimalField(
        max_digits=20, decimal_places=3, null=True, blank=True
    )
    transaction_id = models.CharField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    margin = models.IntegerField()

    def save(self, *args, **kwargs):
        if (
            not self.margin and self.transaction_type == self.BUY
        ):  # Set margin only if not already set (on create)
            try:
                options = PlatformOptions.objects.get(id=1)
                if self.asset_type == self.GOLD:
                    self.margin = options.gold_margin
                elif self.asset_type == self.SILVER:
                    self.margin = options.silver_margin
                else:
                    self.margin = 0  # default fallback
            except ObjectDoesNotExist:
                self.margin = 0  # fallback if no PlatformOptions record exists

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ledger.user.username} - {self.transaction_type} {self.quantity} {self.ledger.asset_name}"


class PriceAlert(models.Model):
    CONDITION_CHOICES = [
        ("above", "Above"),
        ("below", "Below"),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    asset = models.CharField(max_length=20)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES)
    target_price = models.DecimalField(max_digits=12, decimal_places=2)
    expo_push_token = models.CharField(max_length=200)
    is_triggered = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)


class PushToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="push_tokens")
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.token[:15]}"