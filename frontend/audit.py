from datetime import date, datetime
from decimal import Decimal

from django.db.models import Model

from api.models import AuditLog


def _json_value(value):
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    if isinstance(value, Model):
        return str(value.pk)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def log_audit(user, action, instance, old_value=None, new_value=None):
    return AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        model_name=instance._meta.object_name,
        object_id=str(instance.pk),
        old_value=_json_value(old_value or {}),
        new_value=_json_value(new_value or {}),
    )
