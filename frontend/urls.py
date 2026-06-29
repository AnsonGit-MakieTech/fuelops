from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("guides/progress/", views.guide_progress, name="guide_progress"),
    path("daily-operations/", views.daily_operations, name="daily_operations"),
    path("daily-operations/new/", views.daily_operation_create, name="daily_operation_create"),
    path(
        "daily-operations/<int:pk>/",
        views.daily_operation_detail,
        name="daily_operation_detail",
    ),
    path("fuel-deliveries/", views.fuel_deliveries, name="fuel_deliveries"),
    path("fuel-deliveries/new/", views.fuel_delivery_create, name="fuel_delivery_create"),
    path("expenses/", views.expenses, name="expenses"),
    path("expenses/new/", views.expense_create, name="expense_create"),
    path("reports/", views.reports, name="reports"),
]
