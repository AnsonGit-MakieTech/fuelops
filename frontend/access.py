from api.models import Station, StationMembership


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


def current_station_for_user(user):
    stations = stations_for_user(user)
    owned_station = stations.filter(owner=user).first()
    return owned_station or stations.first()


def membership_for_user(user, station):
    if not user.is_authenticated or not station:
        return None
    return StationMembership.objects.filter(
        user=user,
        station=station,
        status=StationMembership.Status.ACTIVE,
    ).first()


def can_approve_station(user, station):
    if user.is_superuser:
        return True
    membership = membership_for_user(user, station)
    return bool(membership and membership.can_approve)


def can_manage_station_team(user, station):
    return can_approve_station(user, station)
