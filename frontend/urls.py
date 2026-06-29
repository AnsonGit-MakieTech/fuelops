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
    path("stations/switch/", views.switch_station, name="switch_station"),
    path("settings/station/", views.station_settings, name="station_settings"),
    path("settings/station/edit/", views.station_edit, name="station_edit"),
    path(
        "settings/products/new/",
        views.fuel_product_edit,
        name="fuel_product_create",
    ),
    path(
        "settings/products/<int:pk>/edit/",
        views.fuel_product_edit,
        name="fuel_product_edit",
    ),
    path("settings/tanks/new/", views.tank_edit, name="tank_create"),
    path("settings/tanks/<int:pk>/edit/", views.tank_edit, name="tank_edit"),
    path("settings/pumps/new/", views.pump_edit, name="pump_create"),
    path("settings/pumps/<int:pk>/edit/", views.pump_edit, name="pump_edit"),
    path("settings/suppliers/", views.suppliers, name="suppliers"),
    path("settings/suppliers/new/", views.supplier_edit, name="supplier_create"),
    path(
        "settings/suppliers/<int:pk>/edit/",
        views.supplier_edit,
        name="supplier_edit",
    ),
    path("inventory/", views.inventory, name="inventory"),
    path(
        "inventory/adjustments/new/",
        views.inventory_adjustment_create,
        name="inventory_adjustment_create",
    ),
    path(
        "inventory/adjustments/<int:pk>/approve/",
        views.inventory_adjustment_approve,
        name="inventory_adjustment_approve",
    ),
    path("daily-operations/", views.daily_operations, name="daily_operations"),
    path("daily-operations/new/", views.daily_operation_create, name="daily_operation_create"),
    path(
        "daily-operations/<int:pk>/",
        views.daily_operation_detail,
        name="daily_operation_detail",
    ),
    path(
        "daily-operations/<int:operation_pk>/readings/<int:reading_pk>/edit/",
        views.pump_reading_edit,
        name="pump_reading_edit",
    ),
    path(
        "daily-operations/<int:operation_pk>/readings/<int:reading_pk>/archive/",
        views.pump_reading_archive,
        name="pump_reading_archive",
    ),
    path("fuel-deliveries/", views.fuel_deliveries, name="fuel_deliveries"),
    path("fuel-deliveries/new/", views.fuel_delivery_create, name="fuel_delivery_create"),
    path("fuel-deliveries/<int:pk>/edit/", views.fuel_delivery_edit, name="fuel_delivery_edit"),
    path("fuel-deliveries/<int:pk>/archive/", views.fuel_delivery_archive, name="fuel_delivery_archive"),
    path("expenses/", views.expenses, name="expenses"),
    path("expenses/new/", views.expense_create, name="expense_create"),
    path("expenses/categories/", views.expense_categories, name="expense_categories"),
    path("expenses/categories/new/", views.expense_category_edit, name="expense_category_create"),
    path("expenses/categories/<int:pk>/edit/", views.expense_category_edit, name="expense_category_edit"),
    path("expenses/<int:pk>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:pk>/archive/", views.expense_archive, name="expense_archive"),
    path("reports/", views.reports, name="reports"),
]
