from accounts.models import CustomUser
from typing import Optional
from rest_framework_simplejwt.tokens import RefreshToken


def get_or_create_user(phone: str):

    user, is_created = CustomUser.objects.get_or_create(phone=phone)
    refresh = RefreshToken.for_user(user)
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
        "created": is_created,
    }
