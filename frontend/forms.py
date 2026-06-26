from django import forms

from api.models import (
    CashCollection,
    DailyOperation,
    Expense,
    FuelDelivery,
    FuelProduct,
    Pump,
    PumpReading,
    Station,
    Supplier,
    Tank,
)


class StyledFormMixin:
    def apply_styles(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class DailyOperationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DailyOperation
        fields = ["station", "operation_date", "notes"]
        widgets = {
            "operation_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["station"].queryset = Station.objects.filter(is_active=True)
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["station"].queryset = Station.objects.filter(is_active=True)
        self.fields["fuel_product"].queryset = FuelProduct.objects.filter(is_active=True)
        self.fields["tank"].queryset = Tank.objects.filter(is_active=True)
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["station"].queryset = Station.objects.filter(is_active=True)
        self.apply_styles()
