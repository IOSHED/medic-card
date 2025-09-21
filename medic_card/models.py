from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
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

    def get_user_progress_stats(self, user):
        """Возвращает статистику прогресса пользователя по теме"""
        if not user.is_authenticated:
            return None

        tickets = self.tickets.filter(is_active=True)
        total_questions = 0
        correct_answers = 0
        mistakes = 0

        for ticket in tickets:
            try:
                progress = TicketProgress.objects.get(user=user, ticket=ticket)
                total_questions += progress.total_questions
                correct_answers += progress.correct_answers
                mistakes += progress.total_questions - progress.correct_answers
            except TicketProgress.DoesNotExist:
                pass

        return {
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "mistakes": mistakes,
            "accuracy": (correct_answers / total_questions * 100)
            if total_questions > 0
            else 0,
        }

    def get_progress_color(self, user):
        """Возвращает цвет рамки на основе количества ошибок"""
        stats = self.get_user_progress_stats(user)
        if not stats or stats["total_questions"] == 0:
            return "secondary"  # Серый - нет прогресса

        accuracy = stats["accuracy"]
        if accuracy >= 80:
            return "success"  # Зеленый - хорошо
        elif accuracy >= 60:
            return "warning"  # Желтый - удовлетворительно
        else:
            return "danger"  # Красный - плохо


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
    is_temporary = models.BooleanField(default=False, verbose_name="Временный билет")
    original_ticket = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Оригинальный билет",
    )

    class Meta:
        verbose_name = "Билет"
        verbose_name_plural = "Билеты"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.theme.title} - {self.title}"

    def get_questions_count(self):
        return self.questions.filter(is_active=True).count()

    def get_user_progress_stats(self, user):
        """Возвращает статистику прогресса пользователя по билету"""
        if not user.is_authenticated:
            return None

        try:
            progress = TicketProgress.objects.get(user=user, ticket=self)
            return {
                "total_questions": progress.total_questions,
                "correct_answers": progress.correct_answers,
                "mistakes": progress.total_questions - progress.correct_answers,
                "accuracy": (progress.correct_answers / progress.total_questions * 100)
                if progress.total_questions > 0
                else 0,
                "is_completed": progress.is_completed,
            }
        except TicketProgress.DoesNotExist:
            return {
                "total_questions": self.get_questions_count(),
                "correct_answers": 0,
                "mistakes": 0,
                "accuracy": 0,
                "is_completed": False,
            }

    def get_progress_color(self, user):
        """Возвращает цвет рамки на основе количества ошибок"""
        stats = self.get_user_progress_stats(user)
        if not stats or stats["total_questions"] == 0:
            return "secondary"  # Серый - нет прогресса

        if not stats["is_completed"]:
            return "info"  # Синий - в процессе

        accuracy = stats["accuracy"]
        if accuracy >= 80:
            return "success"  # Зеленый - хорошо
        elif accuracy >= 60:
            return "warning"  # Желтый - удовлетворительно
        else:
            return "danger"  # Красный - плохо

    def create_errors_ticket(self, user, wrong_questions):
        """Создает временный билет только с вопросами, на которые пользователь ответил неправильно"""
        if not wrong_questions.exists():
            return None

        # Создаем временный билет
        temp_ticket = Ticket.objects.create(
            theme=self.theme,
            title=f"{self.title} - Перерешивание ошибок",
            description=f"Временный билет для перерешивания ошибок из билета '{self.title}'",
            created_by=user,
            is_active=True,
            is_temporary=True,
            original_ticket=self,
        )

        # Копируем только неправильные вопросы
        for question in wrong_questions:
            new_question = Question.objects.create(
                ticket=temp_ticket,
                text=question.text,
                image=question.image,
                created_by=user,
                is_active=True,
            )

            # Копируем ответы
            for answer in question.answers.filter(is_active=True):
                Answer.objects.create(
                    question=new_question,
                    text=answer.text,
                    is_correct=answer.is_correct,
                    is_active=True,
                    order=answer.order,
                )

        return temp_ticket


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


class TicketProgress(models.Model):
    """Модель для отслеживания прогресса прохождения билета пользователем"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Пользователь"
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, verbose_name="Билет")
    current_question_index = models.PositiveIntegerField(
        default=0, verbose_name="Текущий вопрос (индекс)"
    )
    is_completed = models.BooleanField(default=False, verbose_name="Завершен")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Начат")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Завершен")
    correct_answers = models.PositiveIntegerField(
        default=0, verbose_name="Правильных ответов"
    )
    total_questions = models.PositiveIntegerField(
        default=0, verbose_name="Всего вопросов"
    )
    time_spent = models.DurationField(
        null=True, blank=True, verbose_name="Время выполнения"
    )
    question_order = models.JSONField(
        null=True, blank=True, verbose_name="Порядок вопросов (ID)"
    )

    class Meta:
        verbose_name = "Прогресс билета"
        verbose_name_plural = "Прогресс билетов"
        unique_together = ["user", "ticket"]

    def __str__(self):
        return f"{self.user.username} - {self.ticket.title}"

    def get_progress_percentage(self):
        """Возвращает процент выполнения билета"""
        if self.total_questions == 0:
            return 0
        return (self.current_question_index / self.total_questions) * 100

    def get_current_question(self):
        """Возвращает текущий вопрос"""
        questions = self.ticket.questions.filter(is_active=True).order_by(
            "order", "created_at"
        )
        if self.current_question_index < questions.count():
            return questions[self.current_question_index]
        return None

    def get_remaining_questions(self):
        """Возвращает количество оставшихся вопросов"""
        return max(0, self.total_questions - self.current_question_index)

    def calculate_time_spent(self):
        """Вычисляет время выполнения"""
        if self.completed_at and self.started_at:
            self.time_spent = self.completed_at - self.started_at
            self.save()

    def get_current_time_spent(self):
        """Возвращает текущее время выполнения (если билет еще не завершен)"""
        if self.is_completed and self.time_spent:
            return self.time_spent
        elif self.started_at:
            from django.utils import timezone

            return timezone.now() - self.started_at
        return None

    def get_time_spent_display(self):
        """Возвращает время выполнения в читаемом формате"""
        time_spent = self.get_current_time_spent()
        if time_spent:
            total_seconds = int(time_spent.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            if hours > 0:
                return f"{hours}ч {minutes}м {seconds}с"
            elif minutes > 0:
                return f"{minutes}м {seconds}с"
            else:
                return f"{seconds}с"
        return "Не завершен"

    def get_questions_in_order(self):
        """Возвращает вопросы в сохраненном порядке"""
        if self.question_order:
            # Получаем вопросы в сохраненном порядке
            questions = []
            for question_id in self.question_order:
                try:
                    question = Question.objects.get(id=question_id, is_active=True)
                    questions.append(question)
                except Question.DoesNotExist:
                    continue
            return questions
        else:
            # Если порядок не сохранен, возвращаем в обычном порядке
            return list(
                self.ticket.questions.filter(is_active=True).order_by(
                    "order", "created_at"
                )
            )

    def set_questions_order(self, questions):
        """Сохраняет порядок вопросов"""
        self.question_order = [q.id for q in questions]
        self.save()


class Favorites(models.Model):
    """Модель для хранения избранных тем и билетов"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Пользователь"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        unique_together = ["user", "content_type", "object_id"]
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user.username} - {self.content_object}"

    @classmethod
    def is_favorite(cls, user, obj):
        """Проверяет, добавлен ли объект в избранное"""
        if not user.is_authenticated:
            return False
        return cls.objects.filter(
            user=user,
            content_type=ContentType.objects.get_for_model(obj),
            object_id=obj.id,
        ).exists()

    @classmethod
    def toggle_favorite(cls, user, obj):
        """Добавляет или удаляет объект из избранного"""
        if not user.is_authenticated:
            return False, "Необходима авторизация"

        content_type = ContentType.objects.get_for_model(obj)
        favorite, created = cls.objects.get_or_create(
            user=user, content_type=content_type, object_id=obj.id
        )

        if not created:
            favorite.delete()
            return False, "Удалено из избранного"
        else:
            return True, "Добавлено в избранное"
