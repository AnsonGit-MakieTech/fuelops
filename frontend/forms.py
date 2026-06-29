from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from api.models import (
    CashCollection,
    DailyOperation,
    Expense,
    FuelDelivery,
    FuelProduct,
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
            field.widget.attrs.setdefault("class", "form-control")


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
        self.fields["supplier"].queryset = Supplier.objects.filter(is_active=True)
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
        self.fields["station"].queryset = stations if stations is not None else Station.objects.none()
        self.apply_styles()
