from .guides import GUIDE_VERSION, ROUTE_GUIDES
from .models import GuidedTourProgress
from .access import can_manage_station_team, current_station_for_user


def guided_tour(request):
    if not request.user.is_authenticated or not request.resolver_match:
        return {"guided_tour": None}

    guide_key = ROUTE_GUIDES.get(request.resolver_match.url_name)
    if not guide_key:
        return {"guided_tour": None}

    has_seen = GuidedTourProgress.objects.filter(
        user=request.user,
        guide_key=guide_key,
        version=GUIDE_VERSION,
    ).exists()

    return {
        "guided_tour": {
            "key": guide_key,
            "version": GUIDE_VERSION,
            "has_seen": has_seen,
        }
    }


def station_permissions(request):
    if not request.user.is_authenticated:
        return {"can_manage_team": False}
    station = current_station_for_user(request.user)
    return {
        "can_manage_team": bool(station and can_manage_station_team(request.user, station)),
    }
