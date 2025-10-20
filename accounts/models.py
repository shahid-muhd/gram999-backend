from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.conf import settings
from django.utils import timezone
from django_countries.fields import CountryField


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
    email = models.EmailField(unique=True, blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=False)
    emirates_id = models.CharField(max_length=55, blank=True, unique=True, null=True)
    dob = models.DateField(blank=True, null=True)

    KYC_STATUSES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("review", "Under Review"),
    ]
    kyc_status = models.CharField(
        max_length=20,
        choices=KYC_STATUSES,
        default="pending",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_blocked = models.BooleanField(default=False)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone"]

    objects = CustomUserManager()

    def __str__(self):
        return self.email


class Address(models.Model):
    ADDRESS_TYPES = [
        ("Home", "Home"),
        ("Work", "Work"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default="Home")  # Added field
    address_line1 = models.CharField(max_length=255)  # Street address, house no.
    address_line2 = models.CharField(max_length=255, blank=True, null=True)  # Apartment, suite, etc.
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100, blank=True, null=True)  # State / Province / Region
    postal_code = models.CharField(max_length=20)  # Zip/Postal code
    country = models.CharField(max_length=100) 
    is_primary = models.BooleanField(default=False)  # Default address flag

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Addresses"
        indexes = [
            models.Index(fields=["city", "country"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_primary=True),
                name="unique_primary_address_per_user",
            )
        ]

    def __str__(self):
        return f"{self.address_line1}, {self.city}, {self.country.name} ({self.type})"


class OTPVerification(models.Model):
    CONTACT_TYPE_CHOICES = (
        ("email", "Email"),
        ("phone", "Phone"),
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


class Nominee(models.Model):
    RELATIONSHIP_CHOICES = [
        ("father", "Father"),
        ("mother", "Mother"),
        ("spouse", "Spouse"),
        ("brother", "Brother"),
        ("sister", "Sister"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="nominees"
    )
    full_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} ({self.relationship})"
