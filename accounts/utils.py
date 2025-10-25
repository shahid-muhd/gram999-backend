import base64
import json
import re
from random import randint
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import CustomUser
from .didit_client import DiditClient
from .twilio_client import send_sms


def get_or_create_user(phone: str):
    """
    Returns user tokens and profile data.
    Marks user as 'created' if it's a new user or missing profile details.
    """
    user, is_new_user = CustomUser.objects.get_or_create(phone=phone)
    refresh = RefreshToken.for_user(user)

    if not user.first_name or not user.last_name:
        is_new_user = True

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "second_name": user.last_name,
            "kyc_status": user.kyc_status,
            "phone": user.phone,
        },
        "created": is_new_user,
    }


# === Legacy ShuftiPro methods (keep only if you still use Shufti) ===


def send_shufti_api_request(request_data):
    """
    (Legacy ShuftiPro) Sends an API request to Shufti.
    """
    import requests

    auth = f"{settings.SHUFTI_CLIENT_ID}:{settings.SHUFTI_SECRET_KEY}"
    b64Val = base64.b64encode(auth.encode()).decode()

    response = requests.post(
        settings.SHUFTI_API_URL,
        headers={
            "Authorization": f"Basic {b64Val}",
            "Content-Type": "application/json",
        },
        data=json.dumps(request_data),
    )
    try:
        return response.json()
    except Exception:
        return {"success": False, "error": response.text}


# === Didit integration ===


def send_otp(contact, contact_type):
    from accounts.models import OTPVerification
    from random import randint
    from django.core.mail import send_mail
    from django.utils import timezone
    from datetime import timedelta

    OTPVerification.objects.filter(contact=contact, contact_type=contact_type).delete()

    generated_otp = str(randint(100000, 999999))
    print("generated otp >>", generated_otp)
    # sendOTP(contact, contact_type)
    OTPVerification.objects.create(
        contact=contact,
        contact_type=contact_type,
        otp=generated_otp,
        expires_at=timezone.now() + timedelta(minutes=6),
    )

    res_message = ""
    if contact_type == "email":
        send_mail(
            subject="Your Verification Code",
            message=f"Your OTP code is: {generated_otp}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[contact],
            fail_silently=False,
        )
        res_message = "OTP sent to email."
    else:

        # payload = {
        #     "phone_number": contact,
        #     "options": {"locale": "en-IN", "code_size": 6},
        # }
        # didit_client.send_otp(payload)

        sms_body = f"Verification code for your Gram99 account is: {generated_otp}"
        print(contact)
        send_sms(body=sms_body, receivers_phone=contact)

        res_message = "OTP sent to phone"

    if settings.DEBUG:
        print(res_message, generated_otp)


def sendKycRequest(user: CustomUser):
    """
    Starts a Didit KYC workflow session using DiditClient.
    """
    client = DiditClient()

    payload = {
        "workflow_id": settings.DIDIT_WORKFLOW_ID,
        "vendor_data": str(user.id),
        "callback": f"{settings.BACKEND_URL}/api/accounts/kyc/callback/",
        "redirect_url": f"{settings.BACKEND_URL}/api/accounts/kyc/redirect/",
        "customer": {
            "email": user.email,
            "phone": getattr(user, "phone", None),
        },
        "metadata": {
            "initiated_by": "django-backend",
            "request_id": f"REQ_{randint(1000,9999)}_{user.id}",
        },
    }

    return client.create_session(payload)


def change_user_data(user: CustomUser, id_data: dict):
    # client = DiditClient(version="v1")
    # client.update_session_status(session_id, status)
    pass


from datetime import datetime


def sync_user_with_id_data(user: CustomUser, id_data: dict) -> CustomUser:
    """
    Syncs user's data with extracted ID card data.

    Updates:
    - first_name and last_name from id_data["full_name"]
    - dob from id_data["dob"] (converted to DRF-acceptable date format)
    """

    id_full_name = id_data.get("full_name", "").strip()
    id_dob = id_data.get("dob")

    # ✅ Handle name splitting safely
    name_parts = id_full_name.split(" ", 1)
    user.first_name = name_parts[0].title() if name_parts else ""

    if len(name_parts) > 1:
        user.last_name = name_parts[1].title()
    else:
        user.last_name = ""

    # ✅ Normalize DOB (accepts 'YYYY-MM-DD', 'DD/MM/YYYY', etc.)
    if id_dob:
        try:
            # Try parsing in multiple formats
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
                try:
                    parsed_dob = datetime.strptime(id_dob, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                raise ValueError("Unsupported DOB format")

            user.dob = parsed_dob
        except Exception as e:
            print(f"⚠️ DOB parsing failed: {e}")

    user.save()


from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from jwt import decode as jwt_decode
from django.conf import settings

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token):
    try:
        # Validate the token
        UntypedToken(token)

        # Decode the token to get user_id
        decoded_data = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = decoded_data.get("user_id")
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()
