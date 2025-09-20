from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Профиль пользователя"
    fields = ("password_hint", "failed_login_attempts", "last_failed_attempt")


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)

    # Убираем лишние поля из Personal info
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    # Убираем лишние поля из формы добавления пользователя
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2"),
            },
        ),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "password_hint",
        "failed_login_attempts",
        "last_failed_attempt",
    )
    list_filter = ("failed_login_attempts", "last_failed_attempt")
    search_fields = ("user__username", "password_hint")
    readonly_fields = ("failed_login_attempts", "last_failed_attempt")

    fieldsets = (
        (None, {"fields": ("user", "password_hint")}),
        (
            "Статистика входа",
            {"fields": ("failed_login_attempts", "last_failed_attempt")},
        ),
    )


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
