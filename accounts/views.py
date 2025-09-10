# accounts/views.py

from rest_framework.decorators import api_view, permission_classes, parser_classes
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser, FormParser
import base64, json, requests
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
from .utils import get_or_create_user, sendOTP, sendKycRequest

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
            OTPVerification.objects.filter(
                contact=contact, contact_type=contact_type
            ).delete()

            generated_otp = str(random.randint(100000, 999999))
            print('generated otp >>',generated_otp)
            # sendOTP(contact, contact_type)
            OTPVerification.objects.create(
                contact=contact,
                contact_type=contact_type,
                otp=generated_otp,
                expires_at=timezone.now() + timedelta(minutes=6),
            )

            message = ""
            if contact_type == "email":
                send_mail(
                    subject="Your Verification Code",
                    message=f"Your OTP code is: {generated_otp}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                message = "OTP sent to email."
            else:
                # Implement actual SMS send logic here
                # e.g., send_sms(phone, generated_otp)
                message = phone

            response_data = {
                "success": True,
                "message": message,
            }

            # Return OTP only in dev/debug mode
            if settings.DEBUG:
                response_data["otp"] = generated_otp

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_kyc_verification(request):

    user = request.user

    response = sendKycRequest(user)

    return Response(response)


import hmac, hashlib, json
from django.http import JsonResponse


@csrf_exempt
def shufti_callback(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        raw_body = request.body
        headers = dict(request.headers)

        print("🔹 Raw body:", raw_body)
        print("🔹 Headers:", headers)

        # --- Parse JSON manually (to avoid DRF issues) ---
        data = json.loads(raw_body.decode("utf-8") or "{}")
        print("✅ Parsed:", data)

        reference = data.get("reference")
        event = data.get("event")

        user_id = None
        if reference:
            try:
                user_id = int(reference.split("_")[-1])
            except (ValueError, IndexError):
                pass

        # --- Update user KYC status ---
        if user_id:
            try:
                user = CustomUser.objects.get(id=user_id)
                if event == "verification.accepted":
                    user.kyc_status = "accepted"
                elif event == "verification.declined":
                    user.kyc_status = "declined"
                user.save()
                print(f"✅ Updated user {user.id} KYC status to {user.kyc_status}")
            except CustomUser.DoesNotExist:
                print(f"⚠️ User {user_id} not found")

        return JsonResponse({"status": "received", "user_id": user_id}, status=200)

    except Exception as e:
        print("❌ Callback error:", e)
        return JsonResponse({"error": "Invalid payload"}, status=200)


from django.http import HttpResponse


def kyc_redirect(request):
    result = request.GET.get("event", "")

    deep_link = f"gram999mobile://kyc-process/result?event={result}"

    # Manually return 302 redirect
    response = HttpResponse(status=302)
    response["Location"] = deep_link
    return response
