import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from frontend.access import (
    VIEW_REPORTS,
    current_station_for_request,
    require_station_permission,
    stations_for_user,
)
from frontend.services.reporting import build_report, date_range, month_bounds

from .models import liters, money


ZERO = Decimal("0")


def _station(request, require_reports=False):
    station = current_station_for_request(request)
    station_id = request.GET.get("station")
    if station_id:
        station = stations_for_user(request.user).filter(pk=station_id).first()
    if not station:
        raise PermissionDenied
    if require_reports:
        require_station_permission(request.user, station, VIEW_REPORTS)
    return station


def _decimal(value, field_name):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")
    if number < ZERO:
        raise ValueError(f"{field_name} cannot be negative.")
    return number


def _payload(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Request body must be valid JSON.")
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload


def _error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def _summary_json(summary):
    return {key: str(value) for key, value in summary.items()}


@login_required
@require_GET
def dashboard_summary(request):
    station = _station(request)
    today = timezone.localdate()
    month_start, month_end = month_bounds(today.strftime("%Y-%m"))
    report = build_report(station, today, today, month_start, month_end)
    tanks = station.tanks.filter(is_active=True).select_related("fuel_product")
    return JsonResponse(
        {
            "ok": True,
            "station": {"id": station.pk, "name": station.name},
            "date": today.isoformat(),
            "summary": _summary_json(report["summary"]),
            "tanks": [
                {
                    "id": tank.pk,
                    "name": tank.name,
                    "product": tank.fuel_product.name,
                    "current_liters": str(tank.current_volume_liters),
                    "capacity_liters": str(tank.capacity_liters),
                    "low_stock": tank.is_low_stock,
                }
                for tank in tanks
            ],
        }
    )


@login_required
@require_GET
def daily_report(request):
    station = _station(request, require_reports=True)
    today_value = timezone.localdate().isoformat()
    date_from, date_to = date_range(
        request.GET.get("date_from") or request.GET.get("date") or today_value,
        request.GET.get("date_to") or request.GET.get("date") or today_value,
    )
    month_start, month_end = month_bounds(request.GET.get("month") or date_from.strftime("%Y-%m"))
    report = build_report(station, date_from, date_to, month_start, month_end)
    return JsonResponse(
        {
            "ok": True,
            "station": {"id": station.pk, "name": station.name},
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "operations": [
                {
                    "id": operation.pk,
                    "date": operation.operation_date.isoformat(),
                    "liters_sold": str(operation.total_liters_sold),
                    "expected_sales": str(operation.total_expected_sales),
                    "collections": str(operation.total_collections),
                    "shortage": str(operation.shortage),
                    "overage": str(operation.overage),
                    "status": operation.status,
                }
                for operation in report["daily_operations"]
            ],
        }
    )


@login_required
@require_GET
def monthly_report(request):
    station = _station(request, require_reports=True)
    month_start, month_end = month_bounds(request.GET.get("month") or timezone.localdate().strftime("%Y-%m"))
    report = build_report(station, month_start, month_end, month_start, month_end)
    return JsonResponse(
        {
            "ok": True,
            "station": {"id": station.pk, "name": station.name},
            "month": month_start.strftime("%Y-%m"),
            "summary": _summary_json(report["summary"]),
            "products": [
                {key: str(value) if isinstance(value, Decimal) else value for key, value in item.items()}
                for item in report["product_totals"]
            ],
            "inventory_movements": [
                {
                    "date": item["date"].isoformat(),
                    "type": item["type"],
                    "tank": item["tank_name"],
                    "liters": str(item["movement_liters"]),
                    "reference": item["reference"],
                }
                for item in report["inventory_movements"]
            ],
        }
    )


@login_required
@require_POST
def calculate_pump_reading(request):
    try:
        payload = _payload(request)
        opening = _decimal(payload.get("opening_reading"), "opening_reading")
        closing = _decimal(payload.get("closing_reading"), "closing_reading")
        price = _decimal(payload.get("price_per_liter"), "price_per_liter")
        cost = _decimal(payload.get("cost_per_liter", 0), "cost_per_liter")
        if closing < opening:
            raise ValueError("closing_reading must be greater than or equal to opening_reading.")
    except ValueError as error:
        return _error(str(error))
    sold = liters(closing - opening)
    return JsonResponse(
        {
            "ok": True,
            "liters_sold": str(sold),
            "expected_sales": str(money(sold * price)),
            "fuel_cost": str(money(sold * cost)),
            "gross_profit": str(money(sold * (price - cost))),
        }
    )


@login_required
@require_POST
def calculate_cash_variance(request):
    try:
        payload = _payload(request)
        expected = _decimal(payload.get("expected_sales"), "expected_sales")
        total = sum(
            (
                _decimal(payload.get(field, 0), field)
                for field in (
                    "actual_cash",
                    "gcash_or_bank_transfer",
                    "card_payments",
                    "credit_sales",
                )
            ),
            ZERO,
        )
    except ValueError as error:
        return _error(str(error))
    variance = money(total - expected)
    return JsonResponse(
        {
            "ok": True,
            "total_collection": str(money(total)),
            "variance": str(variance),
            "shortage": str(money(abs(variance)) if variance < ZERO else money(ZERO)),
            "overage": str(money(variance) if variance > ZERO else money(ZERO)),
        }
    )
