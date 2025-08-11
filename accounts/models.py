from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True,blank=True,null=True)
    first_name = models.CharField(max_length=150, blank=True,null=True)
    last_name = models.CharField(max_length=150, blank=True,null=True)
    phone = models.CharField(max_length=20, blank=False)
    emirates_id = models.CharField(max_length=55, blank=True,unique=True,null=True)
    kyc_status = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    
    REQUIRED_FIELDS = ['phone'] 
    
    objects = CustomUserManager()

    def __str__(self):
        return self.email


class OTPVerification(models.Model):
    CONTACT_TYPE_CHOICES = (
        ('email', 'Email'),
        ('phone', 'Phone'),
    )

    contact = models.CharField(max_length=255, db_index=True)
    contact_type = models.CharField(max_length=10, choices=CONTACT_TYPE_CHOICES)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        return self.expires_at < timezone.now()

    def __str__(self):
        return f"{self.contact_type}: {self.contact} -> {self.otp}"