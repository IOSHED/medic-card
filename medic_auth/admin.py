from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from unfold.admin import StackedInline

from .models import UserProfile


class UserProfileInline(StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Профиль пользователя"
    fields = ("password_hint", "failed_login_attempts", "last_failed_attempt")

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Permissions", {
            "fields": (
                "is_active", "is_staff", "is_superuser",
                "groups", "user_permissions"
            )
        }),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2"),
        }),
    )


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
