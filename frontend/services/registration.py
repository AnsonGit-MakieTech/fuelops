import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from api.models import (
    AuditLog,
    FuelProduct,
    Pump,
    Station,
    StationInvitation,
    StationMembership,
    Supplier,
    Tank,
)
from frontend.models import UserProfile


TERMS_VERSION = "2026-06"


def normalize_email(email):
    return email.strip().lower()


@transaction.atomic
def register_owner(cleaned_data, require_verification):
    User = get_user_model()
    email = normalize_email(cleaned_data["email"])
    user = User.objects.create_user(
        username=email,
        email=email,
        password=cleaned_data["password1"],
        first_name=cleaned_data["first_name"].strip(),
        last_name=cleaned_data["last_name"].strip(),
        is_active=not require_verification,
    )
    station = Station.objects.create(
        name=cleaned_data["station_name"].strip(),
        address=cleaned_data["station_address"].strip(),
        owner=user,
    )
    Group.objects.get_or_create(name="Owner")[0].user_set.add(user)
    UserProfile.objects.create(
        user=user,
        email_verified_at=None if require_verification else timezone.now(),
        terms_accepted_at=timezone.now(),
        terms_version=TERMS_VERSION,
    )
    AuditLog.objects.create(
        user=user,
        action="owner_registered",
        model_name="Station",
        object_id=str(station.pk),
        new_value={"station": station.name, "email": email},
    )
    return user, station


def send_verification_email(request, user, from_email):
    context = {
        "user": user,
        "verification_url": request.build_absolute_uri(
            reverse(
                "verify_email",
                kwargs={
                    "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": default_token_generator.make_token(user),
                },
            )
        ),
    }
    send_mail(
        subject="Verify your FuelOps account",
        message=render_to_string("registration/emails/verify_email.txt", context),
        from_email=from_email,
        recipient_list=[user.email],
    )


@transaction.atomic
def activate_user(user):
    user.is_active = True
    user.save(update_fields=["is_active"])
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=["email_verified_at", "updated_at"])
    AuditLog.objects.create(
        user=user,
        action="email_verified",
        model_name="User",
        object_id=str(user.pk),
        new_value={"email": user.email},
    )
    return user


@transaction.atomic
def configure_first_station(user, station, cleaned_data):
    product = FuelProduct(
        station=station,
        name=cleaned_data["product_name"].strip(),
        code=cleaned_data["product_code"],
        current_price_per_liter=cleaned_data["selling_price"],
        cost_per_liter=cleaned_data["cost_price"],
    )
    product.full_clean()
    product.save()

    tank = Tank(
        station=station,
        fuel_product=product,
        name=cleaned_data["tank_name"].strip(),
        capacity_liters=cleaned_data["tank_capacity"],
        current_volume_liters=cleaned_data["current_volume"],
        reorder_level_liters=cleaned_data["reorder_level"],
    )
    tank.full_clean()
    tank.save()

    pump = Pump(
        station=station,
        fuel_product=product,
        tank=tank,
        name=cleaned_data["pump_name"].strip(),
        meter_number=cleaned_data["meter_number"].strip(),
    )
    pump.full_clean()
    pump.save()

    Supplier.objects.get_or_create(name=cleaned_data["supplier_name"].strip())
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.onboarding_completed_at = timezone.now()
    profile.save(update_fields=["onboarding_completed_at", "updated_at"])
    AuditLog.objects.create(
        user=user,
        action="station_setup_completed",
        model_name="Station",
        object_id=str(station.pk),
        new_value={
            "product": product.name,
            "tank": tank.name,
            "pump": pump.name,
        },
    )
    return product, tank, pump


def invitation_hash(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@transaction.atomic
def create_invitation(station, invited_by, email, role):
    raw_token = secrets.token_urlsafe(32)
    invitation = StationInvitation.objects.create(
        station=station,
        email=normalize_email(email),
        role=role,
        token_hash=invitation_hash(raw_token),
        invited_by=invited_by,
        expires_at=timezone.now() + timedelta(hours=48),
    )
    AuditLog.objects.create(
        user=invited_by,
        action="station_invitation_created",
        model_name="StationInvitation",
        object_id=str(invitation.pk),
        new_value={"email": invitation.email, "role": invitation.role},
    )
    return invitation, raw_token


def send_invitation_email(request, invitation, raw_token, from_email):
    context = {
        "invitation": invitation,
        "accept_url": request.build_absolute_uri(
            reverse("accept_invitation", kwargs={"token": raw_token})
        ),
    }
    send_mail(
        subject=f"Join {invitation.station.name} on FuelOps",
        message=render_to_string("registration/emails/invitation.txt", context),
        from_email=from_email,
        recipient_list=[invitation.email],
    )


def get_active_invitation(raw_token):
    invitation = StationInvitation.objects.filter(
        token_hash=invitation_hash(raw_token),
    ).select_related("station", "invited_by").first()
    return invitation if invitation and invitation.is_active else None


@transaction.atomic
def accept_invitation_for_user(invitation, user):
    membership, _ = StationMembership.objects.update_or_create(
        station=invitation.station,
        user=user,
        defaults={
            "role": invitation.role,
            "status": StationMembership.Status.ACTIVE,
            "invited_by": invitation.invited_by,
            "joined_at": timezone.now(),
        },
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at", "updated_at"])
    Group.objects.get_or_create(name=membership.get_role_display())[0].user_set.add(user)
    AuditLog.objects.create(
        user=user,
        action="station_invitation_accepted",
        model_name="StationMembership",
        object_id=str(membership.pk),
        new_value={"station": invitation.station.name, "role": membership.role},
    )
    return membership


@transaction.atomic
def register_invited_user(invitation, cleaned_data):
    User = get_user_model()
    user = User.objects.create_user(
        username=invitation.email,
        email=invitation.email,
        password=cleaned_data["password1"],
        first_name=cleaned_data["first_name"].strip(),
        last_name=cleaned_data["last_name"].strip(),
        is_active=True,
    )
    UserProfile.objects.create(
        user=user,
        email_verified_at=timezone.now(),
        terms_accepted_at=timezone.now(),
        terms_version=TERMS_VERSION,
    )
    accept_invitation_for_user(invitation, user)
    return user
