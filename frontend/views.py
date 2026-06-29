import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from api.models import (
    CashCollection,
    DailyOperation,
    Expense,
    FuelDelivery,
    PumpReading,
    Station,
    Tank,
)

from .forms import (
    CashCollectionForm,
    DailyOperationForm,
    ExpenseForm,
    FuelDeliveryForm,
    PumpReadingForm,
)
from .guides import GUIDE_VERSION, VALID_GUIDE_KEYS
from .models import GuidedTourProgress


ZERO = Decimal("0")


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


def user_can_approve(user):
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=["Owner", "Manager"]).exists()


def get_current_station(user):
    owned_station = Station.objects.filter(owner=user, is_active=True).first()
    if owned_station:
        return owned_station
    return Station.objects.filter(is_active=True).first()


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
        daily_operation__operation_date__gte=month_start,
        daily_operation__operation_date__lte=today,
    ).select_related("pump__fuel_product")

    today_expected_sales = sum((item.expected_sales for item in today_readings), ZERO)
    today_liters = sum((item.liters_sold for item in today_readings), ZERO)
    today_collected = sum((item.total_collection for item in today_collections), ZERO)
    today_shortage = sum((item.shortage for item in today_collections), ZERO)
    today_overage = sum((item.overage for item in today_collections), ZERO)
    monthly_expected_sales = sum((item.expected_sales for item in monthly_readings), ZERO)
    monthly_fuel_cost = sum(
        (item.liters_sold * item.pump.fuel_product.cost_per_liter for item in monthly_readings),
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
        },
    )


@login_required
def daily_operations(request):
    station = get_current_station(request.user)
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
    if request.method == "POST":
        form = DailyOperationForm(request.POST)
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
        form = DailyOperationForm(initial=initial)

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
        DailyOperation.objects.select_related("station", "encoded_by", "approved_by"),
        pk=pk,
    )
    reading_form = PumpReadingForm(station=operation.station, daily_operation=operation)
    collection_instance = getattr(operation, "cash_collection", None)
    collection_form = CashCollectionForm(instance=collection_instance)

    if request.method == "POST":
        action = request.POST.get("action")

        if action in {"add_reading", "save_collection", "submit"} and operation.status == DailyOperation.Status.APPROVED:
            messages.error(request, "Approved daily operations cannot be changed.")
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
            operation.submit()
            messages.success(request, "Daily operation submitted for review.")
            return redirect("daily_operation_detail", pk=operation.pk)

        elif action == "approve":
            if not user_can_approve(request.user):
                messages.error(request, "Only owners and managers can approve operations.")
                return redirect("daily_operation_detail", pk=operation.pk)
            try:
                operation.approve(request.user)
            except ValidationError as error:
                messages.error(request, error.message_dict if hasattr(error, "message_dict") else error.messages)
            else:
                messages.success(request, "Daily operation approved and inventory deducted.")
            return redirect("daily_operation_detail", pk=operation.pk)

        elif action == "reject":
            if not user_can_approve(request.user):
                messages.error(request, "Only owners and managers can reject operations.")
                return redirect("daily_operation_detail", pk=operation.pk)
            operation.reject(request.user, request.POST.get("notes", ""))
            messages.success(request, "Daily operation rejected.")
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
            "can_approve": user_can_approve(request.user),
        },
    )


@login_required
def fuel_deliveries(request):
    deliveries = FuelDelivery.objects.select_related(
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
            "deliveries": deliveries,
        },
    )


@login_required
def fuel_delivery_create(request):
    if request.method == "POST":
        form = FuelDeliveryForm(request.POST)
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
        station = get_current_station(request.user)
        if station:
            initial["station"] = station
        form = FuelDeliveryForm(initial=initial)

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
    items = Expense.objects.select_related("station", "category", "encoded_by").order_by("-expense_date")[:100]
    return render(
        request,
        "frontend/expenses.html",
        {
            "page_title": "Expenses",
            "expenses": items,
        },
    )


@login_required
def expense_create(request):
    if request.method == "POST":
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.encoded_by = request.user
            expense.save()
            messages.success(request, "Expense saved.")
            return redirect("expenses")
    else:
        initial = {"expense_date": timezone.localdate()}
        station = get_current_station(request.user)
        if station:
            initial["station"] = station
        form = ExpenseForm(initial=initial)

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
    station = get_current_station(request.user)
    stations = Station.objects.filter(is_active=True)
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
        operation_date=report_date,
    ).select_related("station", "encoded_by", "approved_by") if station else []

    monthly_readings = PumpReading.objects.filter(
        daily_operation__station=station,
        daily_operation__operation_date__gte=month_start,
        daily_operation__operation_date__lt=month_end,
    ).select_related("pump__fuel_product") if station else []
    monthly_expected_sales = sum((item.expected_sales for item in monthly_readings), ZERO)
    monthly_liters = sum((item.liters_sold for item in monthly_readings), ZERO)
    monthly_fuel_cost = sum(
        (item.liters_sold * item.pump.fuel_product.cost_per_liter for item in monthly_readings),
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
