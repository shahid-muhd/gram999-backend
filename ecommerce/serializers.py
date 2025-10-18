from rest_framework import serializers
from .models import (
    Category, Product, ProductImage,
    Address, Cart, CartItem,
    Order, OrderItem
)


# --------------------------------------------------------
# Category Serializer
# --------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


# --------------------------------------------------------
# Product Image Serializer
# --------------------------------------------------------
class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    class Meta:
        model = ProductImage
        fields = ["id", "image"]

    def get_image(self, obj):
        # This will return relative path only
        return f"/media/{obj.image.name}" 
# --------------------------------------------------------
# Product Serializer
# --------------------------------------------------------

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    image_files = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    final_price = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)

    class Meta:
        model = Product
        fields = "__all__"

    def create(self, validated_data):
        # Extract image files from request
        image_files = validated_data.pop("image_files", [])
        # Create the product
        product = Product.objects.create(**validated_data)
        # Create ProductImage objects
        for img in image_files:
            ProductImage.objects.create(product=product, image=img)
        return product


# --------------------------------------------------------
# Address Serializer
# --------------------------------------------------------
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"
        read_only_fields = ["user"]


# --------------------------------------------------------
# CartItem Serializer
# --------------------------------------------------------
class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source="product", write_only=True
    )
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_id", "quantity", "total_price"]

    def get_total_price(self, obj):
        return obj.total_price()


# --------------------------------------------------------
# Cart Serializer
# --------------------------------------------------------
class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "user", "items", "total_price"]
        read_only_fields = ["user"]

    def get_total_price(self, obj):
        return obj.total_price()


# --------------------------------------------------------
# OrderItem Serializer
# --------------------------------------------------------
class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "quantity", "price"]


# --------------------------------------------------------
# Order Serializer
# --------------------------------------------------------
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Order
        fields = "__all__"
        read_only_fields = ["user", "created_at", "updated_at"]
