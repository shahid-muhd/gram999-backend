from accounts.models import CustomUser
from typing import Optional
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
import base64, json, requests
from random import randint


def get_or_create_user(phone: str):

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


def send_shufti_api_request(request_data):
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
    print(response.json())
    return response.json()


def sendOTP(contact, contact_type):

    otp_request = {
        "reference": f"REQ_{randint(1000,9999)}_{contact}",
        "country": "",
        "language": "en",
        "callback_url": None,
        "redirect_url": None,
        "verification_mode": "any",
        "show_consent": "1",
        "decline_on_single_step": "1",
        "manual_review": "0",
        "show_privacy_policy": "0",
        "show_results": "0",
        "show_feedback_form": "0",
        "allow_na_ocr_inputs": "0",
        "ttl": 60,
        "enhanced_originality_checks": "0",
    }

    if contact_type == "email":
        otp_request["email"] = contact
    else:
        otp_request["phone"] = (
            {
                "phone_number": contact,
                "random_code": str(randint(100000, 999999)),
                "text": "Hi, Your code for your Gram 999 account verification is:",
            },
        )
    print(otp_request)
    send_shufti_api_request(otp_request)


def sendKycRequest(user):
    verification_request = {
        "reference": f"REQ_{randint(1000,9999)}_{user.id}",
        "callback_url": "https://handy-moved-monkfish.ngrok-free.app/api/accounts/kyc/callback/",
        "redirect_url": "https://handy-moved-monkfish.ngrok-free.app/api/accounts/kyc/redirect/",
        "email": user.email,
        "language": "EN",
        "verification_mode": "any",
        "face": {"proof": ""},
        "document": {
            "proof": "",
            "supported_types": ["passport", "id_card", "driving_license"],
            "name": {
                "first_name": "",
                "last_name": "",
                "middle_name": "",
            },
            "dob": "",
            "document_number": "",
            "expiry_date": "",
            "issue_date": "",
            "gender": "",
        },
    }

    return send_shufti_api_request(verification_request)
