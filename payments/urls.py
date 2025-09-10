from django.urls import path
from . import views

urlpatterns = [
    path("create_customer/", views.create_lean_customer, name="create_lean_customer"),
    path(
        "create_payment_intent/",
        views.create_payment_intent,
        name="create_payment_intent",
    ),
    path("my_payment_sources/", views.my_payment_sources, name="my_payment_sources"),
    path("customer_token/", views.get_customer_token, name="get_customer_token"),
    path("webhook/", views.lean_webhook, name="lean_webhook"),
]
