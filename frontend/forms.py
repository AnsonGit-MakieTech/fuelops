from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone

from api.models import (
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


class StyledFormMixin:
    def apply_styles(self):
        for field in self.fields.values():
            css_class = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-control"
            )
            field.widget.attrs.setdefault("class", css_class)


class FuelOpsAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Email or username")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        username = self.cleaned_data.get("username", "").strip()
        if "@" in username:
            self.cleaned_data["username"] = username.lower()
        return super().clean()


class OwnerRegistrationForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
    station_name = forms.CharField(max_length=150)
    station_address = forms.CharField(
        label="Station address",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    accept_terms = forms.BooleanField(
        label="I accept the FuelOps terms and privacy policy.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields["accept_terms"].widget.attrs["class"] = "form-check-input"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password1")
        confirmation = cleaned_data.get("password2")

        if password and confirmation and password != confirmation:
            self.add_error("password2", "Passwords do not match.")

        if password:
            User = get_user_model()
            candidate = User(
                username=cleaned_data.get("email", ""),
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password, candidate)
            except DjangoValidationError as error:
                self.add_error("password1", forms.ValidationError(error.messages))
        return cleaned_data


class VerificationResendForm(StyledFormMixin, forms.Form):
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class StationSetupForm(StyledFormMixin, forms.Form):
    product_name = forms.CharField(label="Fuel product", max_length=80)
    product_code = forms.CharField(label="Product code", max_length=30)
    selling_price = forms.DecimalField(label="Selling price per liter", min_value=0, decimal_places=2)
    cost_price = forms.DecimalField(label="Cost per liter", min_value=0, decimal_places=2)
    tank_name = forms.CharField(max_length=100)
    tank_capacity = forms.DecimalField(min_value=0.001, decimal_places=3)
    current_volume = forms.DecimalField(min_value=0, decimal_places=3, initial=0)
    reorder_level = forms.DecimalField(min_value=0, decimal_places=3)
    pump_name = forms.CharField(max_length=100)
    meter_number = forms.CharField(max_length=80)
    supplier_name = forms.CharField(max_length=150, initial="Default Fuel Supplier")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

    def clean_product_code(self):
        return self.cleaned_data["product_code"].strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        capacity = cleaned_data.get("tank_capacity")
        current = cleaned_data.get("current_volume")
        reorder = cleaned_data.get("reorder_level")
        if capacity is not None and current is not None and current > capacity:
            self.add_error("current_volume", "Current volume cannot exceed tank capacity.")
        if capacity is not None and reorder is not None and reorder > capacity:
            self.add_error("reorder_level", "Reorder level cannot exceed tank capacity.")
        return cleaned_data


class StationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Station
        fields = ["name", "address", "timezone"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class FuelProductForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FuelProduct
        fields = [
            "name",
            "code",
            "current_price_per_liter",
            "cost_per_liter",
            "is_active",
        ]

    def __init__(self, *args, station, **kwargs):
        super().__init__(*args, **kwargs)
        self.station = station
        self.apply_styles()

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        if self.station.fuel_products.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This product code already exists for the station.")
        return code


class TankForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Tank
        fields = [
            "fuel_product",
            "name",
            "capacity_liters",
            "current_volume_liters",
            "reorder_level_liters",
            "is_active",
        ]

    def __init__(self, *args, station, **kwargs):
        super().__init__(*args, **kwargs)
        self.station = station
        self.fields["fuel_product"].queryset = station.fuel_products.filter(is_active=True)
        if self.instance.pk:
            self.fields["current_volume_liters"].disabled = True
            self.fields["current_volume_liters"].help_text = (
                "Use an inventory adjustment to change existing stock."
            )
        self.apply_styles()

    def clean_fuel_product(self):
        product = self.cleaned_data["fuel_product"]
        if product.station_id != self.station.id:
            raise forms.ValidationError("Fuel product must belong to this station.")
        return product

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if self.station.tanks.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This tank name already exists for the station.")
        return name


class PumpForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Pump
        fields = ["fuel_product", "tank", "name", "meter_number", "is_active"]

    def __init__(self, *args, station, **kwargs):
        super().__init__(*args, **kwargs)
        self.station = station
        self.fields["fuel_product"].queryset = station.fuel_products.filter(is_active=True)
        self.fields["tank"].queryset = station.tanks.filter(is_active=True).select_related(
            "fuel_product"
        )
        self.apply_styles()

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("fuel_product")
        tank = cleaned_data.get("tank")
        if product and product.station_id != self.station.id:
            self.add_error("fuel_product", "Fuel product must belong to this station.")
        if tank and tank.station_id != self.station.id:
            self.add_error("tank", "Tank must belong to this station.")
        if product and tank and tank.fuel_product_id != product.id:
            self.add_error("tank", "Tank fuel product must match the pump fuel product.")
        return cleaned_data

    def clean_meter_number(self):
        meter_number = self.cleaned_data["meter_number"].strip()
        if self.station.pumps.filter(meter_number__iexact=meter_number).exclude(
            pk=self.instance.pk
        ).exists():
            raise forms.ValidationError("This meter number already exists for the station.")
        return meter_number


class SupplierForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address", "is_active"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, station, **kwargs):
        super().__init__(*args, **kwargs)
        self.station = station
        self.apply_styles()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if self.station.suppliers.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This supplier already exists for the station.")
        return name


class InventoryAdjustmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = InventoryAdjustment
        fields = ["tank", "adjustment_date", "adjustment_type", "liters", "reason"]
        widgets = {
            "adjustment_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, station, **kwargs):
        super().__init__(*args, **kwargs)
        self.station = station
        self.fields["tank"].queryset = station.tanks.filter(is_active=True).select_related(
            "fuel_product"
        )
        self.apply_styles()

    def clean_tank(self):
        tank = self.cleaned_data["tank"]
        if tank.station_id != self.station.id:
            raise forms.ValidationError("Tank must belong to this station.")
        return tank


class InviteMemberForm(StyledFormMixin, forms.Form):
    email = forms.EmailField()
    role = forms.ChoiceField(
        choices=[
            (StationMembership.Role.MANAGER, "Manager"),
            (StationMembership.Role.STAFF, "Staff"),
            (StationMembership.Role.ACCOUNTANT, "Accountant"),
        ]
    )

    def __init__(self, *args, station=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.station = station
        self.apply_styles()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if self.station and StationMembership.objects.filter(
            station=self.station,
            user__email__iexact=email,
            status=StationMembership.Status.ACTIVE,
        ).exists():
            raise forms.ValidationError("This user already has access to the station.")
        if self.station and StationInvitation.objects.filter(
            station=self.station,
            email__iexact=email,
            accepted_at=None,
            revoked_at=None,
            expires_at__gt=timezone.now(),
        ).exists():
            raise forms.ValidationError("An active invitation already exists for this email.")
        return email


class InvitationRegistrationForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
    accept_terms = forms.BooleanField(
        label="I accept the FuelOps terms and privacy policy.",
    )

    def __init__(self, *args, email, **kwargs):
        super().__init__(*args, **kwargs)
        self.email = email
        self.apply_styles()
        self.fields["accept_terms"].widget.attrs["class"] = "form-check-input"

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password1")
        confirmation = cleaned_data.get("password2")
        if password and confirmation and password != confirmation:
            self.add_error("password2", "Passwords do not match.")
        if password:
            User = get_user_model()
            candidate = User(
                username=self.email,
                email=self.email,
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password, candidate)
            except DjangoValidationError as error:
                self.add_error("password1", forms.ValidationError(error.messages))
        return cleaned_data


class DailyOperationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DailyOperation
        fields = ["station", "operation_date", "notes"]
        widgets = {
            "operation_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, stations=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["station"].queryset = stations if stations is not None else Station.objects.none()
        self.apply_styles()

    def clean(self):
        cleaned_data = super().clean()
        station = cleaned_data.get("station")
        operation_date = cleaned_data.get("operation_date")
        if station and operation_date and DailyOperation.objects.filter(
            station=station,
            operation_date=operation_date,
            is_archived=False,
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                "Daily operation with this Station and Operation date already exists."
            )
        return cleaned_data


class PumpReadingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PumpReading
        fields = ["pump", "opening_reading", "closing_reading", "price_per_liter"]

    def __init__(self, *args, station=None, daily_operation=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Pump.objects.filter(is_active=True).select_related("fuel_product", "tank")
        if station:
            queryset = queryset.filter(station=station)
        self.fields["pump"].queryset = queryset
        self.daily_operation = daily_operation
        self.apply_styles()

    def clean_pump(self):
        pump = self.cleaned_data["pump"]
        if self.daily_operation and PumpReading.objects.filter(
            daily_operation=self.daily_operation,
            pump=pump,
            is_archived=False,
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This pump already has a reading for this operation.")
        return pump


class CashCollectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CashCollection
        fields = [
            "actual_cash",
            "gcash_or_bank_transfer",
            "card_payments",
            "credit_sales",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class FuelDeliveryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FuelDelivery
        fields = [
            "station",
            "fuel_product",
            "tank",
            "supplier",
            "delivery_date",
            "liters_delivered",
            "cost_per_liter",
            "invoice_number",
            "notes",
        ]
        widgets = {
            "delivery_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, stations=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_stations = stations if stations is not None else Station.objects.none()
        self.fields["station"].queryset = allowed_stations
        self.fields["fuel_product"].queryset = FuelProduct.objects.filter(
            station__in=allowed_stations,
            is_active=True,
        )
        self.fields["tank"].queryset = Tank.objects.filter(
            station__in=allowed_stations,
            is_active=True,
        )
        self.fields["supplier"].queryset = Supplier.objects.filter(
            station__in=allowed_stations,
            is_active=True,
        )
        self.apply_styles()


class ExpenseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            "station",
            "category",
            "expense_date",
            "amount",
            "vendor",
            "reference_number",
            "paid_by",
            "notes",
        ]
        widgets = {
            "expense_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, stations=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_stations = stations if stations is not None else Station.objects.none()
        self.fields["station"].queryset = allowed_stations
        category_filter = Q(is_active=True)
        if self.instance.pk and self.instance.category_id:
            category_filter |= Q(pk=self.instance.category_id)
        self.fields["category"].queryset = ExpenseCategory.objects.filter(
            Q(station__isnull=True) | Q(station__in=allowed_stations),
            category_filter,
        ).distinct()
        self.apply_styles()


class ExpenseCategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, station=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.station = station
        self.apply_styles()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicate = ExpenseCategory.objects.filter(name__iexact=name).filter(
            Q(station__isnull=True) | Q(station=self.station)
        ).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError(
                "This category already exists as a system default or station category."
            )
        return name
