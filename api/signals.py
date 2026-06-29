from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Station, StationMembership


@receiver(post_save, sender=Station)
def ensure_station_owner_membership(sender, instance, **kwargs):
    if not instance.owner_id:
        return

    StationMembership.objects.filter(
        station=instance,
        role=StationMembership.Role.OWNER,
    ).exclude(user_id=instance.owner_id).update(status=StationMembership.Status.REVOKED)
    StationMembership.objects.update_or_create(
        station=instance,
        user_id=instance.owner_id,
        defaults={
            "role": StationMembership.Role.OWNER,
            "status": StationMembership.Status.ACTIVE,
        },
    )
