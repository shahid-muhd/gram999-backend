from django.conf import settings
from django.db import models

class LeanCustomer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lean_customer_id = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"LeanCustomer({self.user}, {self.lean_customer_id})"

class PaymentDestination(models.Model):
    destination_id = models.CharField(max_length=128, primary_key=True)
    display_name = models.CharField(max_length=128)
    iban = models.CharField(max_length=64, blank=True, null=True)
    swift = models.CharField(max_length=32, blank=True, null=True)

class PaymentIntent(models.Model):
    payment_intent_id = models.CharField(max_length=128, primary_key=True)
    customer = models.ForeignKey(LeanCustomer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=8)
    status = models.CharField(max_length=64, default="CREATED")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Intent({self.payment_intent_id}, {self.amount} {self.currency})"

# --- Ledger for Gold & Silver ---

class AssetType(models.TextChoices):
    GOLD = "gold", "Gold"
    SILVER = "silver", "Silver"

class LedgerEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    asset_type = models.CharField(max_length=16, choices=AssetType.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, help_text="Quantity of asset (grams)")
    price_per_unit = models.DecimalField(max_digits=18, decimal_places=2, help_text="Price per gram at transaction time")
    total_value = models.DecimalField(max_digits=18, decimal_places=2)
    transaction_type = models.CharField(max_length=16, choices=[("buy", "Buy"), ("sell", "Sell"), ("sip", "SIP")])
    payment_intent = models.ForeignKey(PaymentIntent, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ledger({self.user}, {self.asset_type}, {self.transaction_type}, {self.quantity}g)"

class Balance(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    gold_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    silver_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Balance({self.user}, Gold={self.gold_quantity}g, Silver={self.silver_quantity}g)"

# --- SIP Plan ---

class SipFrequency(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"

class SipPlan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    asset_type = models.CharField(max_length=16, choices=AssetType.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2, help_text="Investment amount in currency")
    frequency = models.CharField(max_length=16, choices=SipFrequency.choices)
    start_date = models.DateField()
    next_run = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SipPlan({self.user}, {self.asset_type}, {self.amount}, {self.frequency})"