from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from api.models import ExpenseCategory, FuelProduct, Pump, Station, Supplier, Tank


class Command(BaseCommand):
    help = "Seed default FuelOps roles, expense categories, and starter station data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--station-name",
            default="Main Station",
            help="Station name used for starter fuel products, tanks, and pumps.",
        )
        parser.add_argument(
            "--skip-station",
            action="store_true",
            help="Seed only roles and expense categories.",
        )

    def handle(self, *args, **options):
        self.seed_roles()
        self.seed_expense_categories()

        if not options["skip_station"]:
            self.seed_station_defaults(options["station_name"])

        self.stdout.write(self.style.SUCCESS("FuelOps defaults seeded successfully."))

    def seed_roles(self):
        for name in ["Owner", "Manager", "Staff", "Accountant"]:
            Group.objects.get_or_create(name=name)
            self.stdout.write(f"role - {name}")

    def seed_expense_categories(self):
        categories = [
            "Salaries",
            "Bills",
            "Calibration",
            "Fuel Purchase",
            "Maintenance",
            "Government Fees",
            "License Renewal",
            "Supplies",
            "Other",
        ]

        for name in categories:
            ExpenseCategory.objects.get_or_create(station=None, name=name)
            self.stdout.write(f"expense category - {name}")

    def seed_station_defaults(self, station_name):
        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()

        station, _ = Station.objects.get_or_create(
            name=station_name,
            defaults={
                "owner": owner,
                "timezone": "Asia/Manila",
            },
        )
        self.stdout.write(f"station - {station.name}")

        supplier, _ = Supplier.objects.get_or_create(
            station=station,
            name="Default Fuel Supplier",
        )
        self.stdout.write(f"supplier - {supplier.name}")

        product_defaults = [
            {
                "name": "Premium",
                "code": "PREMIUM",
                "current_price_per_liter": Decimal("65.00"),
                "cost_per_liter": Decimal("60.00"),
                "tank_name": "Premium Tank",
                "pump_name": "Premium Pump 1",
                "meter_number": "PREMIUM-001",
            },
            {
                "name": "Diesel",
                "code": "DIESEL",
                "current_price_per_liter": Decimal("58.00"),
                "cost_per_liter": Decimal("53.00"),
                "tank_name": "Diesel Tank",
                "pump_name": "Diesel Pump 1",
                "meter_number": "DIESEL-001",
            },
        ]

        for defaults in product_defaults:
            product, _ = FuelProduct.objects.get_or_create(
                station=station,
                code=defaults["code"],
                defaults={
                    "name": defaults["name"],
                    "current_price_per_liter": defaults["current_price_per_liter"],
                    "cost_per_liter": defaults["cost_per_liter"],
                },
            )
            self.stdout.write(f"fuel product - {product.name}")

            tank, _ = Tank.objects.get_or_create(
                station=station,
                name=defaults["tank_name"],
                defaults={
                    "fuel_product": product,
                    "capacity_liters": Decimal("10000.000"),
                    "current_volume_liters": Decimal("0.000"),
                    "reorder_level_liters": Decimal("2000.000"),
                },
            )
            self.stdout.write(f"tank - {tank.name}")

            pump, _ = Pump.objects.get_or_create(
                station=station,
                meter_number=defaults["meter_number"],
                defaults={
                    "fuel_product": product,
                    "tank": tank,
                    "name": defaults["pump_name"],
                },
            )
            self.stdout.write(f"pump - {pump.name}")
