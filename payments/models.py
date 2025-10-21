from django.conf import settings
from django.db import models



class AssetType(models.TextChoices):
    GOLD = "gold", "Gold"
    SILVER = "silver", "Silver"


class LeanCustomer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lean_customer_id = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"LeanCustomer({self.user}, {self.lean_customer_id})"


class LeanEntity(models.Model):
    lean_customer = models.ForeignKey(
        LeanCustomer, on_delete=models.CASCADE, related_name="entities"
    )
    entity_id = models.CharField(max_length=128, unique=True)
    provider = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"LeanEntity({self.entity_id} for {self.lean_customer.user})"


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





# --- SIP Plan ---
class SipFrequency(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"


class SipType(models.TextChoices):
    NORMAL = "normal", "Normal"
    GOAL = "goal", "Goal-based"


class SipPlan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    asset_type = models.CharField(max_length=16, choices=AssetType.choices)
    amount = models.DecimalField(
        max_digits=18, decimal_places=2, help_text="Investment amount in currency"
    )
    frequency = models.CharField(max_length=16, choices=SipFrequency.choices)
    type = models.CharField(
        max_length=16, choices=SipType.choices, default=SipType.NORMAL
    )

    # ✅ Normal SIP fields
    start_date = models.DateField()
    next_run = models.DateField()
    is_active = models.BooleanField(default=True)

    # ✅ Goal-based SIP fields
    target_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total target amount (investment + growth)",
    )
    end_date = models.DateField(null=True, blank=True)
    goal_name = models.CharField(max_length=128, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SipPlan({self.user}, {self.asset_type}, {self.amount}, {self.frequency}, {self.type})"




# --- Ledger for Gold & Silver ---




class LedgerEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    asset_type = models.CharField(max_length=16, choices=AssetType.choices)
    quantity = models.DecimalField(
        max_digits=18, decimal_places=4, help_text="Quantity of asset (grams)"
    )
    price_per_unit = models.DecimalField(
        max_digits=18, decimal_places=2, help_text="Price per gram at transaction time"
    )
    total_value = models.DecimalField(max_digits=18, decimal_places=2)
    transaction_type = models.CharField(
        max_length=16, choices=[("buy", "Buy"), ("sell", "Sell"), ("sip", "SIP")]
    )
    payment_intent = models.ForeignKey(
        PaymentIntent, on_delete=models.SET_NULL, null=True, blank=True
    )
    sip = models.ForeignKey(SipPlan, on_delete=models.SET_NULL, null=True, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ledger({self.user}, {self.asset_type}, {self.transaction_type}, {self.quantity}g)"

from django.db.models import Q, CheckConstraint, F

class Balance(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    gold_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    silver_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    leased_gold_quantity = models.DecimalField(
        max_digits=18, decimal_places=4, default=0
    )

    gold_invested_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    silver_invested_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(leased_gold_quantity__lte=F("gold_quantity")),
                name="leased_gold_lte_gold_quantity",
            )
        ]

    def __str__(self):
        return (
            f"Balance({self.user}, Gold={self.gold_quantity}g, Silver={self.silver_quantity}g, "
            f"Leased Gold={self.leased_gold_quantity}g, "
            f"Gold Invested={self.gold_invested_amount}, Silver Invested={self.silver_invested_amount})"
        )


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # Current balance in fiat (wallet money)
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet({self.user}, Balance={self.balance})"

    def deposit(self, amount, payment_intent=None, description="Deposit"):
        """Add money to wallet (user deposits or lease payouts)"""
        self.balance += amount
        self.save(update_fields=["balance", "updated_at"])
        WalletTransaction.objects.create(
            wallet=self,
            payment_intent=payment_intent,
            amount=amount,
            transaction_type="deposit",
            description=description,
        )

    def withdraw(self, amount, payment_intent, description="Withdraw"):
        """Withdraw money from wallet, linked to a PaymentIntent"""
        if amount > self.balance:
            raise ValueError("Insufficient wallet balance")
        self.balance -= amount
        self.save(update_fields=["balance", "updated_at"])
        WalletTransaction.objects.create(
            wallet=self,
            payment_intent=payment_intent,
            amount=amount,
            transaction_type="withdraw",
            description=description,
        )


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("deposit", "Deposit"),
        ("withdraw", "Withdraw"),
    ]
    DESCRIPTION_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("gold_purchase", "Gold Purchase"),
        ("gold_sellout", "Gold Sellout"),
        ("silver_purchase", "Silver Purchase"),
        ("silver_sellout", "Silver Sellout"),
        ("lease_payout", "Lease Payout"),
        ("lease_creation", "Lease Creation"),
        ("refund", "Refund"),
    ]

    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="transactions"
    )
    payment_intent = models.ForeignKey(
        "PaymentIntent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_transactions",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    transaction_type = models.CharField(max_length=16, choices=TRANSACTION_TYPES)
    description = models.CharField(
        max_length=32, choices=DESCRIPTION_CHOICES, default="other"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"WalletTransaction({self.wallet.user}, {self.transaction_type}, "
            f"{self.amount}, Intent={self.payment_intent_id})"
        )
