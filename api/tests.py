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
        self.assertEqual(reading.cost_per_liter, Decimal("60.00"))

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
        supplier = Supplier.objects.create(station=self.station, name="Test Supplier")
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
        CashCollection.objects.create(
            daily_operation=self.operation,
            actual_cash=Decimal("1300.00"),
        )
        self.operation.submit()

        self.operation.approve(self.user)
        self.tank.refresh_from_db()
        self.assertEqual(self.tank.current_volume_liters, Decimal("980.000"))

        self.operation.approve(self.user)
        self.tank.refresh_from_db()
        self.assertEqual(self.tank.current_volume_liters, Decimal("980.000"))

    def test_submission_and_approval_enforce_ready_state_and_transitions(self):
        self.operation.status = DailyOperation.Status.APPROVED
        with self.assertRaises(ValidationError):
            self.operation.save()
        self.operation.status = DailyOperation.Status.DRAFT

        with self.assertRaises(ValidationError):
            self.operation.submit()

        PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("110.000"),
            price_per_liter=Decimal("65.00"),
        )
        with self.assertRaises(ValidationError):
            self.operation.submit()

        CashCollection.objects.create(
            daily_operation=self.operation,
            actual_cash=Decimal("650.00"),
        )
        with self.assertRaises(ValidationError):
            self.operation.approve(self.user)

        self.operation.submit()
        self.assertEqual(self.operation.status, DailyOperation.Status.SUBMITTED)
        with self.assertRaises(ValidationError):
            self.operation.submit()

    def test_rejection_requires_reason_and_returns_operation_to_correction_flow(self):
        reading = PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("110.000"),
            price_per_liter=Decimal("65.00"),
        )
        CashCollection.objects.create(
            daily_operation=self.operation,
            actual_cash=Decimal("650.00"),
        )
        self.operation.submit()

        with self.assertRaises(ValidationError):
            self.operation.reject(self.user, "")

        self.operation.reject(self.user, "Correct the closing meter.")
        self.assertEqual(self.operation.status, DailyOperation.Status.REJECTED)
        self.assertEqual(self.operation.rejection_reason, "Correct the closing meter.")

        reading.closing_reading = Decimal("111.000")
        reading.save()
        self.operation.submit()
        self.assertEqual(self.operation.status, DailyOperation.Status.SUBMITTED)

    def test_submitted_and_approved_records_are_locked_and_reopen_reverses_inventory(self):
        reading = PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("120.000"),
            price_per_liter=Decimal("65.00"),
        )
        collection = CashCollection.objects.create(
            daily_operation=self.operation,
            actual_cash=Decimal("1300.00"),
        )
        self.operation.submit()

        reading.closing_reading = Decimal("121.000")
        with self.assertRaises(ValidationError):
            reading.save()
        collection.actual_cash = Decimal("1400.00")
        with self.assertRaises(ValidationError):
            collection.save()

        self.operation.approve(self.user)
        self.tank.refresh_from_db()
        self.assertEqual(self.tank.current_volume_liters, Decimal("980.000"))
        self.operation.notes = "Direct approved edit"
        with self.assertRaises(ValidationError):
            self.operation.save()
        self.operation.notes = ""
        with self.assertRaises(ValidationError):
            self.operation.delete()
        with self.assertRaises(ValidationError):
            self.operation.reopen(self.user, "")

        self.operation.reopen(self.user, "Correct approved meter entry.")
        self.tank.refresh_from_db()
        self.assertEqual(self.operation.status, DailyOperation.Status.DRAFT)
        self.assertEqual(self.tank.current_volume_liters, Decimal("1000.000"))
        self.assertIsNone(self.operation.inventory_deducted_at)

        reading.refresh_from_db()
        reading.closing_reading = Decimal("119.000")
        reading.save()

    def test_collection_variance_recalculates_when_readings_change_or_delete(self):
        collection = CashCollection.objects.create(
            daily_operation=self.operation,
            actual_cash=Decimal("600.00"),
        )
        reading = PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("110.000"),
            price_per_liter=Decimal("65.00"),
        )
        collection.refresh_from_db()
        self.assertEqual(collection.shortage, Decimal("50.00"))

        reading.closing_reading = Decimal("108.000")
        reading.save()
        collection.refresh_from_db()
        self.assertEqual(collection.expected_sales, Decimal("520.00"))
        self.assertEqual(collection.overage, Decimal("80.00"))

        reading.delete()
        collection.refresh_from_db()
        self.assertEqual(collection.expected_sales, Decimal("0.00"))
        self.assertEqual(collection.overage, Decimal("600.00"))

    def test_reading_cost_snapshot_does_not_change_with_product_cost(self):
        reading = PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("110.000"),
            price_per_liter=Decimal("65.00"),
        )
        self.product.cost_per_liter = Decimal("70.00")
        self.product.save(update_fields=["cost_per_liter", "updated_at"])

        reading.refresh_from_db()
        self.assertEqual(reading.cost_per_liter, Decimal("60.00"))

    def test_archiving_reading_preserves_history_and_recalculates_collection(self):
        reading = PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("110.000"),
            price_per_liter=Decimal("65.00"),
        )
        collection = CashCollection.objects.create(
            daily_operation=self.operation,
            actual_cash=Decimal("650.00"),
        )

        reading.archive(self.user, "Wrong meter entry")

        reading.refresh_from_db()
        collection.refresh_from_db()
        self.assertTrue(reading.is_archived)
        self.assertEqual(collection.expected_sales, Decimal("0.00"))
        replacement = PumpReading.objects.create(
            daily_operation=self.operation,
            pump=self.pump,
            opening_reading=Decimal("100.000"),
            closing_reading=Decimal("109.000"),
            price_per_liter=Decimal("65.00"),
        )
        self.assertEqual(replacement.liters_sold, Decimal("9.000"))

    def test_archiving_delivery_reverses_inventory_and_locks_record(self):
        supplier = Supplier.objects.create(station=self.station, name="Archive Supplier")
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

        delivery.archive(self.user, "Duplicate invoice")

        self.tank.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(self.tank.current_volume_liters, Decimal("1000.000"))
        self.assertTrue(delivery.is_archived)
        delivery.notes = "Attempted edit"
        with self.assertRaises(ValidationError):
            delivery.save()
