from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from api.models import (
    CashCollection,
    DailyOperation,
    Expense,
    FuelDelivery,
    InventoryAdjustment,
    PumpReading,
)


ZERO = Decimal("0")


def month_bounds(month_value):
    try:
        year, month = [int(part) for part in month_value.split("-")]
        start = date(year, month, 1)
    except (AttributeError, TypeError, ValueError):
        start = timezone.localdate().replace(day=1)
    end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return start, end


def date_range(date_from_value, date_to_value):
    today = timezone.localdate()
    try:
        date_from = date.fromisoformat(date_from_value)
    except (TypeError, ValueError):
        date_from = today
    try:
        date_to = date.fromisoformat(date_to_value)
    except (TypeError, ValueError):
        date_to = date_from
    if date_to < date_from:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def build_report(station, date_from, date_to, month_start, month_end):
    operations = DailyOperation.objects.filter(
        station=station,
        status=DailyOperation.Status.APPROVED,
        is_archived=False,
        operation_date__range=(date_from, date_to),
    ).select_related("station", "encoded_by", "approved_by")

    readings = list(
        PumpReading.objects.filter(
            daily_operation__station=station,
            daily_operation__status=DailyOperation.Status.APPROVED,
            daily_operation__is_archived=False,
            daily_operation__operation_date__gte=month_start,
            daily_operation__operation_date__lt=month_end,
            is_archived=False,
        ).select_related("pump__fuel_product")
    )
    expenses = Expense.objects.filter(
        station=station,
        expense_date__gte=month_start,
        expense_date__lt=month_end,
        is_archived=False,
    ).select_related("category", "encoded_by")
    deliveries = list(
        FuelDelivery.objects.filter(
            station=station,
            delivery_date__gte=month_start,
            delivery_date__lt=month_end,
            is_archived=False,
        ).select_related("fuel_product", "tank", "supplier")
    )
    collections = CashCollection.objects.filter(
        daily_operation__station=station,
        daily_operation__status=DailyOperation.Status.APPROVED,
        daily_operation__is_archived=False,
        daily_operation__operation_date__gte=month_start,
        daily_operation__operation_date__lt=month_end,
    )

    expected_sales = sum((item.expected_sales for item in readings), ZERO)
    liters_sold = sum((item.liters_sold for item in readings), ZERO)
    fuel_cost = sum((item.liters_sold * item.cost_per_liter for item in readings), ZERO)
    expense_total = expenses.aggregate(total=Sum("amount"))["total"] or ZERO
    delivery_liters = sum((item.liters_delivered for item in deliveries), ZERO)
    delivery_cost = sum((item.total_cost for item in deliveries), ZERO)
    shortage = sum((item.shortage for item in collections), ZERO)
    overage = sum((item.overage for item in collections), ZERO)

    product_map = {}
    for reading in readings:
        product = reading.pump.fuel_product
        totals = product_map.setdefault(
            product.pk,
            {
                "name": product.name,
                "code": product.code,
                "liters": ZERO,
                "sales": ZERO,
                "fuel_cost": ZERO,
                "gross_profit": ZERO,
            },
        )
        line_cost = reading.liters_sold * reading.cost_per_liter
        totals["liters"] += reading.liters_sold
        totals["sales"] += reading.expected_sales
        totals["fuel_cost"] += line_cost
        totals["gross_profit"] += reading.expected_sales - line_cost

    adjustments = InventoryAdjustment.objects.filter(
        station=station,
        adjustment_date__gte=month_start,
        adjustment_date__lt=month_end,
        applied_at__isnull=False,
    ).select_related("tank", "approved_by")
    movements = [
        {
            "date": delivery.delivery_date,
            "type": "Delivery",
            "tank": delivery.tank.name,
            "liters": delivery.liters_delivered,
            "reference": delivery.invoice_number or delivery.supplier.name,
        }
        for delivery in deliveries
    ]
    movements.extend(
        {
            "date": adjustment.adjustment_date,
            "type": adjustment.get_adjustment_type_display(),
            "tank": adjustment.tank.name,
            "liters": adjustment.liters,
            "reference": adjustment.reason,
        }
        for adjustment in adjustments
    )
    movements.sort(key=lambda item: (item["date"], item["type"]), reverse=True)

    gross_profit = expected_sales - fuel_cost
    return {
        "daily_operations": operations,
        "expenses": expenses,
        "deliveries": deliveries,
        "expense_categories": expenses.values("category__name").annotate(total=Sum("amount")).order_by("category__name"),
        "product_totals": sorted(product_map.values(), key=lambda item: item["name"]),
        "inventory_movements": movements,
        "summary": {
            "monthly_liters": liters_sold,
            "monthly_expected_sales": expected_sales,
            "monthly_fuel_cost": fuel_cost,
            "gross_profit": gross_profit,
            "monthly_expenses": expense_total,
            "net_profit": gross_profit - expense_total,
            "monthly_shortage": shortage,
            "monthly_overage": overage,
            "delivery_liters": delivery_liters,
            "delivery_cost": delivery_cost,
        },
    }
