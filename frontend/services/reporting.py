from datetime import date
from decimal import Decimal

from django.db.models import (
    Case,
    CharField,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.utils import timezone

from api.models import (
    CashCollection,
    DailyOperation,
    Expense,
    FuelDelivery,
    InventoryAdjustment,
    PumpReading,
    liters,
    money,
)


ZERO = Decimal("0")


def with_operation_totals(queryset):
    return queryset.select_related(
        "station",
        "encoded_by",
        "approved_by",
        "cash_collection",
    ).annotate(
        annotated_total_liters_sold=Sum(
            "readings__liters_sold",
            filter=Q(readings__is_archived=False),
        ),
        annotated_total_expected_sales=Sum(
            "readings__expected_sales",
            filter=Q(readings__is_archived=False),
        ),
    )


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


def inventory_movement_queryset(station, month_start, month_end):
    deliveries = FuelDelivery.objects.filter(
        station=station,
        delivery_date__gte=month_start,
        delivery_date__lt=month_end,
        is_archived=False,
    ).order_by().annotate(
        date=F("delivery_date"),
        type=Value("Delivery", output_field=CharField()),
        tank_name=F("tank__name"),
        movement_liters=F("liters_delivered"),
        reference=Case(
            When(invoice_number="", then=F("supplier__name")),
            default=F("invoice_number"),
            output_field=CharField(),
        ),
    ).values("date", "type", "tank_name", "movement_liters", "reference")
    adjustments = InventoryAdjustment.objects.filter(
        station=station,
        adjustment_date__gte=month_start,
        adjustment_date__lt=month_end,
        applied_at__isnull=False,
    ).order_by().annotate(
        date=F("adjustment_date"),
        type=Case(
            When(adjustment_type=InventoryAdjustment.AdjustmentType.GAIN, then=Value("Gain")),
            When(adjustment_type=InventoryAdjustment.AdjustmentType.LOSS, then=Value("Loss")),
            default=Value("Correction"),
            output_field=CharField(),
        ),
        tank_name=F("tank__name"),
        movement_liters=F("liters"),
        reference=F("reason"),
    ).values("date", "type", "tank_name", "movement_liters", "reference")
    return deliveries.union(adjustments, all=True).order_by("-date", "-type")


def build_report(station, date_from, date_to, month_start, month_end):
    operations = with_operation_totals(
        DailyOperation.objects.filter(
            station=station,
            status=DailyOperation.Status.APPROVED,
            is_archived=False,
            operation_date__range=(date_from, date_to),
        )
    )

    readings = PumpReading.objects.filter(
        daily_operation__station=station,
        daily_operation__status=DailyOperation.Status.APPROVED,
        daily_operation__is_archived=False,
        daily_operation__operation_date__gte=month_start,
        daily_operation__operation_date__lt=month_end,
        is_archived=False,
    )
    expenses = Expense.objects.filter(
        station=station,
        expense_date__gte=month_start,
        expense_date__lt=month_end,
        is_archived=False,
    ).select_related("category", "encoded_by")
    deliveries = FuelDelivery.objects.filter(
        station=station,
        delivery_date__gte=month_start,
        delivery_date__lt=month_end,
        is_archived=False,
    ).select_related("fuel_product", "tank", "supplier")
    collections = CashCollection.objects.filter(
        daily_operation__station=station,
        daily_operation__status=DailyOperation.Status.APPROVED,
        daily_operation__is_archived=False,
        daily_operation__operation_date__gte=month_start,
        daily_operation__operation_date__lt=month_end,
    )

    line_cost = ExpressionWrapper(
        F("liters_sold") * F("cost_per_liter"),
        output_field=DecimalField(max_digits=24, decimal_places=5),
    )
    reading_totals = readings.aggregate(
        liters=Sum("liters_sold"),
        sales=Sum("expected_sales"),
        fuel_cost=Sum(line_cost),
    )
    expected_sales = reading_totals["sales"] or ZERO
    liters_sold = reading_totals["liters"] or ZERO
    fuel_cost = reading_totals["fuel_cost"] or ZERO
    expense_total = expenses.aggregate(total=Sum("amount"))["total"] or ZERO
    delivery_totals = deliveries.aggregate(
        liters=Sum("liters_delivered"),
        cost=Sum("total_cost"),
    )
    delivery_liters = delivery_totals["liters"] or ZERO
    delivery_cost = delivery_totals["cost"] or ZERO
    collection_totals = collections.aggregate(
        shortage=Sum("shortage"),
        overage=Sum("overage"),
    )
    shortage = collection_totals["shortage"] or ZERO
    overage = collection_totals["overage"] or ZERO

    product_totals = []
    for totals in readings.values(
        "pump__fuel_product__name",
        "pump__fuel_product__code",
    ).annotate(
        liters=Sum("liters_sold"),
        sales=Sum("expected_sales"),
        fuel_cost=Sum(line_cost),
    ).order_by("pump__fuel_product__name"):
        product_totals.append(
            {
                "name": totals["pump__fuel_product__name"],
                "code": totals["pump__fuel_product__code"],
                "liters": liters(totals["liters"]),
                "sales": money(totals["sales"]),
                "fuel_cost": money(totals["fuel_cost"]),
                "gross_profit": money(
                    (totals["sales"] or ZERO) - (totals["fuel_cost"] or ZERO)
                ),
            }
        )

    gross_profit = expected_sales - fuel_cost
    return {
        "daily_operations": operations,
        "expenses": expenses,
        "deliveries": deliveries,
        "expense_categories": expenses.values("category__name").annotate(total=Sum("amount")).order_by("category__name"),
        "product_totals": product_totals,
        "inventory_movements": inventory_movement_queryset(
            station,
            month_start,
            month_end,
        ),
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
