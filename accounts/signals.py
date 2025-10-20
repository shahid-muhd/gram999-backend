from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@receiver(post_save, sender=CustomUser)
def send_kyc_status_update(sender, instance, created, **kwargs):
    if created:
        print(f"🟡 New user created: {instance.email}, skipping signal.")
        return


    new_status = instance.kyc_status

    print(f"🟠 Signal triggered for {instance.email}:  new={new_status}")

    if new_status is not None:
        print(f"🟢 Sending WebSocket update for {instance.email}")
        channel_layer = get_channel_layer()
        group_name = f"user_{instance.id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "account_update",
                "data": {
                    "kyc_status": new_status,
                    "message": f"Your KYC status has been updated to {new_status}",
                },
            },
        )

    instance._kyc_status_cache = new_status
