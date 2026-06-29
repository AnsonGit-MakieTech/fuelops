from django.urls import path

from . import views


urlpatterns = [
    path("dashboard/summary/", views.dashboard_summary, name="api_dashboard_summary"),
    path("reports/daily/", views.daily_report, name="api_daily_report"),
    path("reports/monthly/", views.monthly_report, name="api_monthly_report"),
    path("calculate/pump-reading/", views.calculate_pump_reading, name="api_calculate_pump_reading"),
    path("calculate/cash-variance/", views.calculate_cash_variance, name="api_calculate_cash_variance"),
]
