from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import AssetTransaction, AssetLedger


@receiver(pre_save, sender=AssetTransaction)
def store_old_transaction_values(sender, instance, **kwargs):
    """
    Before saving, store the old transaction data for comparison in post_save.
    """
    if instance.pk:  # If updating existing transaction
        old_instance = AssetTransaction.objects.get(pk=instance.pk)
        instance._old_transaction_type = old_instance.transaction_type
        instance._old_quantity = old_instance.quantity
    else:
        instance._old_transaction_type = None
        instance._old_quantity = None


@receiver(post_save, sender=AssetTransaction)
def update_ledger_after_transaction(sender, instance, created, **kwargs):
    """
    After saving, update or create the ledger for the transaction's user & asset.
    Handles both creation and update without double counting.
    """
    # Get or create the ledger
    ledger, _ = AssetLedger.objects.get_or_create(
        user=instance.user,
        asset_type=instance.asset_type,
        defaults={
            "quantity_owned": 0,
            "total_purchased_quantity": 0,
            "total_sold_quantity": 0
        }
    )

    # If updating, reverse the effect of the old transaction first
    if not created and instance._old_transaction_type:
        if instance._old_transaction_type == AssetTransaction.BUY:
            ledger.quantity_owned -= instance._old_quantity
            ledger.total_purchased_quantity -= instance._old_quantity
        elif instance._old_transaction_type == AssetTransaction.SELL:
            ledger.quantity_owned += instance._old_quantity
            ledger.total_sold_quantity -= instance._old_quantity

    # Apply the effect of the new/current transaction
    if instance.transaction_type == AssetTransaction.BUY:
        ledger.quantity_owned += instance.quantity
        ledger.total_purchased_quantity += instance.quantity
    elif instance.transaction_type == AssetTransaction.SELL:
        ledger.quantity_owned -= instance.quantity
        ledger.total_sold_quantity += instance.quantity

    ledger.save()
