from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter
from .views import UserLedgerViewSet

router = DefaultRouter()
router.register(r"orders", UserLedgerViewSet, basename="user-ledger")

urlpatterns = [
    path("create_customer/", views.create_lean_customer, name="create_lean_customer"),
    path(
        "create_payment_intent/",
        views.create_payment_intent,
        name="create_payment_intent",
    ),
    path("my_payment_sources/", views.my_payment_sources, name="my_payment_sources"),
    path("customer_token/", views.get_customer_token, name="get_customer_token"),
    path("bank_accounts/", views.bank_accounts, name="get_lean_accounts"),
    path("webhook/", views.lean_webhook, name="lean_webhook"),
    path("wallet-balance/", views.get_wallet, name="get_wallet"),
    path(
        "wallet-transactions/",
        views.get_wallet_transactions,
        name="get_wallet_transactions",
    ),
    path("", include(router.urls)),  # include router URLs here
]
