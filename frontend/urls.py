from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import FuelOpsAuthenticationForm


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=FuelOpsAuthenticationForm,
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", views.owner_register, name="register"),
    path(
        "accounts/verify/<uidb64>/<token>/",
        views.verify_email,
        name="verify_email",
    ),
    path(
        "accounts/verification/resend/",
        views.resend_verification,
        name="resend_verification",
    ),
    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/emails/password_reset_email.txt",
            subject_template_name="registration/emails/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path(
        "accounts/invitations/<str:token>/accept/",
        views.accept_invitation,
        name="accept_invitation",
    ),
    path("guides/progress/", views.guide_progress, name="guide_progress"),
    path("setup/station/", views.station_setup, name="station_setup"),
    path("team/", views.team_members, name="team_members"),
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
