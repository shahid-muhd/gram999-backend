from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Category, Product, Cart, CartItem, Order
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework import status
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    CartSerializer,
    OrderSerializer,
)
from rest_framework.exceptions import ValidationError


# --------------------------------------------------------
# Category
# --------------------------------------------------------
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        if category.products.exists():
            raise ValidationError(
                "This category cannot be deleted because it has products assigned."
            )
        return super().destroy(request, *args, **kwargs)


# --------------------------------------------------------
# Product
# --------------------------------------------------------


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer

    def get_queryset(self):
        print(f"DEBUG: user={self.request.user}, is_staff={self.request.user.is_staff}")
        if self.request.user.is_staff:
            return Product.objects.all()
        return Product.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [AllowAny()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# --------------------------------------------------------
# Cart
# --------------------------------------------------------
from django.shortcuts import get_object_or_404


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"])
    def add_item(self, request):
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)

        # 🔸 Validate product_id
        if not product_id:
            return Response(
                {"error": "Product ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            return Response(
                {"error": "Quantity must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 🔸 Ensure product exists
        product = get_object_or_404(Product, id=product_id, is_active=True)

        # 🔸 Ensure sufficient stock
        if product.stock < quantity:
            return Response(
                {"error": "Insufficient stock for this product."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 🔸 Get or create the user's cart
        cart, _ = Cart.objects.get_or_create(user=request.user)

        # 🔸 Add or update cart item
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={"quantity": quantity}
        )

        if not created:
            item.quantity += quantity
            item.save()

        return Response(
            {"detail": f"{product.name} added to cart."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def remove_item(self, request):
        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"error": "Product ID required."}, status=status.HTTP_400_BAD_REQUEST
            )

        cart = Cart.objects.filter(user=request.user).first()
        if not cart:
            return Response(
                {"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST
            )

        item = CartItem.objects.filter(cart=cart, product_id=product_id).first()
        if not item:
            return Response(
                {"error": "Item not found in cart."}, status=status.HTTP_404_NOT_FOUND
            )

        item.delete()
        return Response(
            {"detail": "Item removed from cart."}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["post"])
    def update_quantity(self, request):
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity")

        if not product_id or quantity is None:
            return Response(
                {"error": "Product ID and quantity are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quantity = int(quantity)
            if quantity < 1:
                raise ValueError
        except ValueError:
            return Response(
                {"error": "Quantity must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart = Cart.objects.filter(user=request.user).first()
        if not cart:
            return Response(
                {"error": "Cart not found."}, status=status.HTTP_404_NOT_FOUND
            )

        item = CartItem.objects.filter(cart=cart, product_id=product_id).first()
        if not item:
            return Response(
                {"error": "Item not found in cart."}, status=status.HTTP_404_NOT_FOUND
            )

        if item.product.stock < quantity:
            return Response(
                {"error": "Insufficient stock."}, status=status.HTTP_400_BAD_REQUEST
            )

        item.quantity = quantity
        item.save()
        return Response(
            {"detail": "Quantity updated successfully."}, status=status.HTTP_200_OK
        )


# --------------------------------------------------------
# Order
# --------------------------------------------------------
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
