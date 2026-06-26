from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import (
    CashCollection,
    DailyOperation,
    FuelDelivery,
    FuelProduct,
    Pump,
    PumpReading,
    Station,
    Supplier,
    Tank,
)


class FuelOpsCalculationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="owner",
            password="test-password",
        )
        self.station = Station.objects.create(
            name="Test Station",
            owner=self.user,
        )
        self.product = FuelProduct.objects.create(
            station=self.station,
            name="Premium",
            code="PREMIUM",
            current_price_per_liter=Decimal("65.00"),
            cost_per_liter=Decimal("60.00"),
        )
        self.tank = Tank.objects.create(
            station=self.station,
            fuel_product=self.product,
            name="Premium Tank",
            capacity_liters=Decimal("10000.000"),
            current_volume_liters=Decimal("1000.000"),
            reorder_level_liters=Decimal("500.000"),
        )
        self.pump = Pump.objects.create(
            station=self.station,
            fuel_product=self.product,
            tank=self.tank,
            name="Premium Pump 1",
            meter_number="PREMIUM-001",
        )
        self.operation = DailyOperation.objects.create(
            station=self.station,
            operation_date=date(2026, 6, 26),
            encoded_by=self.user,
        )

    def test_pump_reading_calculates_liters_and_expected_sales(self):
        reading = PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("125.500"),
            price_per_liter=Decimal("65.00"),
        )

        self.assertEqual(reading.liters_sold, Decimal("25.500"))
        self.assertEqual(reading.expected_sales, Decimal("1657.50"))

    def test_invalid_pump_reading_is_rejected(self):
        with self.assertRaises(ValidationError):
            PumpReading.objects.create(
                daily_operation=self.operation,
                pump=self.pump,
                opening_reading=Decimal("125.000"),
                closing_reading=Decimal("100.000"),
                price_per_liter=Decimal("65.00"),
            )

    def test_cash_collection_calculates_shortage(self):
        PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("110.000"),
            price_per_liter=Decimal("65.00"),
        )

        collection = CashCollection.objects.create(
            daily_operation=self.operation,
            actual_cash=Decimal("600.00"),
        )

        self.assertEqual(collection.expected_sales, Decimal("650.00"))
        self.assertEqual(collection.total_collection, Decimal("600.00"))
        self.assertEqual(collection.shortage, Decimal("50.00"))
        self.assertEqual(collection.overage, Decimal("0.00"))

    def test_fuel_delivery_increases_tank_inventory_and_update_applies_delta(self):
        supplier = Supplier.objects.create(name="Test Supplier")
        delivery = FuelDelivery.objects.create(
            station=self.station,
            fuel_product=self.product,
            tank=self.tank,
            supplier=supplier,
            delivery_date=date(2026, 6, 26),
            liters_delivered=Decimal("500.000"),
            cost_per_liter=Decimal("60.00"),
            received_by=self.user,
        )

        self.tank.refresh_from_db()
        self.assertEqual(self.tank.current_volume_liters, Decimal("1500.000"))
        self.assertEqual(delivery.total_cost, Decimal("30000.00"))

        delivery.liters_delivered = Decimal("700.000")
        delivery.save()

        self.tank.refresh_from_db()
        self.assertEqual(self.tank.current_volume_liters, Decimal("1700.000"))

    def test_approving_operation_deducts_inventory_once(self):
        PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("120.000"),
            price_per_liter=Decimal("65.00"),
        )

        self.operation.approve(self.user)
        self.tank.refresh_from_db()
        self.assertEqual(self.tank.current_volume_liters, Decimal("980.000"))

        self.operation.approve(self.user)
        self.tank.refresh_from_db()
        self.assertEqual(self.tank.current_volume_liters, Decimal("980.000"))
