# reports/urls.py
from django.urls import path
from .views import (
    SalesSummaryView,
    SIPOverviewView,
    SIPInstallmentHistoryView,
    UserSIPDetailsView,
    ActiveSIPPlansView,
)

urlpatterns = [
    path("sales-summary/", SalesSummaryView.as_view(), name="sales-summary"),
    path("sip/overview/", SIPOverviewView.as_view(), name="admin-sip-overview"),
    path(
        "sip/active-plans/", ActiveSIPPlansView.as_view(), name="admin-active-sip-plans"
    ),
    path(
        "ip/installments/",
        SIPInstallmentHistoryView.as_view(),
        name="admin-sip-installments",
    ),
    path(
        "sip/user/<int:user_id>/",
        UserSIPDetailsView.as_view(),
        name="admin-user-sip-details",
    ),
]
