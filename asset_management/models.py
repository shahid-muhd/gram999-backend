from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from accounts.models import CustomUser


class PlatformOptions(models.Model):
    gold_margin = models.DecimalField(
        default=1.2, max_digits=10, decimal_places=3, verbose_name="Gold Margin (%)"
    )
    silver_margin = models.DecimalField(
        default=1.2, max_digits=10, decimal_places=3, verbose_name="Silver Margin (%)"
    )
    gold_markdown = models.DecimalField(
        default=1.7, max_digits=10, decimal_places=3, verbose_name="Gold Markdown (%)"
    )
    silver_markdown = models.DecimalField(
        default=1.7, max_digits=10, decimal_places=3, verbose_name="Silver Markdown (%)"
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


class PriceAlert(models.Model):
    CONDITION_CHOICES = [
        ("above", "Above"),
        ("below", "Below"),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    asset = models.CharField(max_length=20)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES)
    target_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_triggered = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "asset", "condition", "target_price"],
                condition=models.Q(is_triggered=False),
                name="unique_active_price_alert",
            )
        ]


class PushToken(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="push_tokens"
    )
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.token[:15]}"


from django.utils import timezone


class GoldLease(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("terminated", "Terminated"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # Gold leased from user's owned balance
    quantity = models.DecimalField(max_digits=18, decimal_places=4)

    # Lease duration
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField()

    # Lifecycle
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")

    # ✅ New field: total earnings from payouts
    earnings = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Lease({self.user}, {self.quantity}g, {self.status}, Earnings={self.earnings})"

    def mark_completed_if_expired(self):
        """Check if lease expired and update status"""
        if self.status == "active" and timezone.now().date() >= self.end_date:
            self.status = "completed"
            self.save(update_fields=["status", "updated_at"])
            return True
        return False


class LeasePayout(models.Model):
    lease = models.ForeignKey(
        GoldLease, related_name="payouts", on_delete=models.CASCADE
    )
    payout_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(
        max_digits=18, decimal_places=2, help_text="Payout in currency"
    )
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # ✅ Update earnings only when a new payout is created
        if is_new:
            self.lease.earnings += self.amount
            self.lease.save(update_fields=["earnings", "updated_at"])

    def __str__(self):
        return f"Payout({self.lease.user}, {self.amount} on {self.payout_date})"
