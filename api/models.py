from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone


MONEY_PLACES = Decimal("0.01")
LITER_PLACES = Decimal("0.001")
ZERO = Decimal("0")


def decimal_or_zero(value):
    if value is None:
        return ZERO
    return Decimal(value)


def money(value):
    return decimal_or_zero(value).quantize(MONEY_PLACES)


def liters(value):
    return decimal_or_zero(value).quantize(LITER_PLACES)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Station(TimeStampedModel):
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="owned_stations",
        null=True,
        blank=True,
    )
    timezone = models.CharField(max_length=64, default="Asia/Manila")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StationMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        STAFF = "staff", "Staff"
        ACCOUNTANT = "accountant", "Accountant"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REVOKED = "revoked", "Revoked"

    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="station_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_station_memberships",
        null=True,
        blank=True,
    )
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["station__name", "role", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["station", "user"],
                name="unique_station_membership",
            )
        ]

    @property
    def can_approve(self):
        return self.status == self.Status.ACTIVE and self.role in {
            self.Role.OWNER,
            self.Role.MANAGER,
        }

    def __str__(self):
        return f"{self.station} - {self.user} ({self.get_role_display()})"


class StationInvitation(TimeStampedModel):
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=[
            (StationMembership.Role.MANAGER, "Manager"),
            (StationMembership.Role.STAFF, "Staff"),
            (StationMembership.Role.ACCOUNTANT, "Accountant"),
        ],
    )
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="station_invitations",
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_active(self):
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )

    def __str__(self):
        return f"{self.station} - {self.email} ({self.get_role_display()})"


class FuelProduct(TimeStampedModel):
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="fuel_products",
    )
    name = models.CharField(max_length=80)
    code = models.CharField(max_length=30)
    current_price_per_liter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    cost_per_liter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["station__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["station", "code"],
                name="unique_fuel_product_code_per_station",
            )
        ]

    def __str__(self):
        return f"{self.station} - {self.name}"


class Tank(TimeStampedModel):
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="tanks",
    )
    fuel_product = models.ForeignKey(
        FuelProduct,
        on_delete=models.PROTECT,
        related_name="tanks",
    )
    name = models.CharField(max_length=100)
    capacity_liters = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(ZERO)],
    )
    current_volume_liters = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    reorder_level_liters = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["station__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["station", "name"],
                name="unique_tank_name_per_station",
            )
        ]

    def clean(self):
        errors = {}

        if self.fuel_product_id and self.station_id:
            if self.fuel_product.station_id != self.station_id:
                errors["fuel_product"] = "Fuel product must belong to the same station."

        if self.current_volume_liters > self.capacity_liters:
            errors["current_volume_liters"] = "Current volume cannot exceed tank capacity."

        if self.reorder_level_liters > self.capacity_liters:
            errors["reorder_level_liters"] = "Reorder level cannot exceed tank capacity."

        if errors:
            raise ValidationError(errors)

    @property
    def is_low_stock(self):
        return self.current_volume_liters <= self.reorder_level_liters

    def __str__(self):
        return f"{self.station} - {self.name}"


class Pump(TimeStampedModel):
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="pumps",
    )
    fuel_product = models.ForeignKey(
        FuelProduct,
        on_delete=models.PROTECT,
        related_name="pumps",
    )
    tank = models.ForeignKey(
        Tank,
        on_delete=models.PROTECT,
        related_name="pumps",
    )
    name = models.CharField(max_length=100)
    meter_number = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["station__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["station", "meter_number"],
                name="unique_pump_meter_per_station",
            )
        ]

    def clean(self):
        errors = {}

        if self.fuel_product_id and self.station_id:
            if self.fuel_product.station_id != self.station_id:
                errors["fuel_product"] = "Fuel product must belong to the same station."

        if self.tank_id and self.station_id:
            if self.tank.station_id != self.station_id:
                errors["tank"] = "Tank must belong to the same station."

        if self.tank_id and self.fuel_product_id:
            if self.tank.fuel_product_id != self.fuel_product_id:
                errors["tank"] = "Tank fuel product must match pump fuel product."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.station} - {self.name}"


class Supplier(TimeStampedModel):
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="suppliers",
    )
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["station__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["station", "name"],
                name="unique_supplier_name_per_station",
            )
        ]

    def __str__(self):
        return f"{self.station} - {self.name}"


class DailyOperation(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="daily_operations",
    )
    operation_date = models.DateField()
    encoded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="encoded_daily_operations",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_daily_operations",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    inventory_deducted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reopened_daily_operations",
        null=True,
        blank=True,
    )
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopen_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-operation_date", "station__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["station", "operation_date"],
                name="unique_daily_operation_per_station_date",
            )
        ]

    @property
    def total_liters_sold(self):
        return liters(self.readings.aggregate(total=Sum("liters_sold"))["total"])

    @property
    def total_expected_sales(self):
        return money(self.readings.aggregate(total=Sum("expected_sales"))["total"])

    @property
    def total_collections(self):
        if not hasattr(self, "cash_collection"):
            return money(ZERO)
        return self.cash_collection.total_collection

    @property
    def shortage(self):
        if not hasattr(self, "cash_collection"):
            return money(ZERO)
        return self.cash_collection.shortage

    @property
    def overage(self):
        if not hasattr(self, "cash_collection"):
            return money(ZERO)
        return self.cash_collection.overage

    @property
    def is_editable(self):
        return self.status in {self.Status.DRAFT, self.Status.REJECTED}

    def save(self, *args, **kwargs):
        transition_allowed = getattr(self, "_transition_allowed", False)
        if not self.pk and self.status != self.Status.DRAFT and not transition_allowed:
            raise ValidationError({"status": "New operations must start as draft."})

        if self.pk and not transition_allowed:
            previous = DailyOperation.objects.get(pk=self.pk)
            if previous.status != self.status:
                raise ValidationError(
                    {"status": "Use the operation workflow actions to change status."}
                )
            if previous.status in {self.Status.SUBMITTED, self.Status.APPROVED}:
                protected_fields = (
                    "station_id",
                    "operation_date",
                    "encoded_by_id",
                    "notes",
                    "approved_by_id",
                    "inventory_deducted_at",
                    "rejection_reason",
                    "reopened_by_id",
                    "reopened_at",
                    "reopen_reason",
                )
                if any(
                    getattr(previous, field) != getattr(self, field)
                    for field in protected_fields
                ):
                    raise ValidationError(
                        "Submitted and approved operations can only change through workflow actions."
                    )
        super().save(*args, **kwargs)

    def save_transition(self, update_fields):
        self._transition_allowed = True
        try:
            self.save(update_fields=update_fields)
        finally:
            self._transition_allowed = False

    def delete(self, *args, **kwargs):
        if not self.is_editable:
            raise ValidationError(
                "Submitted and approved operations cannot be deleted. Use the controlled workflow."
            )
        return super().delete(*args, **kwargs)

    def validate_ready_for_review(self):
        errors = {}
        if not self.readings.exists():
            errors["readings"] = "Add at least one pump reading before submission."
        if not hasattr(self, "cash_collection"):
            errors["collection"] = "Save the cash collection before submission."
        if errors:
            raise ValidationError(errors)

    def submit(self):
        if not self.is_editable:
            raise ValidationError(
                {"status": "Only draft or rejected operations can be submitted."}
            )
        self.validate_ready_for_review()
        self.status = self.Status.SUBMITTED
        self.save_transition(["status", "updated_at"])

    def approve(self, user):
        if self.status == self.Status.APPROVED and self.inventory_deducted_at:
            return
        if self.status != self.Status.SUBMITTED:
            raise ValidationError(
                {"status": "Only submitted operations can be approved."}
            )
        self.validate_ready_for_review()

        with transaction.atomic():
            for reading in self.readings.select_related("pump__tank").select_for_update():
                tank = reading.pump.tank
                tank.current_volume_liters = liters(
                    tank.current_volume_liters - reading.liters_sold
                )
                tank.full_clean()
                tank.save(update_fields=["current_volume_liters", "updated_at"])

            self.status = self.Status.APPROVED
            self.approved_by = user
            self.inventory_deducted_at = timezone.now()
            self.save_transition(
                [
                    "status",
                    "approved_by",
                    "inventory_deducted_at",
                    "updated_at",
                ]
            )

    def reject(self, user, reason):
        if self.status != self.Status.SUBMITTED:
            raise ValidationError(
                {"status": "Only submitted operations can be rejected."}
            )
        reason = reason.strip()
        if not reason:
            raise ValidationError({"rejection_reason": "A rejection reason is required."})
        self.status = self.Status.REJECTED
        self.approved_by = user
        self.rejection_reason = reason
        self.save_transition(
            [
                "status",
                "approved_by",
                "rejection_reason",
                "updated_at",
            ]
        )

    def reopen(self, user, reason):
        if self.status != self.Status.APPROVED or not self.inventory_deducted_at:
            raise ValidationError(
                {"status": "Only approved operations can be reopened."}
            )
        reason = reason.strip()
        if not reason:
            raise ValidationError({"reopen_reason": "A reopen reason is required."})

        with transaction.atomic():
            for reading in self.readings.select_related("pump__tank").select_for_update():
                tank = Tank.objects.select_for_update().get(pk=reading.pump.tank_id)
                tank.current_volume_liters = liters(
                    tank.current_volume_liters + reading.liters_sold
                )
                tank.full_clean()
                tank.save(update_fields=["current_volume_liters", "updated_at"])

            self.status = self.Status.DRAFT
            self.approved_by = None
            self.inventory_deducted_at = None
            self.reopened_by = user
            self.reopened_at = timezone.now()
            self.reopen_reason = reason
            self.save_transition(
                [
                    "status",
                    "approved_by",
                    "inventory_deducted_at",
                    "reopened_by",
                    "reopened_at",
                    "reopen_reason",
                    "updated_at",
                ]
            )

    def __str__(self):
        return f"{self.station} - {self.operation_date}"


class PumpReading(TimeStampedModel):
    daily_operation = models.ForeignKey(
        DailyOperation,
        on_delete=models.CASCADE,
        related_name="readings",
    )
    pump = models.ForeignKey(
        Pump,
        on_delete=models.PROTECT,
        related_name="readings",
    )
    opening_reading = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(ZERO)],
    )
    closing_reading = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(ZERO)],
    )
    liters_sold = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=ZERO,
        editable=False,
    )
    price_per_liter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    cost_per_liter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=ZERO,
        editable=False,
        validators=[MinValueValidator(ZERO)],
    )
    expected_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        editable=False,
    )

    class Meta:
        ordering = ["daily_operation__operation_date", "pump__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["daily_operation", "pump"],
                name="unique_pump_reading_per_operation",
            )
        ]

    def calculate(self):
        self.liters_sold = liters(self.closing_reading - self.opening_reading)
        self.expected_sales = money(self.liters_sold * self.price_per_liter)

    def clean(self):
        errors = {}

        if self.daily_operation_id and not self.daily_operation.is_editable:
            errors["daily_operation"] = (
                "Readings can only change while the operation is draft or rejected."
            )

        if self.closing_reading < self.opening_reading:
            errors["closing_reading"] = "Closing reading must be greater than or equal to opening reading."

        if self.daily_operation_id and self.pump_id:
            if self.daily_operation.station_id != self.pump.station_id:
                errors["pump"] = "Pump must belong to the same station as the operation."

        if not errors:
            self.calculate()

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.pk and self.pump_id:
            self.cost_per_liter = money(self.pump.fuel_product.cost_per_liter)
        self.full_clean()
        self.calculate()
        super().save(*args, **kwargs)
        if hasattr(self.daily_operation, "cash_collection"):
            self.daily_operation.cash_collection.save()

    def delete(self, *args, **kwargs):
        if not self.daily_operation.is_editable:
            raise ValidationError(
                "Readings can only be deleted while the operation is draft or rejected."
            )
        operation = self.daily_operation
        result = super().delete(*args, **kwargs)
        if hasattr(operation, "cash_collection"):
            operation.cash_collection.save()
        return result

    def __str__(self):
        return f"{self.daily_operation} - {self.pump}"


class CashCollection(TimeStampedModel):
    daily_operation = models.OneToOneField(
        DailyOperation,
        on_delete=models.CASCADE,
        related_name="cash_collection",
    )
    expected_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        editable=False,
    )
    actual_cash = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    gcash_or_bank_transfer = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    card_payments = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    credit_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    shortage = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        editable=False,
    )
    overage = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        editable=False,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-daily_operation__operation_date"]

    @property
    def total_collection(self):
        return money(
            self.actual_cash
            + self.gcash_or_bank_transfer
            + self.card_payments
            + self.credit_sales
        )

    @property
    def variance(self):
        return money(self.total_collection - self.expected_sales)

    def calculate(self):
        self.expected_sales = self.daily_operation.total_expected_sales
        variance = self.variance
        self.shortage = money(abs(variance)) if variance < ZERO else money(ZERO)
        self.overage = money(variance) if variance > ZERO else money(ZERO)

    def clean(self):
        if self.daily_operation_id and not self.daily_operation.is_editable:
            raise ValidationError(
                {"daily_operation": "Collections can only change while the operation is draft or rejected."}
            )
        if self.daily_operation_id:
            self.calculate()

    def save(self, *args, **kwargs):
        self.full_clean()
        self.calculate()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.daily_operation.is_editable:
            raise ValidationError(
                "Collections can only be deleted while the operation is draft or rejected."
            )
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.daily_operation} collection"


class FuelDelivery(TimeStampedModel):
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="fuel_deliveries",
    )
    fuel_product = models.ForeignKey(
        FuelProduct,
        on_delete=models.PROTECT,
        related_name="fuel_deliveries",
    )
    tank = models.ForeignKey(
        Tank,
        on_delete=models.PROTECT,
        related_name="fuel_deliveries",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="fuel_deliveries",
    )
    delivery_date = models.DateField()
    liters_delivered = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    cost_per_liter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        editable=False,
    )
    invoice_number = models.CharField(max_length=100, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="received_fuel_deliveries",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-delivery_date", "station__name"]

    def calculate(self):
        self.total_cost = money(self.liters_delivered * self.cost_per_liter)

    def clean(self):
        errors = {}

        if self.fuel_product_id and self.station_id:
            if self.fuel_product.station_id != self.station_id:
                errors["fuel_product"] = "Fuel product must belong to the same station."

        if self.tank_id and self.station_id:
            if self.tank.station_id != self.station_id:
                errors["tank"] = "Tank must belong to the same station."

        if self.tank_id and self.fuel_product_id:
            if self.tank.fuel_product_id != self.fuel_product_id:
                errors["tank"] = "Tank fuel product must match delivery fuel product."

        if self.supplier_id and self.station_id:
            if self.supplier.station_id != self.station_id:
                errors["supplier"] = "Supplier must belong to the same station."

        if not errors:
            self.calculate()

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        self.calculate()

        with transaction.atomic():
            if self.pk:
                previous = FuelDelivery.objects.select_for_update().get(pk=self.pk)
                if previous.tank_id == self.tank_id:
                    tank = Tank.objects.select_for_update().get(pk=self.tank_id)
                    tank.current_volume_liters = liters(
                        tank.current_volume_liters
                        + self.liters_delivered
                        - previous.liters_delivered
                    )
                    tank.full_clean()
                    tank.save(update_fields=["current_volume_liters", "updated_at"])
                else:
                    old_tank = Tank.objects.select_for_update().get(pk=previous.tank_id)
                    new_tank = Tank.objects.select_for_update().get(pk=self.tank_id)
                    old_tank.current_volume_liters = liters(
                        old_tank.current_volume_liters - previous.liters_delivered
                    )
                    new_tank.current_volume_liters = liters(
                        new_tank.current_volume_liters + self.liters_delivered
                    )
                    old_tank.full_clean()
                    new_tank.full_clean()
                    old_tank.save(update_fields=["current_volume_liters", "updated_at"])
                    new_tank.save(update_fields=["current_volume_liters", "updated_at"])
            else:
                tank = Tank.objects.select_for_update().get(pk=self.tank_id)
                tank.current_volume_liters = liters(
                    tank.current_volume_liters + self.liters_delivered
                )
                tank.full_clean()
                tank.save(update_fields=["current_volume_liters", "updated_at"])

            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.station} - {self.fuel_product} - {self.delivery_date}"


class ExpenseCategory(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Expense(TimeStampedModel):
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    expense_date = models.DateField()
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    vendor = models.CharField(max_length=150, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    paid_by = models.CharField(max_length=120, blank=True)
    encoded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="encoded_expenses",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-expense_date", "category__name"]

    def __str__(self):
        return f"{self.station} - {self.category} - {self.amount}"


class InventoryAdjustment(TimeStampedModel):
    class AdjustmentType(models.TextChoices):
        GAIN = "gain", "Gain"
        LOSS = "loss", "Loss"
        CORRECTION = "correction", "Correction"

    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="inventory_adjustments",
    )
    tank = models.ForeignKey(
        Tank,
        on_delete=models.PROTECT,
        related_name="inventory_adjustments",
    )
    adjustment_date = models.DateField()
    adjustment_type = models.CharField(
        max_length=20,
        choices=AdjustmentType.choices,
    )
    liters = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    reason = models.TextField()
    encoded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="encoded_inventory_adjustments",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_inventory_adjustments",
        null=True,
        blank=True,
    )
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-adjustment_date", "station__name"]

    def clean(self):
        if self.tank_id and self.station_id and self.tank.station_id != self.station_id:
            raise ValidationError({"tank": "Tank must belong to the same station."})

    def apply(self, user):
        if self.applied_at:
            return

        with transaction.atomic():
            tank = Tank.objects.select_for_update().get(pk=self.tank_id)

            if self.adjustment_type == self.AdjustmentType.GAIN:
                tank.current_volume_liters = liters(tank.current_volume_liters + self.liters)
            elif self.adjustment_type == self.AdjustmentType.LOSS:
                tank.current_volume_liters = liters(tank.current_volume_liters - self.liters)
            else:
                tank.current_volume_liters = liters(self.liters)

            tank.full_clean()
            tank.save(update_fields=["current_volume_liters", "updated_at"])

            self.approved_by = user
            self.applied_at = timezone.now()
            self.save(update_fields=["approved_by", "applied_at", "updated_at"])

    def __str__(self):
        return f"{self.station} - {self.tank} - {self.adjustment_type}"


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=120)
    model_name = models.CharField(max_length=120)
    object_id = models.CharField(max_length=80)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.model_name} {self.object_id}"
