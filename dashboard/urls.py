# reports/urls.py
from django.urls import path
from .views import SalesSummaryView

urlpatterns = [
    path("sales-summary/", SalesSummaryView.as_view(), name="sales-summary"),
]
