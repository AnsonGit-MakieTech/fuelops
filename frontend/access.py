from django.core.exceptions import PermissionDenied

from api.models import Station, StationMembership


MANAGE_CATALOG = "manage_catalog"
MANAGE_TEAM = "manage_team"
ENCODE_OPERATIONS = "encode_operations"
MANAGE_DELIVERIES = "manage_deliveries"
MANAGE_EXPENSES = "manage_expenses"
VIEW_INVENTORY = "view_inventory"
CREATE_ADJUSTMENTS = "create_adjustments"
APPROVE_ADJUSTMENTS = "approve_adjustments"
VIEW_REPORTS = "view_reports"
APPROVE_OPERATIONS = "approve_operations"

ROLE_PERMISSIONS = {
    StationMembership.Role.OWNER: {
        MANAGE_CATALOG,
        MANAGE_TEAM,
        ENCODE_OPERATIONS,
        MANAGE_DELIVERIES,
        MANAGE_EXPENSES,
        VIEW_INVENTORY,
        CREATE_ADJUSTMENTS,
        APPROVE_ADJUSTMENTS,
        VIEW_REPORTS,
        APPROVE_OPERATIONS,
    },
    StationMembership.Role.MANAGER: {
        MANAGE_CATALOG,
        MANAGE_TEAM,
        ENCODE_OPERATIONS,
        MANAGE_DELIVERIES,
        MANAGE_EXPENSES,
        VIEW_INVENTORY,
        CREATE_ADJUSTMENTS,
        APPROVE_ADJUSTMENTS,
        VIEW_REPORTS,
        APPROVE_OPERATIONS,
    },
    StationMembership.Role.STAFF: {
        ENCODE_OPERATIONS,
        MANAGE_DELIVERIES,
        MANAGE_EXPENSES,
        VIEW_INVENTORY,
        CREATE_ADJUSTMENTS,
    },
    StationMembership.Role.ACCOUNTANT: {
        MANAGE_EXPENSES,
        VIEW_REPORTS,
    },
}


def stations_for_user(user):
    if not user.is_authenticated:
        return Station.objects.none()
    if user.is_superuser:
        return Station.objects.filter(is_active=True)
    return Station.objects.filter(
        memberships__user=user,
        memberships__status=StationMembership.Status.ACTIVE,
        is_active=True,
    ).distinct()


def stations_for_user_with_permission(user, permission):
    if not user.is_authenticated:
        return Station.objects.none()
    if user.is_superuser:
        return Station.objects.filter(is_active=True)
    roles = [
        role
        for role, permissions in ROLE_PERMISSIONS.items()
        if permission in permissions
    ]
    return Station.objects.filter(
        memberships__user=user,
        memberships__status=StationMembership.Status.ACTIVE,
        memberships__role__in=roles,
        is_active=True,
    ).distinct()


def current_station_for_user(user, preferred_station_id=None):
    stations = stations_for_user(user)
    if preferred_station_id:
        preferred = stations.filter(pk=preferred_station_id).first()
        if preferred:
            return preferred
    owned_station = stations.filter(owner=user).first()
    return owned_station or stations.first()


def current_station_for_request(request):
    station = current_station_for_user(
        request.user,
        request.session.get("active_station_id"),
    )
    if station:
        request.session["active_station_id"] = station.pk
    else:
        request.session.pop("active_station_id", None)
    return station


def membership_for_user(user, station):
    if not user.is_authenticated or not station:
        return None
    return StationMembership.objects.filter(
        user=user,
        station=station,
        status=StationMembership.Status.ACTIVE,
    ).first()


def can_approve_station(user, station):
    return user_has_station_permission(user, station, APPROVE_OPERATIONS)


def can_manage_station_team(user, station):
    return user_has_station_permission(user, station, MANAGE_TEAM)


def user_has_station_permission(user, station, permission):
    if user.is_superuser:
        return True
    membership = membership_for_user(user, station)
    if not membership:
        return False
    return permission in ROLE_PERMISSIONS.get(membership.role, set())


def require_station_permission(user, station, permission):
    if not user_has_station_permission(user, station, permission):
        raise PermissionDenied


def permissions_for_user(user, station):
    return {
        permission: user_has_station_permission(user, station, permission)
        for permission in {
            MANAGE_CATALOG,
            MANAGE_TEAM,
            ENCODE_OPERATIONS,
            MANAGE_DELIVERIES,
            MANAGE_EXPENSES,
            VIEW_INVENTORY,
            CREATE_ADJUSTMENTS,
            APPROVE_ADJUSTMENTS,
            VIEW_REPORTS,
            APPROVE_OPERATIONS,
        }
    }
