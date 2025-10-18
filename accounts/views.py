# accounts/views.py

from rest_framework.decorators import api_view, permission_classes, parser_classes
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

import json
from random import randint
from .models import CustomUser
from rest_framework import generics, permissions
from .serializers import UserDetailSerializer, UserListCreateSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import hmac
import hashlib
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.core.mail import send_mail
from django.conf import settings
import random
from django.utils import timezone
from datetime import timedelta
from accounts.models import OTPVerification
from .utils import get_or_create_user, sendKycRequest, send_otp

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        user = self.user
        data["user"] = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "second_name": user.last_name,
            "kyc_status": user.kyc_status,
        }

        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all()

    def get_serializer_class(self):
        return UserListCreateSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"


class VerificationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        phone = request.data.get("phone")
        otp = request.data.get("otp")

        if not email and not phone:
            return Response(
                {"success": False, "message": "Email or phone is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contact = email or phone
        contact_type = "email" if email else "phone"

        # Handle OTP Verification
        if otp:
            try:
                otp_obj = OTPVerification.objects.get(
                    contact=contact, otp=otp, contact_type=contact_type
                )
                if otp_obj.is_expired():
                    otp_obj.delete()
                    return Response(
                        {"success": False, "message": "OTP has expired."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                otp_obj.delete()

                user_auth_data = get_or_create_user(phone)
                return Response(
                    {
                        "data": user_auth_data,
                        "success": True,
                        "message": "OTP verified successfully.",
                    },
                    status=status.HTTP_200_OK,
                )
            except OTPVerification.DoesNotExist:
                return Response(
                    {"success": False, "message": "Invalid OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # If OTP not provided, generate and send
        # Remove existing OTPs for this contact
        try:
            print("contact>>>.", contact, contact_type)
            send_otp(contact, contact_type)
            response_data = {
                "success": True,
            }

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_kyc_verification(request):
    user = request.user
    response = sendKycRequest(user)
    return Response(response)


import time
from django.http import JsonResponse


@csrf_exempt
def kyc_callback(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        raw_body = request.body
        data = json.loads(raw_body.decode("utf-8") or "{}")

        # --- Signature Verification ---
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")

        if not signature or not timestamp:
            return JsonResponse({"error": "Missing headers"}, status=400)

        # Reject if request too old (>5 min)
        if abs(int(time.time()) - int(timestamp)) > 300:
            return JsonResponse({"error": "Stale webhook"}, status=400)

        secret = settings.DIDIT_WEBHOOK_SECRET.encode()
        expected_sig = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return JsonResponse({"error": "Invalid signature"}, status=401)

        # --- Parse webhook payload ---
        webhook_type = data.get("webhook_type")
        session_id = data.get("session_id")
        vendor_data = data.get("vendor_data")  #  passed user.id when creating session
        status = data.get("status")  # e.g. Approved / Declined / In Review / Abandoned

        print(
            f"✅ Didit Webhook: type={webhook_type}, session={session_id}, decision={status}"
        )

        id_verification = data.get("decision", {}).get("id_verification", {})

        # Extract user information
        user_id_data = {
            "full_name": id_verification.get("full_name"),
            "dob": id_verification.get("date_of_birth"),
        }

        from .utils import is_user_data_valid, update_kyc_status

        # --- Update user ---
        if vendor_data:
            try:
                user = CustomUser.objects.get(id=int(vendor_data))
                if status == "Approved":
                    # if is_user_data_valid(user, user_id_data) is not True:
                    #     update_kyc_status(session_id, "Declined")
                    # else:
                    user.kyc_status = "accepted"
                elif status == "Declined":
                    user.kyc_status = "declined"
                elif status == "In Review":
                    user.kyc_status = "pending"
                elif status == "Abandoned":
                    user.kyc_status = "abandoned"
                user.save()

            except CustomUser.DoesNotExist:
                print(f"⚠️ User {vendor_data} not found")

        return JsonResponse({"status": "ok"}, status=200)

    except Exception as e:
        print("❌ Webhook error:", e)
        return JsonResponse({"error": "Invalid payload"}, status=400)


from django.http import HttpResponse


def kyc_redirect(request):
    result = request.GET.get("event", "")
    print("redirection view hit...")
    deep_link = f"gram999mobile://kyc-process/result?event={result}"

    # Manually return 302 redirect
    response = HttpResponse(status=302)
    response["Location"] = deep_link
    return response


from .models import Nominee
from .serializers import NomineeSerializer


class NomineeView(generics.RetrieveUpdateAPIView):
    serializer_class = NomineeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Only return existing nominee; don't create new one during GET
        try:
            return Nominee.objects.get(user=self.request.user)
        except Nominee.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        nominee = self.get_object()
        if nominee is None:
            return Response(
                {"detail": "Nominee not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(nominee)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        nominee = self.get_object()
        serializer = self.get_serializer(nominee, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()  # Handles update_or_create inside serializer
        return Response(serializer.data)


from rest_framework import generics, permissions
from .models import Address
from .serializers import AddressSerializer


class AddressListCreateView(generics.ListCreateAPIView):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).order_by(
            "-is_primary", "-created_at"
        )

    def perform_create(self, serializer):
        serializer.save()


class AddressRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def toggle_user_block(request, user_id):
    """
    Block or unblock a user.
    Optional JSON body: {"is_blocked": true/false}
    If not provided, the status will toggle.
    """
    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    # Get boolean from request body
    is_blocked = request.data.get("is_blocked")
    if isinstance(is_blocked, bool):
        user.is_blocked = is_blocked
    else:
        # Toggle if not provided
        user.is_blocked = not user.is_blocked

    user.save()

    status_text = "blocked" if user.is_blocked else "unblocked"
    return Response(
        {"detail": f"User {user.email} has been {status_text}."},
        status=status.HTTP_200_OK,
    )
