import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from api.models import (
    AuditLog,
    CashCollection,
    DailyOperation,
    ExpenseCategory,
    FuelDelivery,
    FuelProduct,
    InventoryAdjustment,
    Pump,
    PumpReading,
    Station,
    StationMembership,
    Supplier,
    Tank,
)
from .guides import GUIDE_VERSION
from .models import GuidedTourProgress, UserProfile
from .services.registration import create_invitation


class GuidedTourTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="guide-owner",
            password="test-password",
        )
        self.client.force_login(self.user)

    def post_progress(self, **overrides):
        payload = {
            "guide_key": "dashboard",
            "version": GUIDE_VERSION,
            "status": GuidedTourProgress.Status.COMPLETED,
        }
        payload.update(overrides)
        return self.client.post(
            reverse("guide_progress"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_guided_page_is_unseen_until_progress_is_saved(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["guided_tour"]["key"], "dashboard")
        self.assertFalse(response.context["guided_tour"]["has_seen"])
        self.assertContains(response, 'data-guide-key="dashboard"')

        self.post_progress()
        response = self.client.get(reverse("dashboard"))

        self.assertTrue(response.context["guided_tour"]["has_seen"])

    def test_progress_endpoint_creates_and_updates_one_record(self):
        response = self.post_progress()

        self.assertEqual(response.status_code, 200)
        progress = GuidedTourProgress.objects.get(user=self.user, guide_key="dashboard")
        self.assertEqual(progress.status, GuidedTourProgress.Status.COMPLETED)

        response = self.post_progress(status=GuidedTourProgress.Status.DISMISSED)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(GuidedTourProgress.objects.count(), 1)
        progress.refresh_from_db()
        self.assertEqual(progress.status, GuidedTourProgress.Status.DISMISSED)

    def test_progress_endpoint_rejects_unknown_guide_version_and_status(self):
        invalid_requests = [
            {"guide_key": "unknown"},
            {"version": GUIDE_VERSION + 1},
            {"status": "started"},
        ]

        for invalid_payload in invalid_requests:
            with self.subTest(invalid_payload=invalid_payload):
                response = self.post_progress(**invalid_payload)
                self.assertEqual(response.status_code, 400)

        self.assertFalse(GuidedTourProgress.objects.exists())

    def test_progress_endpoint_rejects_malformed_json(self):
        response = self.client.post(
            reverse("guide_progress"),
            data="not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_progress_is_scoped_to_authenticated_user(self):
        self.post_progress()
        second_user = get_user_model().objects.create_user(
            username="guide-manager",
            password="test-password",
        )
        self.client.force_login(second_user)

        response = self.client.get(reverse("dashboard"))

        self.assertFalse(response.context["guided_tour"]["has_seen"])

    def test_anonymous_progress_request_redirects_to_login(self):
        client = Client()
        response = client.post(
            reverse("guide_progress"),
            data=json.dumps(
                {
                    "guide_key": "dashboard",
                    "version": GUIDE_VERSION,
                    "status": GuidedTourProgress.Status.COMPLETED,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)


class RegistrationAndAccessTests(TestCase):
    registration_data = {
        "first_name": "Ana",
        "last_name": "Owner",
        "email": "ana@example.com",
        "password1": "SafeFuelOpsPass123!",
        "password2": "SafeFuelOpsPass123!",
        "station_name": "Ana Fuel Station",
        "station_address": "Cebu City",
        "accept_terms": "on",
    }

    def setUp(self):
        cache.clear()

    def create_owner_station(self, username="owner@example.com", station_name="Owner Station"):
        user = get_user_model().objects.create_user(
            username=username,
            email=username,
            password="SafeFuelOpsPass123!",
        )
        station = Station.objects.create(name=station_name, owner=user)
        return user, station

    def create_product_chain(self, station, suffix="1"):
        product = FuelProduct.objects.create(
            station=station,
            name=f"Diesel {suffix}",
            code=f"DIESEL-{suffix}",
            current_price_per_liter="60.00",
            cost_per_liter="55.00",
        )
        tank = Tank.objects.create(
            station=station,
            fuel_product=product,
            name=f"Tank {suffix}",
            capacity_liters="10000.000",
            current_volume_liters="5000.000",
            reorder_level_liters="1500.000",
        )
        pump = Pump.objects.create(
            station=station,
            fuel_product=product,
            tank=tank,
            name=f"Pump {suffix}",
            meter_number=f"METER-{suffix}",
        )
        return product, tank, pump

    def create_station_member(self, station, role, username):
        user = get_user_model().objects.create_user(
            username=username,
            email=username,
            password="SafeFuelOpsPass123!",
        )
        StationMembership.objects.create(
            station=station,
            user=user,
            role=role,
        )
        return user

    @override_settings(EMAIL_VERIFICATION_REQUIRED=False, REGISTRATION_ENABLED=True)
    def test_owner_registration_atomically_creates_account_station_and_membership(self):
        response = self.client.post(reverse("register"), self.registration_data)

        self.assertRedirects(response, reverse("station_setup"), fetch_redirect_response=False)
        user = get_user_model().objects.get(username="ana@example.com")
        station = Station.objects.get(owner=user)
        membership = StationMembership.objects.get(station=station, user=user)
        self.assertTrue(user.is_active)
        self.assertEqual(membership.role, StationMembership.Role.OWNER)
        self.assertEqual(membership.status, StationMembership.Status.ACTIVE)
        self.assertIsNotNone(user.fuelops_profile.email_verified_at)
        self.assertTrue(AuditLog.objects.filter(action="owner_registered", user=user).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    @override_settings(EMAIL_VERIFICATION_REQUIRED=False, REGISTRATION_ENABLED=True)
    def test_registration_rejects_case_insensitive_duplicate_email(self):
        get_user_model().objects.create_user(
            username="ANA@EXAMPLE.COM",
            email="ANA@EXAMPLE.COM",
            password="SafeFuelOpsPass123!",
        )

        response = self.client.post(reverse("register"), self.registration_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertEqual(Station.objects.count(), 0)

    @override_settings(
        EMAIL_VERIFICATION_REQUIRED=True,
        REGISTRATION_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_verification_activates_account(self):
        response = self.client.post(reverse("register"), self.registration_data)
        user = get_user_model().objects.get(username="ana@example.com")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)

        verification_url = reverse(
            "verify_email",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": default_token_generator.make_token(user),
            },
        )
        response = self.client.get(verification_url)

        self.assertRedirects(response, reverse("station_setup"), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(UserProfile.objects.get(user=user).email_verified_at)

    @override_settings(EMAIL_VERIFICATION_REQUIRED=False, REGISTRATION_ENABLED=True)
    def test_station_setup_creates_valid_product_tank_and_pump_chain(self):
        self.client.post(reverse("register"), self.registration_data)
        station = Station.objects.get(name="Ana Fuel Station")

        response = self.client.post(
            reverse("station_setup"),
            {
                "product_name": "Diesel",
                "product_code": "diesel",
                "selling_price": "61.50",
                "cost_price": "56.25",
                "tank_name": "Diesel Tank",
                "tank_capacity": "10000.000",
                "current_volume": "5000.000",
                "reorder_level": "2000.000",
                "pump_name": "Diesel Pump 1",
                "meter_number": "D-001",
                "supplier_name": "Primary Supplier",
            },
        )

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        product = FuelProduct.objects.get(station=station)
        tank = Tank.objects.get(station=station)
        pump = Pump.objects.get(station=station)
        self.assertEqual(product.code, "DIESEL")
        self.assertEqual(tank.fuel_product, product)
        self.assertEqual(pump.tank, tank)
        self.assertIsNotNone(UserProfile.objects.get(user=station.owner).onboarding_completed_at)

    def test_cross_station_detail_form_and_report_access_is_blocked(self):
        first_user, first_station = self.create_owner_station()
        second_user, second_station = self.create_owner_station(
            username="second@example.com",
            station_name="Second Station",
        )
        foreign_operation = DailyOperation.objects.create(
            station=second_station,
            operation_date=timezone.localdate(),
            encoded_by=second_user,
        )
        self.client.force_login(first_user)

        response = self.client.get(reverse("daily_operation_detail", args=[foreign_operation.pk]))
        self.assertEqual(response.status_code, 404)

        response = self.client.get(reverse("daily_operation_create"))
        self.assertQuerySetEqual(
            response.context["form"].fields["station"].queryset,
            [first_station],
        )

        response = self.client.get(reverse("reports"), {"station": second_station.pk})
        self.assertEqual(response.context["station"], first_station)
        self.assertNotContains(response, f'value="{second_station.pk}"')

    def test_invited_staff_can_register_with_single_use_token(self):
        owner, station = self.create_owner_station()
        invitation, raw_token = create_invitation(
            station,
            owner,
            "staff@example.com",
            StationMembership.Role.STAFF,
        )

        response = self.client.post(
            reverse("accept_invitation", kwargs={"token": raw_token}),
            {
                "first_name": "Sam",
                "last_name": "Staff",
                "password1": "SafeFuelOpsPass123!",
                "password2": "SafeFuelOpsPass123!",
                "accept_terms": "on",
            },
        )

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        user = get_user_model().objects.get(username="staff@example.com")
        membership = StationMembership.objects.get(user=user, station=station)
        invitation.refresh_from_db()
        self.assertEqual(membership.role, StationMembership.Role.STAFF)
        self.assertIsNotNone(invitation.accepted_at)

        self.client.logout()
        response = self.client.get(reverse("accept_invitation", kwargs={"token": raw_token}))
        self.assertEqual(response.status_code, 400)

    def test_duplicate_daily_operation_error_uses_slide_notification(self):
        user, station = self.create_owner_station()
        DailyOperation.objects.create(
            station=station,
            operation_date=timezone.localdate(),
            encoded_by=user,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("daily_operation_create"),
            {
                "station": station.pk,
                "operation_date": timezone.localdate().isoformat(),
                "notes": "Duplicate",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daily operation with this Station and Operation date already exists.")
        self.assertContains(response, "data-form-error-toast")
        self.assertNotContains(response, 'class="message error"')
        self.assertNotContains(response, 'class="errorlist nonfield"')

    def test_dashboard_and_reports_include_phone_layout_markup(self):
        user, station = self.create_owner_station()
        _, _, pump = self.create_product_chain(station)
        operation = DailyOperation.objects.create(
            station=station,
            operation_date=timezone.localdate(),
            encoded_by=user,
        )
        reading = PumpReading.objects.create(
            daily_operation=operation,
            pump=pump,
            opening_reading="100.000",
            closing_reading="110.000",
            price_per_liter="60.00",
        )
        CashCollection.objects.create(daily_operation=operation, actual_cash="600.00")
        operation.submit()
        operation.approve(user)
        self.client.force_login(user)

        dashboard_response = self.client.get(reverse("dashboard"))
        reports_response = self.client.get(reverse("reports"))

        self.assertContains(dashboard_response, 'class="dashboard-page"')
        self.assertContains(dashboard_response, "mobile-stack-table")
        self.assertContains(reports_response, 'class="reports-page"')
        self.assertContains(reports_response, 'data-label="Expected"')

    def test_operation_page_exposes_rejection_correction_and_reopen_actions_by_status(self):
        owner, station = self.create_owner_station()
        _, tank, pump = self.create_product_chain(station)
        operation = DailyOperation.objects.create(
            station=station,
            operation_date=timezone.localdate(),
            encoded_by=owner,
        )
        reading = PumpReading.objects.create(
            daily_operation=operation,
            pump=pump,
            opening_reading="100.000",
            closing_reading="110.000",
            price_per_liter="60.00",
        )
        CashCollection.objects.create(
            daily_operation=operation,
            actual_cash="600.00",
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("daily_operation_detail", args=[operation.pk]))
        self.assertContains(response, 'data-confirm-title="Submit daily sale?"')
        self.assertNotContains(response, 'id="rejection_reason"')

        self.client.post(
            reverse("daily_operation_detail", args=[operation.pk]),
            {"action": "submit"},
        )
        response = self.client.get(reverse("daily_operation_detail", args=[operation.pk]))
        self.assertContains(response, 'id="rejection_reason"')
        self.assertNotContains(response, "Add Pump Reading")

        self.client.post(
            reverse("daily_operation_detail", args=[operation.pk]),
            {"action": "reject", "rejection_reason": "Correct the meter."},
        )
        response = self.client.get(reverse("daily_operation_detail", args=[operation.pk]))
        self.assertContains(response, "Correction required")
        self.assertContains(response, "Correct the meter.")
        self.assertContains(response, "Add Pump Reading")

        response = self.client.post(
            reverse("pump_reading_edit", args=[operation.pk, reading.pk]),
            {
                "pump": pump.pk,
                "opening_reading": "100.000",
                "closing_reading": "109.000",
                "price_per_liter": "60.00",
            },
        )
        self.assertRedirects(
            response,
            reverse("daily_operation_detail", args=[operation.pk]),
            fetch_redirect_response=False,
        )
        operation.cash_collection.refresh_from_db()
        self.assertEqual(operation.cash_collection.expected_sales, Decimal("540.00"))

        self.client.post(
            reverse("daily_operation_detail", args=[operation.pk]),
            {"action": "submit"},
        )
        self.client.post(
            reverse("daily_operation_detail", args=[operation.pk]),
            {"action": "approve"},
        )
        response = self.client.get(reverse("daily_operation_detail", args=[operation.pk]))
        self.assertContains(response, 'id="reopen_reason"')

        self.client.post(
            reverse("daily_operation_detail", args=[operation.pk]),
            {"action": "reopen", "reopen_reason": "Correct approved values."},
        )
        operation.refresh_from_db()
        tank.refresh_from_db()
        self.assertEqual(operation.status, DailyOperation.Status.DRAFT)
        self.assertEqual(tank.current_volume_liters, Decimal("5000.000"))

    def test_official_reports_use_approved_operations_and_historical_cost(self):
        owner, station = self.create_owner_station()
        product, _, pump = self.create_product_chain(station)
        month_start = timezone.localdate().replace(day=1)
        approved_operation = DailyOperation.objects.create(
            station=station,
            operation_date=month_start,
            encoded_by=owner,
        )
        PumpReading.objects.create(
            daily_operation=approved_operation,
            pump=pump,
            opening_reading="100.000",
            closing_reading="110.000",
            price_per_liter="60.00",
        )
        CashCollection.objects.create(
            daily_operation=approved_operation,
            actual_cash="600.00",
        )
        approved_operation.submit()
        approved_operation.approve(owner)

        draft_operation = DailyOperation.objects.create(
            station=station,
            operation_date=month_start + timedelta(days=1),
            encoded_by=owner,
        )
        PumpReading.objects.create(
            daily_operation=draft_operation,
            pump=pump,
            opening_reading="110.000",
            closing_reading="120.000",
            price_per_liter="60.00",
        )
        product.cost_per_liter = Decimal("90.00")
        product.save(update_fields=["cost_per_liter", "updated_at"])
        self.client.force_login(owner)

        response = self.client.get(
            reverse("reports"),
            {
                "date": month_start.isoformat(),
                "month": month_start.strftime("%Y-%m"),
            },
        )

        self.assertEqual(response.context["summary"]["monthly_expected_sales"], Decimal("600.00"))
        self.assertEqual(response.context["summary"]["monthly_fuel_cost"], Decimal("550.00000"))
        self.assertEqual(response.context["summary"]["gross_profit"], Decimal("50.00000"))
        self.assertEqual(list(response.context["daily_operations"]), [approved_operation])

    def test_password_reset_page_is_available(self):
        response = self.client.get(reverse("password_reset"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset password")

    @override_settings(EMAIL_VERIFICATION_REQUIRED=False, REGISTRATION_ENABLED=True)
    def test_registration_rate_limit_returns_slide_notification(self):
        for _ in range(5):
            self.client.post(reverse("register"), {})

        response = self.client.post(reverse("register"), {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many registration attempts")
        self.assertContains(response, 'class="toast-notification error"')

    def test_station_settings_add_multiple_products_tanks_and_pumps(self):
        owner, station = self.create_owner_station()
        self.client.force_login(owner)

        for suffix, name in [("PREM", "Premium"), ("DSL", "Diesel")]:
            response = self.client.post(
                reverse("fuel_product_create"),
                {
                    "name": name,
                    "code": suffix,
                    "current_price_per_liter": "65.00",
                    "cost_per_liter": "59.00",
                    "is_active": "on",
                },
            )
            self.assertRedirects(response, reverse("station_settings"), fetch_redirect_response=False)

        premium = station.fuel_products.get(code="PREM")
        response = self.client.post(
            reverse("tank_create"),
            {
                "fuel_product": premium.pk,
                "name": "Premium Tank",
                "capacity_liters": "12000.000",
                "current_volume_liters": "6000.000",
                "reorder_level_liters": "2000.000",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("station_settings"), fetch_redirect_response=False)
        tank = station.tanks.get(name="Premium Tank")

        response = self.client.post(
            reverse("pump_create"),
            {
                "fuel_product": premium.pk,
                "tank": tank.pk,
                "name": "Premium Pump 1",
                "meter_number": "PREM-001",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("station_settings"), fetch_redirect_response=False)
        self.assertEqual(station.fuel_products.count(), 2)
        self.assertEqual(station.tanks.count(), 1)
        self.assertEqual(station.pumps.count(), 1)

    def test_suppliers_are_station_scoped_in_pages_and_delivery_form(self):
        first_owner, first_station = self.create_owner_station()
        _, second_station = self.create_owner_station(
            username="second-owner@example.com",
            station_name="Second Station",
        )
        first_supplier = Supplier.objects.create(
            station=first_station,
            name="First Supplier",
        )
        second_supplier = Supplier.objects.create(
            station=second_station,
            name="Private Second Supplier",
        )
        self.client.force_login(first_owner)

        response = self.client.get(reverse("suppliers"))
        self.assertContains(response, first_supplier.name)
        self.assertNotContains(response, second_supplier.name)

        response = self.client.get(reverse("fuel_delivery_create"))
        supplier_queryset = response.context["form"].fields["supplier"].queryset
        self.assertQuerySetEqual(
            supplier_queryset,
            [first_supplier],
            transform=lambda supplier: supplier,
        )

        product, tank, _ = self.create_product_chain(first_station)
        response = self.client.post(
            reverse("fuel_delivery_create"),
            {
                "station": first_station.pk,
                "fuel_product": product.pk,
                "tank": tank.pk,
                "supplier": second_supplier.pk,
                "delivery_date": timezone.localdate().isoformat(),
                "liters_delivered": "100.000",
                "cost_per_liter": "54.00",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")

    def test_inventory_adjustment_is_pending_until_owner_approval(self):
        owner, station = self.create_owner_station()
        _, tank, _ = self.create_product_chain(station)
        staff = self.create_station_member(
            station,
            StationMembership.Role.STAFF,
            "staff-adjustment@example.com",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("inventory_adjustment_create"),
            {
                "tank": tank.pk,
                "adjustment_date": timezone.localdate().isoformat(),
                "adjustment_type": InventoryAdjustment.AdjustmentType.LOSS,
                "liters": "250.000",
                "reason": "Physical dip reconciliation",
            },
        )
        self.assertRedirects(response, reverse("inventory"), fetch_redirect_response=False)
        adjustment = InventoryAdjustment.objects.get(station=station)
        tank.refresh_from_db()
        self.assertIsNone(adjustment.applied_at)
        self.assertEqual(str(tank.current_volume_liters), "5000.000")

        response = self.client.post(reverse("inventory_adjustment_approve", args=[adjustment.pk]))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(owner)
        response = self.client.post(reverse("inventory_adjustment_approve", args=[adjustment.pk]))
        self.assertRedirects(response, reverse("inventory"), fetch_redirect_response=False)
        adjustment.refresh_from_db()
        tank.refresh_from_db()
        self.assertIsNotNone(adjustment.applied_at)
        self.assertEqual(str(tank.current_volume_liters), "4750.000")
        self.assertTrue(
            AuditLog.objects.filter(
                action="inventory_adjustment_applied",
                object_id=str(adjustment.pk),
            ).exists()
        )

    def test_staff_and_accountant_permissions_are_enforced_in_views_and_navigation(self):
        owner, station = self.create_owner_station()
        self.create_product_chain(station)
        staff = self.create_station_member(
            station,
            StationMembership.Role.STAFF,
            "role-staff@example.com",
        )
        accountant = self.create_station_member(
            station,
            StationMembership.Role.ACCOUNTANT,
            "role-accountant@example.com",
        )

        self.client.force_login(staff)
        for route_name in ["daily_operations", "fuel_deliveries", "inventory", "expenses"]:
            self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)
        for route_name in ["reports", "station_settings", "team_members"]:
            self.assertEqual(self.client.get(reverse(route_name)).status_code, 403)
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "Monthly Net Profit")
        self.assertNotContains(response, f'href="{reverse("reports")}"')

        self.client.force_login(accountant)
        for route_name in ["expenses", "reports"]:
            self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)
        for route_name in ["daily_operations", "fuel_deliveries", "inventory", "station_settings"]:
            self.assertEqual(self.client.get(reverse(route_name)).status_code, 403)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Monthly Net Profit")
        self.assertNotContains(response, f'href="{reverse("daily_operations")}"')

    def test_team_role_suspension_reactivation_and_last_owner_protection(self):
        owner, station = self.create_owner_station()
        staff = self.create_station_member(
            station,
            StationMembership.Role.STAFF,
            "lifecycle-staff@example.com",
        )
        owner_membership = StationMembership.objects.get(station=station, user=owner)
        staff_membership = StationMembership.objects.get(station=station, user=staff)
        self.client.force_login(owner)

        response = self.client.post(
            reverse("team_members"),
            {"action": "change_role", "membership_id": owner_membership.pk, "role": "manager"},
            follow=True,
        )
        owner_membership.refresh_from_db()
        self.assertEqual(owner_membership.role, StationMembership.Role.OWNER)
        self.assertContains(response, "at least one active owner", status_code=200)

        self.client.post(
            reverse("team_members"),
            {"action": "change_role", "membership_id": staff_membership.pk, "role": "manager"},
        )
        self.client.post(
            reverse("team_members"),
            {"action": "suspend_member", "membership_id": staff_membership.pk},
        )
        staff_membership.refresh_from_db()
        self.assertEqual(staff_membership.status, StationMembership.Status.SUSPENDED)
        self.client.post(
            reverse("team_members"),
            {"action": "reactivate_member", "membership_id": staff_membership.pk},
        )
        staff_membership.refresh_from_db()
        self.assertEqual(staff_membership.role, StationMembership.Role.MANAGER)
        self.assertEqual(staff_membership.status, StationMembership.Status.ACTIVE)
        self.assertTrue(AuditLog.objects.filter(action="station_member_reactivated").exists())

    def test_active_station_switch_is_session_scoped_and_tenant_checked(self):
        owner, first_station = self.create_owner_station()
        second_station = Station.objects.create(name="Second Managed Station")
        StationMembership.objects.create(
            station=second_station,
            user=owner,
            role=StationMembership.Role.MANAGER,
        )
        private_owner, private_station = self.create_owner_station(
            username="private-owner@example.com",
            station_name="Private Station",
        )
        self.assertNotEqual(private_owner, owner)
        self.client.force_login(owner)

        response = self.client.post(
            reverse("switch_station"),
            {"station_id": second_station.pk, "next": reverse("dashboard")},
        )
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["station"], second_station)
        self.assertEqual(self.client.session["active_station_id"], second_station.pk)

        response = self.client.post(
            reverse("switch_station"),
            {"station_id": private_station.pk, "next": reverse("dashboard")},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.session["active_station_id"], second_station.pk)
        self.assertNotEqual(first_station, second_station)

    def test_report_product_delivery_movement_and_api_contract(self):
        owner, station = self.create_owner_station()
        product, tank, pump = self.create_product_chain(station)
        supplier = Supplier.objects.create(station=station, name="Report Supplier")
        month_start = timezone.localdate().replace(day=1)
        operation = DailyOperation.objects.create(
            station=station,
            operation_date=month_start,
            encoded_by=owner,
        )
        PumpReading.objects.create(
            daily_operation=operation,
            pump=pump,
            opening_reading="100.000",
            closing_reading="110.000",
            price_per_liter="60.00",
        )
        CashCollection.objects.create(daily_operation=operation, actual_cash="600.00")
        operation.submit()
        operation.approve(owner)
        FuelDelivery.objects.create(
            station=station,
            fuel_product=product,
            tank=tank,
            supplier=supplier,
            delivery_date=month_start,
            liters_delivered="100.000",
            cost_per_liter="50.00",
            received_by=owner,
            invoice_number="INV-100",
        )
        self.client.force_login(owner)

        response = self.client.get(
            reverse("reports"),
            {
                "date_from": month_start.isoformat(),
                "date_to": month_start.isoformat(),
                "month": month_start.strftime("%Y-%m"),
            },
        )
        self.assertEqual(response.context["product_totals"][0]["liters"], Decimal("10.000"))
        self.assertEqual(response.context["summary"]["delivery_cost"], Decimal("5000.00"))
        self.assertEqual(response.context["inventory_movements"][0]["reference"], "INV-100")

        response = self.client.get(
            reverse("api_monthly_report"),
            {"month": month_start.strftime("%Y-%m")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["products"][0]["liters"], "10.000")
        response = self.client.post(
            reverse("api_calculate_pump_reading"),
            data=json.dumps(
                {
                    "opening_reading": "100.000",
                    "closing_reading": "110.000",
                    "price_per_liter": "60.00",
                    "cost_per_liter": "55.00",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.json()["gross_profit"], "50.00")

    def test_expense_categories_are_station_scoped_and_owner_managed(self):
        owner, station = self.create_owner_station()
        system_category = ExpenseCategory.objects.create(name="Utilities")
        _, other_station = self.create_owner_station(
            username="category-owner@example.com",
            station_name="Category Other Station",
        )
        other_category = ExpenseCategory.objects.create(
            station=other_station,
            name="Other Station Only",
        )
        self.client.force_login(owner)

        response = self.client.post(
            reverse("expense_category_create"),
            {
                "name": "Generator Maintenance",
                "description": "Scheduled generator service",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("expense_categories"), fetch_redirect_response=False)
        station_category = ExpenseCategory.objects.get(
            station=station,
            name="Generator Maintenance",
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action="expense_category_created",
                object_id=str(station_category.pk),
            ).exists()
        )

        response = self.client.get(reverse("expense_create"))
        categories = response.context["form"].fields["category"].queryset
        self.assertIn(system_category, categories)
        self.assertIn(station_category, categories)
        self.assertNotIn(other_category, categories)

        response = self.client.post(
            reverse("expense_create"),
            {
                "station": station.pk,
                "category": other_category.pk,
                "expense_date": timezone.localdate().isoformat(),
                "amount": "100.00",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(station.expenses.exists())

        staff = self.create_station_member(
            station,
            StationMembership.Role.STAFF,
            "category-staff@example.com",
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("expense_categories")).status_code, 403)

    def test_report_generation_supports_pdf_csv_print_and_audit(self):
        owner, station = self.create_owner_station()
        _, _, pump = self.create_product_chain(station)
        report_date = timezone.localdate().replace(day=1)
        operation = DailyOperation.objects.create(
            station=station,
            operation_date=report_date,
            encoded_by=owner,
        )
        PumpReading.objects.create(
            daily_operation=operation,
            pump=pump,
            opening_reading="100.000",
            closing_reading="110.000",
            price_per_liter="60.00",
        )
        CashCollection.objects.create(daily_operation=operation, actual_cash="600.00")
        operation.submit()
        operation.approve(owner)
        self.client.force_login(owner)
        params = {
            "station": station.pk,
            "date_from": report_date.isoformat(),
            "date_to": report_date.isoformat(),
            "month": report_date.strftime("%Y-%m"),
            "report_type": "comprehensive",
        }

        response = self.client.get(reverse("report_export"), {**params, "format": "pdf"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("fuelops-owner-station-comprehensive", response["Content-Disposition"])

        response = self.client.get(reverse("report_export"), {**params, "format": "csv"})
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        csv_content = response.content.decode("utf-8")
        self.assertIn("Comprehensive Operations Report", csv_content)
        self.assertIn("Approved Sales", csv_content)
        self.assertIn(report_date.isoformat(), csv_content)
        self.assertIn("PHP 600.00", csv_content)

        response = self.client.get(reverse("report_export"), {**params, "format": "print"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comprehensive Operations Report")
        self.assertContains(response, "window.print()")
        self.assertEqual(
            AuditLog.objects.filter(
                action="report_generated",
                model_name="Station",
                object_id=str(station.pk),
            ).count(),
            3,
        )

    def test_report_generation_validates_format_and_report_permission(self):
        owner, station = self.create_owner_station()
        staff = self.create_station_member(
            station,
            StationMembership.Role.STAFF,
            "report-export-staff@example.com",
        )
        accountant = self.create_station_member(
            station,
            StationMembership.Role.ACCOUNTANT,
            "report-export-accountant@example.com",
        )
        params = {
            "report_type": "performance",
            "format": "csv",
            "month": timezone.localdate().strftime("%Y-%m"),
        }

        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("report_export"), params).status_code, 403)

        self.client.force_login(accountant)
        self.assertEqual(self.client.get(reverse("report_export"), params).status_code, 200)

        self.client.force_login(owner)
        self.assertEqual(
            self.client.get(
                reverse("report_export"),
                {"report_type": "performance", "format": "xlsx"},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get(
                reverse("report_export"),
                {"report_type": "custom", "format": "pdf"},
            ).status_code,
            400,
        )
