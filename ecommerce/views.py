from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Category, Product, Cart, CartItem, Order, OrderItem
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework import status
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    CartSerializer,
    OrderSerializer,
)
from rest_framework.exceptions import ValidationError
from rest_framework_extensions.cache.mixins import CacheResponseMixin
from rest_framework_extensions.cache.decorators import cache_response
from rest_framework_extensions.key_constructor.constructors import DefaultKeyConstructor
from rest_framework_extensions.key_constructor.bits import (
    QueryParamsKeyBit,
    ListSqlQueryKeyBit,
    RetrieveSqlQueryKeyBit,
)


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


class ProductListKeyConstructor(DefaultKeyConstructor):
    query_params = QueryParamsKeyBit(["category"])
    list_sql = ListSqlQueryKeyBit()


class ProductViewSet(CacheResponseMixin, viewsets.ModelViewSet):
    """
    Product ViewSet with per-view caching.
    Caches GET requests for 5 minutes.
    Auto invalidates cache when products are modified.
    """

    serializer_class = ProductSerializer

    def get_queryset(self):
        print(f"DEBUG: user={self.request.user}, is_staff={self.request.user.is_staff}")

        queryset = (
            Product.objects.all()
            if self.request.user.is_staff
            else Product.objects.filter(is_active=True)
        )

        category_id = self.request.query_params.get("category")
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return queryset

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [AllowAny()]

    @cache_response(timeout=60 * 5, key_func=ProductListKeyConstructor())
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
from django.db import transaction
from rest_framework import status, viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from .models import Cart, OrderItem, Order
from payments.models import Wallet
from accounts.models import Address 
from .serializers import OrderSerializer  
from accounts.serializers import AddressSerializer


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by("-created_at")

    def retrieve(self, request, *args, **kwargs):
        """
        Return order details including address object.
        """
        order = self.get_object()
        serializer = self.get_serializer(order)
        data = serializer.data

  
        if order.address_id:
            try:
                address = Address.objects.get(id=order.address_id, user=request.user)
                data["address"] = AddressSerializer(address).data
            except Address.DoesNotExist:
                data["address"] = None

        return Response(data)
    @transaction.atomic
    def perform_create(self, serializer):
        print("🔥 RAW INCOMING DATA:", self.request.data)
        user = self.request.user
        cart = Cart.objects.filter(user=user).first()
    
        if not cart or not cart.items.exists():
            raise ValidationError("Your cart is empty.")
    
        # Step 1: Validate all items + compute total
        total_amount = 0
        for item in cart.items.select_related("product").select_for_update(of=("product",)):
            product = item.product
            if not product.is_active:
                raise ValidationError(f"Product '{product.name}' is inactive.")
            if item.quantity > product.stock:
                raise ValidationError(
                    f"Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock}, Requested: {item.quantity}."
                )
            total_amount += item.total_price()
    
        # Step 2: Handle payment
        payment_method = self.request.data.get("payment_method", "").lower()
        payment_status = "Pending"
    
        if payment_method == "wallet":
            wallet = Wallet.objects.select_for_update().filter(user=user).first()
            if not wallet:
                raise ValidationError("Wallet not found for this user.")
            if wallet.balance < total_amount:
                raise ValidationError("Insufficient wallet balance.")
    
            # Deduct from wallet safely
            wallet.withdraw(total_amount, payment_intent=None, description="Order Payment")
            payment_status = "Paid"  # ✅ Payment successful
    
        # Step 3: Create the order
        order = serializer.save(
            user=user,
            total_amount=total_amount,
            payment_method=payment_method,
            payment_status=payment_status,  # ✅ set here
        )
    
        # Step 4: Create OrderItems and reduce stock
        for item in cart.items.select_related("product"):
            product = item.product
            product.stock -= item.quantity
            product.save(update_fields=["stock"])
    
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item.quantity,
                price=product.final_price,
            )
    
        # Step 5: Clear the cart
        cart.items.all().delete()
    
        return order
    