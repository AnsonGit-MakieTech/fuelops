from django.contrib import admin

from .models import GuidedTourProgress, UserProfile


@admin.register(GuidedTourProgress)
class GuidedTourProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "guide_key", "version", "status", "updated_at")
    list_filter = ("status", "guide_key", "version")
    search_fields = ("user__username", "guide_key")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "email_verified_at",
        "onboarding_completed_at",
        "terms_version",
    )
    search_fields = ("user__username", "user__email")
