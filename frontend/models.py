from django.conf import settings
from django.db import models


class GuidedTourProgress(models.Model):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        DISMISSED = "dismissed", "Dismissed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="guided_tour_progress",
    )
    guide_key = models.CharField(max_length=64)
    version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id", "guide_key", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "guide_key", "version"],
                name="unique_user_guided_tour_version",
            )
        ]

    def __str__(self):
        return f"{self.user} / {self.guide_key} v{self.version} / {self.status}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fuelops_profile",
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=20, blank=True)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"FuelOps profile for {self.user}"
