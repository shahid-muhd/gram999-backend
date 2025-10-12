# accounts/serializers.py

from rest_framework import serializers
from .models import CustomUser, Nominee


class UserListCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "password",
            "emirates_id",
        ]
        read_only_fields = ["id", "emirates_id"]

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = "__all__"  # returns all model fields except password
        extra_kwargs = {"password": {"write_only": True}}

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        # --- Check if phone number is being changed ---
        new_phone = validated_data.get("phone")
        if new_phone and new_phone != instance.phone:
            instance.kyc_status = "pending"

        # --- Update other fields ---
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class NomineeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nominee
        fields = ['id', 'full_name', 'date_of_birth', 'relationship', 'address']
        read_only_fields = ['id']

    def create(self, validated_data):
        user = self.context['request'].user
        # If nominee already exists, update instead of creating a new one
        nominee, created = Nominee.objects.update_or_create(
            user=user,
            defaults=validated_data
        )
        return nominee



from rest_framework import serializers
from .models import Address

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id',
            'address_line1',
            'address_line2',
            'city',
            'state_province',
            'postal_code',
            'country',
            'is_primary',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        user = self.context['request'].user

        # If new address is primary, unmark any existing primary address
        if validated_data.get('is_primary', False):
            Address.objects.filter(user=user, is_primary=True).update(is_primary=False)

        return Address.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        user = self.context['request'].user

        # Handle primary flag update
        if validated_data.get('is_primary', False):
            Address.objects.filter(user=user, is_primary=True).exclude(id=instance.id).update(is_primary=False)

        return super().update(instance, validated_data)
