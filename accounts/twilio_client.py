from twilio.rest import Client
from django.conf import settings

client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_sms(receivers_phone, body):
    """
    Send an SMS using Twilio
    :param to: recipient phone number (E.164 format, e.g., +919876543210)
    :param body: message text
    """
    message = client.messages.create(
        messaging_service_sid=settings.TWILIO_MESSAGING_SERVICE_SID,
        body=body,
        to=receivers_phone,
    )
    return message.sid
