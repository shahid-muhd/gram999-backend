# ecommerce/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    ProductViewSet,
    CartViewSet,
    OrderViewSet,
)

router = DefaultRouter()

# 👇 Assign basenames to avoid AssertionError
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")
router.register("carts", CartViewSet, basename="cart")
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("", include(router.urls)),
]
