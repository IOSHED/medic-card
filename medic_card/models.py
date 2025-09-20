from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db import models


class Theme(models.Model):
    """Модель темы - может создавать только персонал"""

    title = models.CharField(max_length=200, verbose_name="Название темы")
    description = models.TextField(blank=True, verbose_name="Описание")
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Создано",
        limit_choices_to={"is_staff": True},
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")

    class Meta:
        verbose_name = "Тема"
        verbose_name_plural = "Темы"
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.title

    def get_tickets_count(self):
        return self.tickets.filter(is_active=True).count()


class Ticket(models.Model):
    """Модель билета - может создавать только персонал"""

    theme = models.ForeignKey(
        Theme, on_delete=models.CASCADE, related_name="tickets", verbose_name="Тема"
    )
    title = models.CharField(max_length=200, verbose_name="Название билета")
    description = models.TextField(blank=True, verbose_name="Описание")
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Создано",
        limit_choices_to={"is_staff": True},
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")

    class Meta:
        verbose_name = "Билет"
        verbose_name_plural = "Билеты"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.theme.title} - {self.title}"

    def get_questions_count(self):
        return self.questions.filter(is_active=True).count()


class Question(models.Model):
    """Модель вопроса - может создавать только персонал"""

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="questions", verbose_name="Билет"
    )
    text = models.TextField(verbose_name="Текст вопроса")
    image = models.ImageField(
        upload_to="questions/images/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpg", "jpeg", "gif"])
        ],
        verbose_name="Изображение",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Создано",
        limit_choices_to={"is_staff": True},
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")

    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.ticket.title} - {self.text[:50]}..."

    def get_correct_answers(self):
        return self.answers.filter(is_correct=True)

    def get_answers_count(self):
        return self.answers.filter(is_active=True).count()


class Answer(models.Model):
    """Модель варианта ответа"""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="Вопрос",
    )
    text = models.TextField(verbose_name="Текст ответа")
    is_correct = models.BooleanField(default=False, verbose_name="Правильный ответ")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")

    class Meta:
        verbose_name = "Ответ"
        verbose_name_plural = "Ответы"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.question.text[:30]}... - {self.text[:30]}..."


class UserAnswer(models.Model):
    """Модель для хранения ответов пользователей"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Пользователь"
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, verbose_name="Вопрос"
    )
    selected_answers = models.ManyToManyField(Answer, verbose_name="Выбранные ответы")
    is_correct = models.BooleanField(verbose_name="Правильно отвечено")
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата ответа")

    class Meta:
        verbose_name = "Ответ пользователя"
        verbose_name_plural = "Ответы пользователей"
        unique_together = ["user", "question"]

    def __str__(self):
        return f"{self.user.username} - {self.question.text[:30]}..."
