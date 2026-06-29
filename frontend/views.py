import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from api.models import (
    AuditLog,
    CashCollection,
    DailyOperation,
    Expense,
    ExpenseCategory,
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
    ExpenseCategoryForm,
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
    current_station_for_request,
    require_station_permission,
    stations_for_user,
    stations_for_user_with_permission,
    user_has_station_permission,
)
from .audit import log_audit
from .guides import GUIDE_VERSION, VALID_GUIDE_KEYS
from .models import GuidedTourProgress
from .security import request_is_rate_limited
from .services.reporting import build_report, date_range, month_bounds, with_operation_totals
from .services.report_exports import (
    REPORT_FORMATS,
    REPORT_TYPES,
    build_sections,
    render_csv,
    render_pdf,
    report_filename,
    report_metadata,
)
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


def paginate(request, queryset, *, page_param="page", per_page=20):
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get(page_param))
    query = request.GET.copy()
    query.pop(page_param, None)
    return page_obj, query.urlencode()


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
    station = get_current_station(request)
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
    station = get_current_station(request)
    if not station:
        raise PermissionDenied
    require_station_permission(request.user, station, MANAGE_TEAM)

    action = request.POST.get("action") if request.method == "POST" else None

    if action in {"change_role", "suspend_member", "reactivate_member"}:
        with transaction.atomic():
            membership = get_object_or_404(
                StationMembership.objects.select_for_update().select_related("user"),
                pk=request.POST.get("membership_id"),
                station=station,
            )
            actor = station.memberships.filter(
                user=request.user,
                status=StationMembership.Status.ACTIVE,
            ).first()
            actor_role = (
                StationMembership.Role.OWNER
                if request.user.is_superuser
                else getattr(actor, "role", None)
            )
            if not actor_role:
                raise PermissionDenied
            if membership.role == StationMembership.Role.OWNER and actor_role != StationMembership.Role.OWNER:
                raise PermissionDenied
            if action == "suspend_member" and membership.user_id == request.user.id:
                messages.error(request, "You cannot suspend your own access.")
                return redirect("team_members")

            old_value = {"role": membership.role, "status": membership.status}
            if action == "change_role":
                new_role = request.POST.get("role")
                if new_role not in StationMembership.Role.values:
                    messages.error(request, "Select a valid member role.")
                    return redirect("team_members")
                if new_role == StationMembership.Role.OWNER and actor_role != StationMembership.Role.OWNER:
                    raise PermissionDenied
                if (
                    membership.role == StationMembership.Role.OWNER
                    and new_role != StationMembership.Role.OWNER
                    and membership.status == StationMembership.Status.ACTIVE
                    and station.memberships.filter(
                        role=StationMembership.Role.OWNER,
                        status=StationMembership.Status.ACTIVE,
                    ).count() <= 1
                ):
                    messages.error(request, "The station must keep at least one active owner.")
                    return redirect("team_members")
                membership.role = new_role
                membership.save(update_fields=["role", "updated_at"])
                event = "station_member_role_changed"
                message = "Team member role updated."
            elif action == "suspend_member":
                if (
                    membership.role == StationMembership.Role.OWNER
                    and membership.status == StationMembership.Status.ACTIVE
                    and station.memberships.filter(
                        role=StationMembership.Role.OWNER,
                        status=StationMembership.Status.ACTIVE,
                    ).count() <= 1
                ):
                    messages.error(request, "The last active owner cannot be suspended.")
                    return redirect("team_members")
                membership.status = StationMembership.Status.SUSPENDED
                membership.save(update_fields=["status", "updated_at"])
                event = "station_member_suspended"
                message = "Team member suspended."
            else:
                if membership.status != StationMembership.Status.SUSPENDED:
                    messages.error(request, "Only suspended members can be reactivated.")
                    return redirect("team_members")
                membership.status = StationMembership.Status.ACTIVE
                membership.save(update_fields=["status", "updated_at"])
                event = "station_member_reactivated"
                message = "Team member reactivated."

            if station.owner_id == membership.user_id and (
                membership.role != StationMembership.Role.OWNER
                or membership.status != StationMembership.Status.ACTIVE
            ):
                replacement = station.memberships.filter(
                    role=StationMembership.Role.OWNER,
                    status=StationMembership.Status.ACTIVE,
                ).exclude(pk=membership.pk).select_related("user").first()
                station.owner = replacement.user
                station.save(update_fields=["owner", "updated_at"])

            log_audit(
                request.user,
                event,
                membership,
                old_value=old_value,
                new_value={"role": membership.role, "status": membership.status},
            )
        messages.success(request, message)
        return redirect("team_members")

    if action == "revoke_invitation":
        invitation = get_object_or_404(
            StationInvitation,
            pk=request.POST.get("invitation_id"),
            station=station,
            accepted_at=None,
            revoked_at=None,
        )
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at", "updated_at"])
        log_audit(
            request.user,
            "station_invitation_revoked",
            invitation,
            new_value={"email": invitation.email, "role": invitation.role},
        )
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

    members, members_query = paginate(
        request,
        station.memberships.select_related("user", "invited_by").order_by(
            "role",
            "user__username",
        ),
    )
    return render(
        request,
        "frontend/team.html",
        {
            "page_title": "Team",
            "station": station,
            "form": form,
            "members": members,
            "members_query": members_query,
            "can_manage_owners": request.user.is_superuser
            or station.memberships.filter(
                user=request.user,
                role=StationMembership.Role.OWNER,
                status=StationMembership.Status.ACTIVE,
            ).exists(),
            "invitations": station.invitations.filter(
                accepted_at=None,
                revoked_at=None,
                expires_at__gt=timezone.now(),
            ),
            "role_choices": StationMembership.Role.choices,
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
        request.session["active_station_id"] = invitation.station_id
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
            request.session["active_station_id"] = invitation.station_id
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


def get_current_station(request):
    return current_station_for_request(request)


def dashboard_metrics(station):
    today = timezone.localdate()
    month_start = today.replace(day=1)

    today_readings = PumpReading.objects.filter(
        daily_operation__station=station,
        daily_operation__operation_date=today,
        daily_operation__is_archived=False,
        is_archived=False,
    ).select_related("pump__fuel_product")
    today_collections = CashCollection.objects.filter(
        daily_operation__station=station,
        daily_operation__operation_date=today,
        daily_operation__is_archived=False,
    )
    monthly_readings = PumpReading.objects.filter(
        daily_operation__station=station,
        daily_operation__status=DailyOperation.Status.APPROVED,
        daily_operation__operation_date__gte=month_start,
        daily_operation__operation_date__lte=today,
        daily_operation__is_archived=False,
        is_archived=False,
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
            is_archived=False,
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
    station = get_current_station(request)
    if not station:
        raise PermissionDenied
    require_station_permission(request.user, station, permission)
    return station


@login_required
@require_POST
def switch_station(request):
    station = get_object_or_404(
        stations_for_user(request.user),
        pk=request.POST.get("station_id"),
    )
    previous_id = request.session.get("active_station_id")
    request.session["active_station_id"] = station.pk
    log_audit(
        request.user,
        "active_station_switched",
        station,
        old_value={"station_id": previous_id},
        new_value={"station_id": station.pk},
    )
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("dashboard")
    return redirect(next_url)


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
    suppliers_page, suppliers_query = paginate(
        request,
        station.suppliers.order_by("name"),
    )
    return render(
        request,
        "frontend/settings/suppliers.html",
        {
            "page_title": "Suppliers",
            "station": station,
            "suppliers": suppliers_page,
            "suppliers_query": suppliers_query,
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
    deliveries, deliveries_query = paginate(
        request,
        station.fuel_deliveries.filter(is_archived=False)
        .select_related("fuel_product", "tank", "supplier", "received_by")
        .order_by("-delivery_date", "-pk"),
        page_param="delivery_page",
        per_page=10,
    )
    adjustments, adjustments_query = paginate(
        request,
        station.inventory_adjustments.select_related(
            "tank",
            "tank__fuel_product",
            "encoded_by",
            "approved_by",
        ).order_by("-adjustment_date", "-pk"),
        page_param="adjustment_page",
        per_page=10,
    )
    return render(
        request,
        "frontend/inventory.html",
        {
            "page_title": "Fuel Inventory",
            "station": station,
            "tanks": tanks,
            "deliveries": deliveries,
            "deliveries_query": deliveries_query,
            "adjustments": adjustments,
            "adjustments_query": adjustments_query,
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
    station = get_current_station(request)
    tanks = Tank.objects.filter(station=station).select_related("fuel_product") if station else []
    metrics = dashboard_metrics(station) if station else {}
    recent_operations = (
        DailyOperation.objects.filter(station=station, is_archived=False)
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
        is_archived=False,
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
    operations, operations_query = paginate(
        request,
        with_operation_totals(
            DailyOperation.objects.filter(station=station, is_archived=False)
        )
        .order_by("-operation_date", "-pk"),
    )
    return render(
        request,
        "frontend/daily_operations.html",
        {
            "page_title": "Daily Sales",
            "station": station,
            "operations": operations,
            "operations_query": operations_query,
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
            log_audit(
                request.user,
                "daily_operation_created",
                operation,
                new_value={"station": operation.station_id, "date": operation.operation_date},
            )
            messages.success(request, "Daily operation created.")
            return redirect("daily_operation_detail", pk=operation.pk)
    else:
        initial = {"operation_date": timezone.localdate()}
        station = get_current_station(request)
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
        ).filter(is_archived=False),
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
                log_audit(
                    request.user,
                    "pump_reading_created",
                    reading,
                    new_value={
                        "pump": reading.pump_id,
                        "opening": reading.opening_reading,
                        "closing": reading.closing_reading,
                        "liters": reading.liters_sold,
                        "expected_sales": reading.expected_sales,
                    },
                )
                messages.success(request, "Pump reading added.")
                return redirect("daily_operation_detail", pk=operation.pk)

        elif action == "save_collection":
            collection_form = CashCollectionForm(request.POST, instance=collection_instance)
            if collection_form.is_valid():
                collection = collection_form.save(commit=False)
                collection.daily_operation = operation
                collection.save()
                log_audit(
                    request.user,
                    "cash_collection_saved",
                    collection,
                    new_value={
                        "actual_cash": collection.actual_cash,
                        "transfer": collection.gcash_or_bank_transfer,
                        "card": collection.card_payments,
                        "credit": collection.credit_sales,
                        "shortage": collection.shortage,
                        "overage": collection.overage,
                    },
                )
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

        elif action == "archive_operation":
            reason = request.POST.get("archive_reason", "")
            try:
                operation.archive(request.user, reason)
            except ValidationError as error:
                messages.error(
                    request,
                    error.message_dict if hasattr(error, "message_dict") else error.messages,
                )
                return redirect("daily_operation_detail", pk=operation.pk)
            log_audit(
                request.user,
                "daily_operation_archived",
                operation,
                old_value={"status": operation.status},
                new_value={"reason": operation.archive_reason},
            )
            messages.success(request, "Daily operation archived. Its financial records were preserved.")
            return redirect("daily_operations")

    readings = operation.readings.filter(is_archived=False).select_related("pump", "pump__fuel_product").order_by("pump__name")

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
            ),
            is_archived=False,
        ),
        pk=operation_pk,
    )
    reading = get_object_or_404(
        PumpReading,
        pk=reading_pk,
        daily_operation=operation,
        is_archived=False,
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
        old_value = {
            "pump": reading.pump_id,
            "opening": reading.opening_reading,
            "closing": reading.closing_reading,
            "price": reading.price_per_liter,
        }
        reading = form.save()
        log_audit(
            request.user,
            "pump_reading_edited",
            reading,
            old_value=old_value,
            new_value={
                "pump": reading.pump_id,
                "opening": reading.opening_reading,
                "closing": reading.closing_reading,
                "price": reading.price_per_liter,
                "liters": reading.liters_sold,
                "expected_sales": reading.expected_sales,
            },
        )
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
@require_POST
def pump_reading_archive(request, operation_pk, reading_pk):
    operation = get_object_or_404(
        DailyOperation.objects.filter(
            station__in=stations_for_user_with_permission(request.user, ENCODE_OPERATIONS),
            is_archived=False,
        ),
        pk=operation_pk,
    )
    reading = get_object_or_404(
        PumpReading,
        pk=reading_pk,
        daily_operation=operation,
        is_archived=False,
    )
    try:
        reading.archive(request.user, request.POST.get("archive_reason", ""))
    except ValidationError as error:
        messages.error(
            request,
            error.message_dict if hasattr(error, "message_dict") else error.messages,
        )
    else:
        log_audit(
            request.user,
            "pump_reading_archived",
            reading,
            old_value={"liters": reading.liters_sold, "expected_sales": reading.expected_sales},
            new_value={"reason": reading.archive_reason},
        )
        messages.success(request, "Pump reading archived and collection variance recalculated.")
    return redirect("daily_operation_detail", pk=operation.pk)


@login_required
def fuel_deliveries(request):
    station = permitted_current_station(request, MANAGE_DELIVERIES)
    deliveries, deliveries_query = paginate(
        request,
        FuelDelivery.objects.filter(
            station=station,
            is_archived=False,
        ).select_related(
            "station",
            "fuel_product",
            "tank",
            "supplier",
            "received_by",
        ).order_by("-delivery_date", "-pk"),
    )
    return render(
        request,
        "frontend/fuel_deliveries.html",
        {
            "page_title": "Fuel Refill",
            "station": station,
            "deliveries": deliveries,
            "deliveries_query": deliveries_query,
        },
    )


@login_required
def fuel_delivery_create(request):
    station = permitted_current_station(request, MANAGE_DELIVERIES)
    allowed_stations = Station.objects.filter(pk=station.pk)
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
                log_audit(
                    request.user,
                    "fuel_delivery_created",
                    delivery,
                    new_value={
                        "station": delivery.station_id,
                        "tank": delivery.tank_id,
                        "liters": delivery.liters_delivered,
                        "cost_per_liter": delivery.cost_per_liter,
                        "total_cost": delivery.total_cost,
                    },
                )
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
@require_http_methods(["GET", "POST"])
def fuel_delivery_edit(request, pk):
    station = permitted_current_station(request, MANAGE_DELIVERIES)
    delivery = get_object_or_404(FuelDelivery, pk=pk, station=station, is_archived=False)
    old_value = {
        "tank": delivery.tank_id,
        "liters": delivery.liters_delivered,
        "cost_per_liter": delivery.cost_per_liter,
        "total_cost": delivery.total_cost,
    }
    form = FuelDeliveryForm(
        request.POST or None,
        instance=delivery,
        stations=Station.objects.filter(pk=station.pk),
    )
    if request.method == "POST" and form.is_valid():
        delivery = form.save(commit=False)
        try:
            delivery.save()
        except ValidationError as error:
            form.add_error(None, error)
        else:
            log_audit(
                request.user,
                "fuel_delivery_edited",
                delivery,
                old_value=old_value,
                new_value={
                    "tank": delivery.tank_id,
                    "liters": delivery.liters_delivered,
                    "cost_per_liter": delivery.cost_per_liter,
                    "total_cost": delivery.total_cost,
                },
            )
            messages.success(request, "Fuel delivery corrected and tank inventory recalculated.")
            return redirect("fuel_deliveries")
    return render(
        request,
        "frontend/fuel_delivery_form.html",
        {"page_title": "Correct Fuel Refill", "form": form, "editing": True},
    )


@login_required
@require_POST
def fuel_delivery_archive(request, pk):
    station = permitted_current_station(request, MANAGE_DELIVERIES)
    delivery = get_object_or_404(FuelDelivery, pk=pk, station=station, is_archived=False)
    old_value = {
        "tank": delivery.tank_id,
        "liters": delivery.liters_delivered,
        "total_cost": delivery.total_cost,
    }
    try:
        delivery.archive(request.user, request.POST.get("archive_reason", ""))
    except ValidationError as error:
        messages.error(
            request,
            error.message_dict if hasattr(error, "message_dict") else error.messages,
        )
    else:
        log_audit(
            request.user,
            "fuel_delivery_archived",
            delivery,
            old_value=old_value,
            new_value={"reason": delivery.archive_reason, "inventory_reversed": True},
        )
        messages.success(request, "Fuel delivery archived and its tank increase reversed.")
    return redirect("fuel_deliveries")


@login_required
def expenses(request):
    station = permitted_current_station(request, MANAGE_EXPENSES)
    items, expenses_query = paginate(
        request,
        Expense.objects.filter(
            station=station,
            is_archived=False,
        ).select_related(
            "station",
            "category",
            "encoded_by",
        ).order_by("-expense_date", "-pk"),
    )
    return render(
        request,
        "frontend/expenses.html",
        {
            "page_title": "Expenses",
            "station": station,
            "expenses": items,
            "expenses_query": expenses_query,
        },
    )


@login_required
def expense_categories(request):
    station = permitted_current_station(request, MANAGE_CATALOG)
    station_categories, categories_query = paginate(
        request,
        station.expense_categories.order_by("name"),
    )
    return render(
        request,
        "frontend/expense_categories.html",
        {
            "page_title": "Expense Categories",
            "station": station,
            "system_categories": ExpenseCategory.objects.filter(station__isnull=True),
            "station_categories": station_categories,
            "categories_query": categories_query,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def expense_category_edit(request, pk=None):
    station = permitted_current_station(request, MANAGE_CATALOG)
    category = (
        get_object_or_404(ExpenseCategory, pk=pk, station=station)
        if pk is not None
        else ExpenseCategory(station=station)
    )
    old_value = (
        {
            "name": category.name,
            "description": category.description,
            "is_active": category.is_active,
        }
        if category.pk
        else {}
    )
    form = ExpenseCategoryForm(
        request.POST or None,
        instance=category,
        station=station,
    )
    form.instance.station = station
    if request.method == "POST" and form.is_valid():
        category = form.save(commit=False)
        category.station = station
        category.full_clean()
        category.save()
        log_audit(
            request.user,
            "expense_category_updated" if pk else "expense_category_created",
            category,
            old_value=old_value,
            new_value={
                "station": station.pk,
                "name": category.name,
                "description": category.description,
                "is_active": category.is_active,
            },
        )
        messages.success(request, "Expense category saved.")
        return redirect("expense_categories")
    return render(
        request,
        "frontend/settings/catalog_form.html",
        {
            "page_title": "Edit Expense Category" if pk else "Add Expense Category",
            "station": station,
            "form": form,
            "entity_label": "Expense Category",
            "submit_label": "Save Category",
            "cancel_url": reverse("expense_categories"),
        },
    )


@login_required
def expense_create(request):
    station = permitted_current_station(request, MANAGE_EXPENSES)
    allowed_stations = Station.objects.filter(pk=station.pk)
    if request.method == "POST":
        form = ExpenseForm(request.POST, stations=allowed_stations)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.encoded_by = request.user
            expense.save()
            log_audit(
                request.user,
                "expense_created",
                expense,
                new_value={
                    "station": expense.station_id,
                    "category": expense.category_id,
                    "date": expense.expense_date,
                    "amount": expense.amount,
                },
            )
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
@require_http_methods(["GET", "POST"])
def expense_edit(request, pk):
    station = permitted_current_station(request, MANAGE_EXPENSES)
    expense = get_object_or_404(Expense, pk=pk, station=station, is_archived=False)
    old_value = {
        "category": expense.category_id,
        "date": expense.expense_date,
        "amount": expense.amount,
        "vendor": expense.vendor,
        "reference": expense.reference_number,
    }
    form = ExpenseForm(
        request.POST or None,
        instance=expense,
        stations=Station.objects.filter(pk=station.pk),
    )
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.save()
        log_audit(
            request.user,
            "expense_edited",
            expense,
            old_value=old_value,
            new_value={
                "category": expense.category_id,
                "date": expense.expense_date,
                "amount": expense.amount,
                "vendor": expense.vendor,
                "reference": expense.reference_number,
            },
        )
        messages.success(request, "Expense corrected.")
        return redirect("expenses")
    return render(
        request,
        "frontend/expense_form.html",
        {"page_title": "Correct Expense", "form": form, "editing": True},
    )


@login_required
@require_POST
def expense_archive(request, pk):
    station = permitted_current_station(request, MANAGE_EXPENSES)
    expense = get_object_or_404(Expense, pk=pk, station=station, is_archived=False)
    try:
        expense.archive(request.user, request.POST.get("archive_reason", ""))
    except ValidationError as error:
        messages.error(
            request,
            error.message_dict if hasattr(error, "message_dict") else error.messages,
        )
        return redirect("expenses")
    log_audit(
        request.user,
        "expense_archived",
        expense,
        old_value={"amount": expense.amount, "category": expense.category_id},
        new_value={"reason": expense.archive_reason},
    )
    messages.success(request, "Expense archived and removed from official reports.")
    return redirect("expenses")


def report_context(request):
    station = permitted_current_station(request, VIEW_REPORTS)
    stations = stations_for_user_with_permission(request.user, VIEW_REPORTS)
    selected_station_id = request.GET.get("station")
    if selected_station_id:
        station = stations.filter(pk=selected_station_id).first() or station

    today = timezone.localdate()
    date_from, date_to = date_range(
        request.GET.get("date_from") or request.GET.get("date") or today.isoformat(),
        request.GET.get("date_to") or request.GET.get("date") or today.isoformat(),
    )
    month_value = request.GET.get("month") or today.strftime("%Y-%m")
    month_start, month_end = month_bounds(month_value)
    report = build_report(station, date_from, date_to, month_start, month_end)
    return {
        "station": station,
        "stations": stations,
        "date_from": date_from,
        "date_to": date_to,
        "month_value": month_start.strftime("%Y-%m"),
        **report,
    }


@login_required
def reports(request):
    context = report_context(request)
    context["daily_operations"], context["sales_query"] = paginate(
        request,
        context["daily_operations"].order_by("-operation_date", "-pk"),
        page_param="sales_page",
    )
    context["inventory_movements"], context["movements_query"] = paginate(
        request,
        context["inventory_movements"],
        page_param="movement_page",
    )

    return render(
        request,
        "frontend/reports.html",
        {
            "page_title": "Reports",
            "report_types": REPORT_TYPES,
            **context,
        },
    )


@login_required
@require_GET
def report_export(request):
    report_type = request.GET.get("report_type", "comprehensive")
    export_format = request.GET.get("format", "pdf")
    if report_type not in REPORT_TYPES:
        return HttpResponseBadRequest("Unknown report type.")
    if export_format not in REPORT_FORMATS:
        return HttpResponseBadRequest("Unknown report format.")

    context = report_context(request)
    sections = build_sections(report_type, context)
    metadata = report_metadata(
        context["station"],
        report_type,
        context["date_from"],
        context["date_to"],
        context["month_value"],
        request.user,
    )
    if export_format == "csv":
        response = HttpResponse(render_csv(metadata, sections), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{report_filename(context["station"], report_type, "csv")}"'
    elif export_format == "pdf":
        response = HttpResponse(render_pdf(metadata, sections), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{report_filename(context["station"], report_type, "pdf")}"'
    else:
        response = render(
            request,
            "frontend/report_print.html",
            {
                "page_title": metadata["title"],
                "metadata": metadata,
                "sections": sections,
            },
        )
    log_audit(
        request.user,
        "report_generated",
        context["station"],
        new_value={
            "report_type": report_type,
            "format": export_format,
            "date_from": context["date_from"],
            "date_to": context["date_to"],
            "month": context["month_value"],
        },
    )
    return response
