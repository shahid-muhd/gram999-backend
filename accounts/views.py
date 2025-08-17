# accounts/views.py
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions
from .serializers import UserDetailSerializer, UserListCreateSerializer

User = get_user_model()


from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
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
from .utils import get_or_create_user

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
        OTPVerification.objects.filter(
            contact=contact, contact_type=contact_type
        ).delete()

        generated_otp = str(random.randint(100000, 999999))
        print(generated_otp)
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
