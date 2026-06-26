from django.contrib import admin

from .models import (
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
    Supplier,
    Tank,
)


class PumpReadingInline(admin.TabularInline):
    model = PumpReading
    extra = 0
    readonly_fields = ("liters_sold", "expected_sales")


class CashCollectionInline(admin.StackedInline):
    model = CashCollection
    extra = 0
    max_num = 1
    readonly_fields = ("expected_sales", "shortage", "overage")


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "timezone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "address", "owner__username", "owner__email")


@admin.register(FuelProduct)
class FuelProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "station",
        "current_price_per_liter",
        "cost_per_liter",
        "is_active",
    )
    list_filter = ("station", "is_active")
    search_fields = ("name", "code", "station__name")


@admin.register(Tank)
class TankAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "station",
        "fuel_product",
        "current_volume_liters",
        "capacity_liters",
        "reorder_level_liters",
        "is_low_stock",
        "is_active",
    )
    list_filter = ("station", "fuel_product", "is_active")
    search_fields = ("name", "station__name", "fuel_product__name")
    readonly_fields = ("is_low_stock",)


@admin.register(Pump)
class PumpAdmin(admin.ModelAdmin):
    list_display = ("name", "meter_number", "station", "fuel_product", "tank", "is_active")
    list_filter = ("station", "fuel_product", "is_active")
    search_fields = ("name", "meter_number", "station__name")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "email", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_person", "phone", "email")


@admin.register(DailyOperation)
class DailyOperationAdmin(admin.ModelAdmin):
    list_display = (
        "operation_date",
        "station",
        "status",
        "encoded_by",
        "approved_by",
        "total_liters_sold",
        "total_expected_sales",
        "total_collections",
        "shortage",
        "overage",
    )
    list_filter = ("status", "station", "operation_date")
    search_fields = ("station__name", "encoded_by__username", "approved_by__username")
    readonly_fields = ("inventory_deducted_at",)
    inlines = [PumpReadingInline, CashCollectionInline]
    actions = ("approve_operations", "submit_operations", "reject_operations")

    @admin.action(description="Submit selected daily operations")
    def submit_operations(self, request, queryset):
        for operation in queryset:
            operation.submit()

    @admin.action(description="Approve selected daily operations")
    def approve_operations(self, request, queryset):
        for operation in queryset:
            operation.approve(request.user)

    @admin.action(description="Reject selected daily operations")
    def reject_operations(self, request, queryset):
        for operation in queryset:
            operation.reject(request.user)


@admin.register(PumpReading)
class PumpReadingAdmin(admin.ModelAdmin):
    list_display = (
        "daily_operation",
        "pump",
        "opening_reading",
        "closing_reading",
        "liters_sold",
        "price_per_liter",
        "expected_sales",
    )
    list_filter = ("daily_operation__station", "pump__fuel_product")
    search_fields = ("daily_operation__station__name", "pump__name", "pump__meter_number")
    readonly_fields = ("liters_sold", "expected_sales")


@admin.register(CashCollection)
class CashCollectionAdmin(admin.ModelAdmin):
    list_display = (
        "daily_operation",
        "expected_sales",
        "actual_cash",
        "gcash_or_bank_transfer",
        "card_payments",
        "credit_sales",
        "shortage",
        "overage",
    )
    list_filter = ("daily_operation__station", "daily_operation__operation_date")
    search_fields = ("daily_operation__station__name",)
    readonly_fields = ("expected_sales", "shortage", "overage")


@admin.register(FuelDelivery)
class FuelDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "delivery_date",
        "station",
        "fuel_product",
        "tank",
        "supplier",
        "liters_delivered",
        "cost_per_liter",
        "total_cost",
        "invoice_number",
    )
    list_filter = ("station", "fuel_product", "supplier", "delivery_date")
    search_fields = ("station__name", "supplier__name", "invoice_number")
    readonly_fields = ("total_cost",)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "expense_date",
        "station",
        "category",
        "amount",
        "vendor",
        "reference_number",
        "encoded_by",
    )
    list_filter = ("station", "category", "expense_date")
    search_fields = ("station__name", "vendor", "reference_number", "encoded_by__username")


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        "adjustment_date",
        "station",
        "tank",
        "adjustment_type",
        "liters",
        "encoded_by",
        "approved_by",
        "applied_at",
    )
    list_filter = ("station", "adjustment_type", "adjustment_date")
    search_fields = ("station__name", "tank__name", "reason")
    readonly_fields = ("applied_at",)
    actions = ("apply_adjustments",)

    @admin.action(description="Apply selected inventory adjustments")
    def apply_adjustments(self, request, queryset):
        for adjustment in queryset:
            adjustment.apply(request.user)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "model_name", "object_id")
    list_filter = ("action", "model_name", "created_at")
    search_fields = ("user__username", "action", "model_name", "object_id")
    readonly_fields = ("created_at", "user", "action", "model_name", "object_id", "old_value", "new_value")

    def has_add_permission(self, request):
        return False
