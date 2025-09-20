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

    # Статистика пользователя
    tickets_solved = models.PositiveIntegerField(
        default=0, verbose_name="Решено билетов"
    )
    mistakes_made = models.PositiveIntegerField(
        default=0, verbose_name="Совершено ошибок"
    )
    correct_answers = models.PositiveIntegerField(
        default=0, verbose_name="Правильных ответов"
    )
    last_activity = models.DateTimeField(
        null=True, blank=True, verbose_name="Последняя активность"
    )

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

    def get_masked_password_hint(self):
        """Возвращает фразу-подсказку, скрытую звездочками кроме первых 2 символов (максимум 8 звездочек)"""
        if not self.password_hint:
            return "Не установлена"

        if len(self.password_hint) <= 2:
            return "*" * len(self.password_hint)

        # Ограничиваем количество звездочек максимум 8
        stars_count = min(len(self.password_hint) - 2, 8)
        return self.password_hint[:2] + "*" * stars_count
