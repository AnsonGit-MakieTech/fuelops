import json
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_http_methods, require_POST

from api.models import (
    AuditLog,
    CashCollection,
    DailyOperation,
    Expense,
    FuelDelivery,
    FuelProduct,
    InventoryAdjustment,
    Pump,
    PumpReading,
    Station,
    StationInvitation,
    StationMembership,
    Supplier,
    Tank,
)

from .forms import (
    CashCollectionForm,
    DailyOperationForm,
    ExpenseForm,
    FuelDeliveryForm,
    FuelProductForm,
    InventoryAdjustmentForm,
    InvitationRegistrationForm,
    InviteMemberForm,
    OwnerRegistrationForm,
    PumpForm,
    PumpReadingForm,
    StationForm,
    StationSetupForm,
    SupplierForm,
    TankForm,
    VerificationResendForm,
)
from .access import (
    APPROVE_ADJUSTMENTS,
    CREATE_ADJUSTMENTS,
    ENCODE_OPERATIONS,
    MANAGE_CATALOG,
    MANAGE_DELIVERIES,
    MANAGE_EXPENSES,
    MANAGE_TEAM,
    VIEW_INVENTORY,
    VIEW_REPORTS,
    can_approve_station,
    current_station_for_user,
    require_station_permission,
    stations_for_user,
    stations_for_user_with_permission,
    user_has_station_permission,
)
from .guides import GUIDE_VERSION, VALID_GUIDE_KEYS
from .models import GuidedTourProgress
from .security import request_is_rate_limited
from .services.registration import (
    accept_invitation_for_user,
    activate_user,
    configure_first_station,
    create_invitation,
    get_active_invitation,
    register_invited_user,
    register_owner,
    send_invitation_email,
    send_verification_email,
)


ZERO = Decimal("0")


@require_http_methods(["GET", "POST"])
def owner_register(request):
    if not settings.REGISTRATION_ENABLED:
        raise Http404("Registration is not enabled.")
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        if request_is_rate_limited(request, "owner-register", limit=5):
            messages.error(request, "Too many registration attempts. Please try again later.")
            form = OwnerRegistrationForm(request.POST)
        else:
            form = OwnerRegistrationForm(request.POST)
            if form.is_valid():
                user, _ = register_owner(
                    form.cleaned_data,
                    require_verification=settings.EMAIL_VERIFICATION_REQUIRED,
                )
                if settings.EMAIL_VERIFICATION_REQUIRED:
                    try:
                        send_verification_email(request, user, settings.DEFAULT_FROM_EMAIL)
                    except Exception:
                        messages.error(
                            request,
                            "Your account was created, but the verification email could not be sent. Request a new link below.",
                        )
                    return render(
                        request,
                        "registration/verification_pending.html",
                        {"page_title": "Verify Email", "email": user.email},
                    )

                auth_login(request, user)
                messages.success(request, "Account created. Configure your first fuel product to finish setup.")
                return redirect("station_setup")
    else:
        form = OwnerRegistrationForm()

    return render(
        request,
        "registration/register.html",
        {"page_title": "Create Account", "form": form},
    )


@require_http_methods(["GET"])
def verify_email(request, uidb64, token):
    User = get_user_model()
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if not user or not default_token_generator.check_token(user, token):
        return render(
            request,
            "registration/verification_invalid.html",
            {"page_title": "Invalid Verification Link"},
            status=400,
        )

    activate_user(user)
    auth_login(request, user)
    messages.success(request, "Email verified. Complete your station setup.")
    return redirect("station_setup")


@require_http_methods(["GET", "POST"])
def resend_verification(request):
    if request.method == "POST":
        form = VerificationResendForm(request.POST)
        if form.is_valid() and not request_is_rate_limited(request, "verification-resend", limit=4):
            User = get_user_model()
            user = User.objects.filter(email__iexact=form.cleaned_data["email"], is_active=False).first()
            if user:
                try:
                    send_verification_email(request, user, settings.DEFAULT_FROM_EMAIL)
                except Exception:
                    pass
            messages.success(request, "If the account is awaiting verification, a new link has been sent.")
            return redirect("login")
        if form.is_valid():
            messages.error(request, "Too many requests. Please try again later.")
    else:
        form = VerificationResendForm()
    return render(
        request,
        "registration/resend_verification.html",
        {"page_title": "Resend Verification", "form": form},
    )


@login_required
@require_http_methods(["GET", "POST"])
def station_setup(request):
    station = get_current_station(request.user)
    if not station:
        messages.error(request, "No station is assigned to your account.")
        return redirect("dashboard")
    require_station_permission(request.user, station, MANAGE_CATALOG)
    if station.pumps.filter(is_active=True).exists():
        messages.info(request, "This station is already configured.")
        return redirect("dashboard")

    if request.method == "POST":
        form = StationSetupForm(request.POST)
        if form.is_valid():
            try:
                configure_first_station(request.user, station, form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, "Station setup complete. FuelOps is ready for daily operations.")
                return redirect("dashboard")
    else:
        form = StationSetupForm()

    return render(
        request,
        "frontend/setup/station.html",
        {
            "page_title": "Station Setup",
            "station": station,
            "form": form,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def team_members(request):
    station = get_current_station(request.user)
    if not station:
        raise PermissionDenied
    require_station_permission(request.user, station, MANAGE_TEAM)

    if request.method == "POST" and request.POST.get("action") == "revoke_invitation":
        invitation = get_object_or_404(
            StationInvitation,
            pk=request.POST.get("invitation_id"),
            station=station,
            accepted_at=None,
            revoked_at=None,
        )
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at", "updated_at"])
        messages.success(request, "Invitation revoked.")
        return redirect("team_members")

    if request.method == "POST":
        form = InviteMemberForm(request.POST, station=station)
        if request_is_rate_limited(request, "team-invite", limit=10):
            messages.error(request, "Too many invitations were requested. Please try again later.")
        elif form.is_valid():
            invitation, raw_token = create_invitation(
                station,
                request.user,
                form.cleaned_data["email"],
                form.cleaned_data["role"],
            )
            try:
                send_invitation_email(request, invitation, raw_token, settings.DEFAULT_FROM_EMAIL)
            except Exception:
                messages.error(request, "Invitation saved, but the email could not be sent.")
            else:
                messages.success(request, "Team invitation sent.")
            return redirect("team_members")
    else:
        form = InviteMemberForm(station=station)

    return render(
        request,
        "frontend/team.html",
        {
            "page_title": "Team",
            "station": station,
            "form": form,
            "members": station.memberships.select_related("user", "invited_by").order_by("role", "user__username"),
            "invitations": station.invitations.filter(
                accepted_at=None,
                revoked_at=None,
                expires_at__gt=timezone.now(),
            ),
        },
    )


@require_http_methods(["GET", "POST"])
def accept_invitation(request, token):
    invitation = get_active_invitation(token)
    if not invitation:
        return render(
            request,
            "registration/invitation_invalid.html",
            {"page_title": "Invalid Invitation"},
            status=400,
        )

    User = get_user_model()
    existing_user = User.objects.filter(email__iexact=invitation.email).first()
    if existing_user:
        if not request.user.is_authenticated:
            messages.info(request, "Sign in with the invited account to accept access.")
            return redirect(f"{reverse('login')}?next={request.path}")
        if request.user.pk != existing_user.pk:
            raise PermissionDenied
        accept_invitation_for_user(invitation, request.user)
        messages.success(request, f"You now have access to {invitation.station.name}.")
        return redirect("dashboard")

    if request.user.is_authenticated:
        raise PermissionDenied

    if request.method == "POST":
        form = InvitationRegistrationForm(request.POST, email=invitation.email)
        if request_is_rate_limited(request, "invitation-accept", limit=6):
            messages.error(request, "Too many attempts. Please try again later.")
        elif form.is_valid():
            user = register_invited_user(invitation, form.cleaned_data)
            auth_login(request, user)
            messages.success(request, f"Account created. You now have access to {invitation.station.name}.")
            return redirect("dashboard")
    else:
        form = InvitationRegistrationForm(email=invitation.email)

    return render(
        request,
        "registration/accept_invitation.html",
        {
            "page_title": "Join Station",
            "invitation": invitation,
            "form": form,
        },
    )


@login_required
@require_POST
def guide_progress(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "Invalid request payload."}, status=400)

    guide_key = payload.get("guide_key")
    version = payload.get("version")
    status = payload.get("status")

    if guide_key not in VALID_GUIDE_KEYS or version != GUIDE_VERSION:
        return JsonResponse({"error": "Unknown guide or version."}, status=400)
    if status not in GuidedTourProgress.Status.values:
        return JsonResponse({"error": "Invalid guide status."}, status=400)

    progress, _ = GuidedTourProgress.objects.update_or_create(
        user=request.user,
        guide_key=guide_key,
        version=version,
        defaults={"status": status},
    )
    return JsonResponse({"status": progress.status})


def decimal_or_zero(value):
    return value or ZERO


def user_can_approve(user, station):
    return can_approve_station(user, station)


def get_current_station(user):
    return current_station_for_user(user)


def month_bounds(month_value):
    try:
        year, month = [int(part) for part in month_value.split("-")]
        start = date(year, month, 1)
    except (AttributeError, TypeError, ValueError):
        today = timezone.localdate()
        start = today.replace(day=1)

    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    return start, end


def dashboard_metrics(station):
    today = timezone.localdate()
    month_start = today.replace(day=1)

    today_readings = PumpReading.objects.filter(
        daily_operation__station=station,
        daily_operation__operation_date=today,
    ).select_related("pump__fuel_product")
    today_collections = CashCollection.objects.filter(
        daily_operation__station=station,
        daily_operation__operation_date=today,
    )
    monthly_readings = PumpReading.objects.filter(
        daily_operation__station=station,
        daily_operation__status=DailyOperation.Status.APPROVED,
        daily_operation__operation_date__gte=month_start,
        daily_operation__operation_date__lte=today,
    )

    today_expected_sales = sum((item.expected_sales for item in today_readings), ZERO)
    today_liters = sum((item.liters_sold for item in today_readings), ZERO)
    today_collected = sum((item.total_collection for item in today_collections), ZERO)
    today_shortage = sum((item.shortage for item in today_collections), ZERO)
    today_overage = sum((item.overage for item in today_collections), ZERO)
    monthly_expected_sales = sum((item.expected_sales for item in monthly_readings), ZERO)
    monthly_fuel_cost = sum(
        (item.liters_sold * item.cost_per_liter for item in monthly_readings),
        ZERO,
    )
    monthly_expenses = decimal_or_zero(
        Expense.objects.filter(
            station=station,
            expense_date__gte=month_start,
            expense_date__lte=today,
        ).aggregate(total=Sum("amount"))["total"]
    )
    monthly_net_profit = monthly_expected_sales - monthly_fuel_cost - monthly_expenses

    return {
        "today": today,
        "today_expected_sales": today_expected_sales,
        "today_liters": today_liters,
        "today_collected": today_collected,
        "today_shortage": today_shortage,
        "today_overage": today_overage,
        "monthly_net_profit": monthly_net_profit,
        "monthly_expenses": monthly_expenses,
    }


def permitted_current_station(request, permission):
    station = get_current_station(request.user)
    if not station:
        raise PermissionDenied
    require_station_permission(request.user, station, permission)
    return station


@login_required
def station_settings(request):
    station = permitted_current_station(request, MANAGE_CATALOG)
    return render(
        request,
        "frontend/settings/station.html",
        {
            "page_title": "Station Settings",
            "station": station,
            "products": station.fuel_products.all(),
            "tanks": station.tanks.select_related("fuel_product").all(),
            "pumps": station.pumps.select_related("fuel_product", "tank").all(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def station_edit(request):
    station = permitted_current_station(request, MANAGE_CATALOG)
    form = StationForm(request.POST or None, instance=station)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Station details updated.")
        return redirect("station_settings")
    return render(
        request,
        "frontend/settings/catalog_form.html",
        {
            "page_title": "Edit Station",
            "station": station,
            "form": form,
            "entity_label": "Station",
            "submit_label": "Save Station",
            "cancel_url": reverse("station_settings"),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def fuel_product_edit(request, pk=None):
    station = permitted_current_station(request, MANAGE_CATALOG)
    product = (
        get_object_or_404(FuelProduct, pk=pk, station=station)
        if pk is not None
        else FuelProduct(station=station)
    )
    form = FuelProductForm(request.POST or None, instance=product, station=station)
    form.instance.station = station
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.station = station
        product.full_clean()
        product.save()
        messages.success(request, "Fuel product saved.")
        return redirect("station_settings")
    return render(
        request,
        "frontend/settings/catalog_form.html",
        {
            "page_title": "Edit Fuel Product" if pk else "Add Fuel Product",
            "station": station,
            "form": form,
            "entity_label": "Fuel Product",
            "submit_label": "Save Product",
            "cancel_url": reverse("station_settings"),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def tank_edit(request, pk=None):
    station = permitted_current_station(request, MANAGE_CATALOG)
    tank = (
        get_object_or_404(Tank, pk=pk, station=station)
        if pk is not None
        else Tank(station=station)
    )
    form = TankForm(request.POST or None, instance=tank, station=station)
    form.instance.station = station
    if request.method == "POST" and form.is_valid():
        tank = form.save(commit=False)
        tank.station = station
        tank.full_clean()
        tank.save()
        messages.success(request, "Tank saved.")
        return redirect("station_settings")
    return render(
        request,
        "frontend/settings/catalog_form.html",
        {
            "page_title": "Edit Tank" if pk else "Add Tank",
            "station": station,
            "form": form,
            "entity_label": "Tank",
            "submit_label": "Save Tank",
            "cancel_url": reverse("station_settings"),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def pump_edit(request, pk=None):
    station = permitted_current_station(request, MANAGE_CATALOG)
    pump = (
        get_object_or_404(Pump, pk=pk, station=station)
        if pk is not None
        else Pump(station=station)
    )
    form = PumpForm(request.POST or None, instance=pump, station=station)
    form.instance.station = station
    if request.method == "POST" and form.is_valid():
        pump = form.save(commit=False)
        pump.station = station
        pump.full_clean()
        pump.save()
        messages.success(request, "Pump saved.")
        return redirect("station_settings")
    return render(
        request,
        "frontend/settings/catalog_form.html",
        {
            "page_title": "Edit Pump" if pk else "Add Pump",
            "station": station,
            "form": form,
            "entity_label": "Pump",
            "submit_label": "Save Pump",
            "cancel_url": reverse("station_settings"),
        },
    )


@login_required
def suppliers(request):
    station = permitted_current_station(request, MANAGE_CATALOG)
    return render(
        request,
        "frontend/settings/suppliers.html",
        {
            "page_title": "Suppliers",
            "station": station,
            "suppliers": station.suppliers.all(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def supplier_edit(request, pk=None):
    station = permitted_current_station(request, MANAGE_CATALOG)
    supplier = (
        get_object_or_404(Supplier, pk=pk, station=station)
        if pk is not None
        else Supplier(station=station)
    )
    form = SupplierForm(request.POST or None, instance=supplier, station=station)
    form.instance.station = station
    if request.method == "POST" and form.is_valid():
        supplier = form.save(commit=False)
        supplier.station = station
        supplier.full_clean()
        supplier.save()
        messages.success(request, "Supplier saved.")
        return redirect("suppliers")
    return render(
        request,
        "frontend/settings/catalog_form.html",
        {
            "page_title": "Edit Supplier" if pk else "Add Supplier",
            "station": station,
            "form": form,
            "entity_label": "Supplier",
            "submit_label": "Save Supplier",
            "cancel_url": reverse("suppliers"),
        },
    )


@login_required
def inventory(request):
    station = permitted_current_station(request, VIEW_INVENTORY)
    tanks = station.tanks.select_related("fuel_product").all()
    return render(
        request,
        "frontend/inventory.html",
        {
            "page_title": "Fuel Inventory",
            "station": station,
            "tanks": tanks,
            "deliveries": station.fuel_deliveries.select_related(
                "fuel_product",
                "tank",
                "supplier",
                "received_by",
            )[:25],
            "adjustments": station.inventory_adjustments.select_related(
                "tank",
                "tank__fuel_product",
                "encoded_by",
                "approved_by",
            )[:25],
            "can_create_adjustments": user_has_station_permission(
                request.user,
                station,
                CREATE_ADJUSTMENTS,
            ),
            "can_approve_adjustments": user_has_station_permission(
                request.user,
                station,
                APPROVE_ADJUSTMENTS,
            ),
            "can_add_delivery": user_has_station_permission(
                request.user,
                station,
                MANAGE_DELIVERIES,
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def inventory_adjustment_create(request):
    station = permitted_current_station(request, CREATE_ADJUSTMENTS)
    adjustment = InventoryAdjustment(station=station, encoded_by=request.user)
    form = InventoryAdjustmentForm(
        request.POST or None,
        instance=adjustment,
        station=station,
        initial={"adjustment_date": timezone.localdate()},
    )
    form.instance.station = station
    form.instance.encoded_by = request.user
    if request.method == "POST" and form.is_valid():
        adjustment = form.save(commit=False)
        adjustment.station = station
        adjustment.encoded_by = request.user
        adjustment.full_clean()
        adjustment.save()
        AuditLog.objects.create(
            user=request.user,
            action="inventory_adjustment_requested",
            model_name="InventoryAdjustment",
            object_id=str(adjustment.pk),
            new_value={
                "station": station.name,
                "tank": adjustment.tank.name,
                "type": adjustment.adjustment_type,
                "liters": str(adjustment.liters),
            },
        )
        messages.success(request, "Inventory adjustment submitted for approval.")
        return redirect("inventory")
    return render(
        request,
        "frontend/inventory_adjustment_form.html",
        {
            "page_title": "Inventory Adjustment",
            "station": station,
            "form": form,
        },
    )


@login_required
@require_POST
def inventory_adjustment_approve(request, pk):
    station = permitted_current_station(request, APPROVE_ADJUSTMENTS)
    adjustment = get_object_or_404(
        InventoryAdjustment.objects.select_related("tank"),
        pk=pk,
        station=station,
        applied_at=None,
    )
    try:
        adjustment.apply(request.user)
    except ValidationError as error:
        messages.error(
            request,
            error.message_dict if hasattr(error, "message_dict") else error.messages,
        )
    else:
        AuditLog.objects.create(
            user=request.user,
            action="inventory_adjustment_applied",
            model_name="InventoryAdjustment",
            object_id=str(adjustment.pk),
            new_value={
                "tank": adjustment.tank.name,
                "type": adjustment.adjustment_type,
                "liters": str(adjustment.liters),
            },
        )
        messages.success(request, "Inventory adjustment approved and applied.")
    return redirect("inventory")


@login_required
def dashboard(request):
    station = get_current_station(request.user)
    tanks = Tank.objects.filter(station=station).select_related("fuel_product") if station else []
    metrics = dashboard_metrics(station) if station else {}
    recent_operations = (
        DailyOperation.objects.filter(station=station)
        .select_related("station", "encoded_by", "approved_by")
        .order_by("-operation_date")[:6]
        if station
        else []
    )

    alerts = []
    for tank in tanks:
        if tank.is_low_stock:
            alerts.append(
                {
                    "level": "warning",
                    "title": f"{tank.fuel_product.name} low stock",
                    "message": f"{tank.name} is at {tank.current_volume_liters} liters.",
                }
            )

    if station and metrics.get("today_shortage", ZERO) > ZERO:
        alerts.append(
            {
                "level": "danger",
                "title": "Cash shortage detected",
                "message": f"Today's remittance is short by PHP {metrics['today_shortage']:.2f}.",
            }
        )

    if station and not DailyOperation.objects.filter(
        station=station,
        operation_date=metrics.get("today"),
    ).exists():
        alerts.append(
            {
                "level": "warning",
                "title": "Daily operation not started",
                "message": "Create today's sales record before closing the shift.",
            }
        )

    return render(
        request,
        "frontend/dashboard.html",
        {
            "page_title": "Dashboard",
            "station": station,
            "tanks": tanks,
            "metrics": metrics,
            "alerts": alerts,
            "recent_operations": recent_operations,
            "can_view_reports": bool(
                station
                and user_has_station_permission(request.user, station, VIEW_REPORTS)
            ),
        },
    )


@login_required
def daily_operations(request):
    station = permitted_current_station(request, ENCODE_OPERATIONS)
    operations = (
        DailyOperation.objects.filter(station=station)
        .select_related("station", "encoded_by", "approved_by")
        .order_by("-operation_date")
        if station
        else []
    )
    return render(
        request,
        "frontend/daily_operations.html",
        {
            "page_title": "Daily Sales",
            "station": station,
            "operations": operations,
        },
    )


@login_required
def daily_operation_create(request):
    allowed_stations = stations_for_user_with_permission(
        request.user,
        ENCODE_OPERATIONS,
    )
    if request.method == "POST":
        form = DailyOperationForm(request.POST, stations=allowed_stations)
        if form.is_valid():
            operation = form.save(commit=False)
            operation.encoded_by = request.user
            operation.save()
            messages.success(request, "Daily operation created.")
            return redirect("daily_operation_detail", pk=operation.pk)
    else:
        initial = {"operation_date": timezone.localdate()}
        station = get_current_station(request.user)
        if station:
            initial["station"] = station
        form = DailyOperationForm(initial=initial, stations=allowed_stations)

    return render(
        request,
        "frontend/daily_operation_form.html",
        {
            "page_title": "New Daily Sale",
            "form": form,
        },
    )


@login_required
def daily_operation_detail(request, pk):
    operation = get_object_or_404(
        DailyOperation.objects.filter(
            station__in=stations_for_user_with_permission(
                request.user,
                ENCODE_OPERATIONS,
            )
        ).select_related(
            "station",
            "encoded_by",
            "approved_by",
        ),
        pk=pk,
    )
    reading_form = PumpReadingForm(station=operation.station, daily_operation=operation)
    collection_instance = getattr(operation, "cash_collection", None)
    collection_form = CashCollectionForm(instance=collection_instance)

    if request.method == "POST":
        action = request.POST.get("action")

        if action in {"add_reading", "save_collection"} and not operation.is_editable:
            messages.error(
                request,
                "Readings and collections can only change while the operation is draft or rejected.",
            )
            return redirect("daily_operation_detail", pk=operation.pk)

        if action == "add_reading":
            reading_form = PumpReadingForm(
                request.POST,
                station=operation.station,
                daily_operation=operation,
            )
            if reading_form.is_valid():
                reading = reading_form.save(commit=False)
                reading.daily_operation = operation
                reading.save()
                messages.success(request, "Pump reading added.")
                return redirect("daily_operation_detail", pk=operation.pk)

        elif action == "save_collection":
            collection_form = CashCollectionForm(request.POST, instance=collection_instance)
            if collection_form.is_valid():
                collection = collection_form.save(commit=False)
                collection.daily_operation = operation
                collection.save()
                messages.success(request, "Cash collection saved.")
                return redirect("daily_operation_detail", pk=operation.pk)

        elif action == "submit":
            try:
                operation.submit()
            except ValidationError as error:
                messages.error(
                    request,
                    error.message_dict if hasattr(error, "message_dict") else error.messages,
                )
            else:
                AuditLog.objects.create(
                    user=request.user,
                    action="daily_operation_submitted",
                    model_name="DailyOperation",
                    object_id=str(operation.pk),
                    new_value={"status": operation.status},
                )
                messages.success(request, "Daily operation submitted for review.")
            return redirect("daily_operation_detail", pk=operation.pk)

        elif action == "approve":
            if not user_can_approve(request.user, operation.station):
                messages.error(request, "Only owners and managers can approve operations.")
                return redirect("daily_operation_detail", pk=operation.pk)
            try:
                operation.approve(request.user)
            except ValidationError as error:
                messages.error(request, error.message_dict if hasattr(error, "message_dict") else error.messages)
            else:
                AuditLog.objects.create(
                    user=request.user,
                    action="daily_operation_approved",
                    model_name="DailyOperation",
                    object_id=str(operation.pk),
                    new_value={
                        "status": operation.status,
                        "inventory_deducted_at": operation.inventory_deducted_at.isoformat(),
                    },
                )
                messages.success(request, "Daily operation approved and inventory deducted.")
            return redirect("daily_operation_detail", pk=operation.pk)

        elif action == "reject":
            if not user_can_approve(request.user, operation.station):
                messages.error(request, "Only owners and managers can reject operations.")
                return redirect("daily_operation_detail", pk=operation.pk)
            reason = request.POST.get("rejection_reason", "")
            try:
                operation.reject(request.user, reason)
            except ValidationError as error:
                messages.error(
                    request,
                    error.message_dict if hasattr(error, "message_dict") else error.messages,
                )
            else:
                AuditLog.objects.create(
                    user=request.user,
                    action="daily_operation_rejected",
                    model_name="DailyOperation",
                    object_id=str(operation.pk),
                    new_value={"status": operation.status, "reason": reason.strip()},
                )
                messages.success(request, "Daily operation rejected for correction.")
            return redirect("daily_operation_detail", pk=operation.pk)

        elif action == "reopen":
            if not user_can_approve(request.user, operation.station):
                messages.error(request, "Only owners and managers can reopen operations.")
                return redirect("daily_operation_detail", pk=operation.pk)
            reason = request.POST.get("reopen_reason", "")
            try:
                operation.reopen(request.user, reason)
            except ValidationError as error:
                messages.error(
                    request,
                    error.message_dict if hasattr(error, "message_dict") else error.messages,
                )
            else:
                AuditLog.objects.create(
                    user=request.user,
                    action="daily_operation_reopened",
                    model_name="DailyOperation",
                    object_id=str(operation.pk),
                    new_value={"status": operation.status, "reason": reason.strip()},
                )
                messages.success(
                    request,
                    "Operation reopened and the previous inventory deduction was reversed.",
                )
            return redirect("daily_operation_detail", pk=operation.pk)

    readings = operation.readings.select_related("pump", "pump__fuel_product").order_by("pump__name")

    return render(
        request,
        "frontend/daily_operation_detail.html",
        {
            "page_title": "Daily Sale Detail",
            "operation": operation,
            "readings": readings,
            "reading_form": reading_form,
            "collection_form": collection_form,
            "collection": collection_instance,
            "can_approve": user_can_approve(request.user, operation.station),
            "is_editable": operation.is_editable,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def pump_reading_edit(request, operation_pk, reading_pk):
    operation = get_object_or_404(
        DailyOperation.objects.filter(
            station__in=stations_for_user_with_permission(
                request.user,
                ENCODE_OPERATIONS,
            )
        ),
        pk=operation_pk,
    )
    reading = get_object_or_404(
        PumpReading,
        pk=reading_pk,
        daily_operation=operation,
    )
    if not operation.is_editable:
        messages.error(
            request,
            "Readings can only be corrected while the operation is draft or rejected.",
        )
        return redirect("daily_operation_detail", pk=operation.pk)

    form = PumpReadingForm(
        request.POST or None,
        instance=reading,
        station=operation.station,
        daily_operation=operation,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pump reading corrected and collection variance recalculated.")
        return redirect("daily_operation_detail", pk=operation.pk)

    return render(
        request,
        "frontend/pump_reading_form.html",
        {
            "page_title": "Correct Pump Reading",
            "station": operation.station,
            "operation": operation,
            "form": form,
        },
    )


@login_required
def fuel_deliveries(request):
    station = permitted_current_station(request, MANAGE_DELIVERIES)
    deliveries = FuelDelivery.objects.filter(
        station__in=stations_for_user_with_permission(
            request.user,
            MANAGE_DELIVERIES,
        )
    ).select_related(
        "station",
        "fuel_product",
        "tank",
        "supplier",
        "received_by",
    ).order_by("-delivery_date")[:100]
    return render(
        request,
        "frontend/fuel_deliveries.html",
        {
            "page_title": "Fuel Refill",
            "station": station,
            "deliveries": deliveries,
        },
    )


@login_required
def fuel_delivery_create(request):
    station = permitted_current_station(request, MANAGE_DELIVERIES)
    allowed_stations = stations_for_user_with_permission(
        request.user,
        MANAGE_DELIVERIES,
    )
    if request.method == "POST":
        form = FuelDeliveryForm(request.POST, stations=allowed_stations)
        if form.is_valid():
            delivery = form.save(commit=False)
            delivery.received_by = request.user
            try:
                delivery.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, "Fuel delivery saved and tank inventory updated.")
                return redirect("fuel_deliveries")
    else:
        initial = {"delivery_date": timezone.localdate()}
        if station:
            initial["station"] = station
        form = FuelDeliveryForm(initial=initial, stations=allowed_stations)

    return render(
        request,
        "frontend/fuel_delivery_form.html",
        {
            "page_title": "Add Fuel Refill",
            "form": form,
        },
    )


@login_required
def expenses(request):
    station = permitted_current_station(request, MANAGE_EXPENSES)
    items = Expense.objects.filter(
        station__in=stations_for_user_with_permission(
            request.user,
            MANAGE_EXPENSES,
        )
    ).select_related(
        "station",
        "category",
        "encoded_by",
    ).order_by("-expense_date")[:100]
    return render(
        request,
        "frontend/expenses.html",
        {
            "page_title": "Expenses",
            "station": station,
            "expenses": items,
        },
    )


@login_required
def expense_create(request):
    station = permitted_current_station(request, MANAGE_EXPENSES)
    allowed_stations = stations_for_user_with_permission(
        request.user,
        MANAGE_EXPENSES,
    )
    if request.method == "POST":
        form = ExpenseForm(request.POST, stations=allowed_stations)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.encoded_by = request.user
            expense.save()
            messages.success(request, "Expense saved.")
            return redirect("expenses")
    else:
        initial = {"expense_date": timezone.localdate()}
        if station:
            initial["station"] = station
        form = ExpenseForm(initial=initial, stations=allowed_stations)

    return render(
        request,
        "frontend/expense_form.html",
        {
            "page_title": "Add Expense",
            "form": form,
        },
    )


@login_required
def reports(request):
    station = permitted_current_station(request, VIEW_REPORTS)
    stations = stations_for_user_with_permission(request.user, VIEW_REPORTS)
    selected_station_id = request.GET.get("station")
    if selected_station_id:
        station = stations.filter(pk=selected_station_id).first() or station

    today = timezone.localdate()
    report_date_value = request.GET.get("date") or today.isoformat()
    try:
        report_date = date.fromisoformat(report_date_value)
    except ValueError:
        report_date = today

    month_value = request.GET.get("month") or today.strftime("%Y-%m")
    month_start, month_end = month_bounds(month_value)

    daily_operations_for_date = DailyOperation.objects.filter(
        station=station,
        status=DailyOperation.Status.APPROVED,
        operation_date=report_date,
    ).select_related("station", "encoded_by", "approved_by") if station else []

    monthly_readings = PumpReading.objects.filter(
        daily_operation__station=station,
        daily_operation__status=DailyOperation.Status.APPROVED,
        daily_operation__operation_date__gte=month_start,
        daily_operation__operation_date__lt=month_end,
    ) if station else []
    monthly_expected_sales = sum((item.expected_sales for item in monthly_readings), ZERO)
    monthly_liters = sum((item.liters_sold for item in monthly_readings), ZERO)
    monthly_fuel_cost = sum(
        (item.liters_sold * item.cost_per_liter for item in monthly_readings),
        ZERO,
    )
    monthly_expenses = decimal_or_zero(
        Expense.objects.filter(
            station=station,
            expense_date__gte=month_start,
            expense_date__lt=month_end,
        ).aggregate(total=Sum("amount"))["total"]
    ) if station else ZERO
    monthly_shortage = sum(
        (
            item.shortage
            for item in CashCollection.objects.filter(
                daily_operation__station=station,
                daily_operation__status=DailyOperation.Status.APPROVED,
                daily_operation__operation_date__gte=month_start,
                daily_operation__operation_date__lt=month_end,
            )
        ),
        ZERO,
    ) if station else ZERO
    monthly_overage = sum(
        (
            item.overage
            for item in CashCollection.objects.filter(
                daily_operation__station=station,
                daily_operation__status=DailyOperation.Status.APPROVED,
                daily_operation__operation_date__gte=month_start,
                daily_operation__operation_date__lt=month_end,
            )
        ),
        ZERO,
    ) if station else ZERO
    gross_profit = monthly_expected_sales - monthly_fuel_cost
    net_profit = gross_profit - monthly_expenses

    expense_categories = (
        Expense.objects.filter(
            station=station,
            expense_date__gte=month_start,
            expense_date__lt=month_end,
        )
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("category__name")
        if station
        else []
    )

    return render(
        request,
        "frontend/reports.html",
        {
            "page_title": "Reports",
            "station": station,
            "stations": stations,
            "report_date": report_date,
            "month_value": month_start.strftime("%Y-%m"),
            "daily_operations": daily_operations_for_date,
            "expense_categories": expense_categories,
            "summary": {
                "monthly_liters": monthly_liters,
                "monthly_expected_sales": monthly_expected_sales,
                "monthly_fuel_cost": monthly_fuel_cost,
                "gross_profit": gross_profit,
                "monthly_expenses": monthly_expenses,
                "net_profit": net_profit,
                "monthly_shortage": monthly_shortage,
                "monthly_overage": monthly_overage,
            },
        },
    )
