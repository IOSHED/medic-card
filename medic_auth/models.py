from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    password_hint = models.CharField(
        max_length=200,
        blank=True,
        help_text="Подсказка для восстановления пароля (будет показана после 3 неудачных попыток входа)",
    )
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_attempt = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Profile for {self.user.username}"

    def reset_failed_attempts(self):
        self.failed_login_attempts = 0
        self.last_failed_attempt = None
        self.save()

    def increment_failed_attempts(self):
        from django.utils import timezone

        self.failed_login_attempts += 1
        self.last_failed_attempt = timezone.now()
        self.save()
