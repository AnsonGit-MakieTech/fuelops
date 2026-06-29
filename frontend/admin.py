from django.contrib import admin

from .models import GuidedTourProgress


@admin.register(GuidedTourProgress)
class GuidedTourProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "guide_key", "version", "status", "updated_at")
    list_filter = ("status", "guide_key", "version")
    search_fields = ("user__username", "guide_key")
