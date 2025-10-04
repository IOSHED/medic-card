from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from unfold.decorators import display
from .models import Answer, Question, Theme, Ticket, TicketProgress, UserAnswer, Favorites


# ============================================================================
# INLINE КЛАССЫ
# ============================================================================

class AnswerInline(TabularInline):
    """Inline для создания ответов при создании/редактировании вопроса"""
    model = Answer
    extra = 4  # Показываем 4 пустых формы для новых ответов
    min_num = 2  # Минимум 2 ответа обязательны
    fields = ["text", "is_correct", "is_active", "order"]
    classes = ['collapse']
    verbose_name = "Ответ"
    verbose_name_plural = "Ответы на этот вопрос"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields['text'].widget.attrs.update({
            'style': 'width: 500px; height: 60px;',
            'placeholder': 'Введите текст ответа...'
        })
        return formset


# ============================================================================
# ОСНОВНЫЕ АДМИН-КЛАССЫ
# ============================================================================

@admin.register(Theme)
class ThemeAdmin(ModelAdmin):
    list_display = ["title", "created_by", "created_at", "is_active", "tickets_count"]
    list_filter = ["is_active", "created_at", "created_by"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "created_by"]


    fieldsets = (
        ("Основная информация", {
            "fields": ("title", "description", "is_active", "order"),
            "description": "Создайте тему, а затем добавьте или выберите билеты ниже"
        }),
        ("Служебная информация", {
            "fields": ("created_at", "created_by"),
            "classes": ["collapse"]
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Автоматически устанавливаем created_by для inline билетов"""
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Ticket) and not instance.pk:
                instance.created_by = request.user
            instance.save()
        formset.save_m2m()

    @display(description="Билеты", label=True)
    def tickets_count(self, obj):
        count = obj.tickets.count()
        return count


@admin.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display = [
        "title",
        "theme",
        "created_by",
        "created_at",
        "is_active",
        "questions_count_display"
    ]
    list_filter = ["is_active", "theme", "created_at", "created_by", "is_temporary"]
    search_fields = ["title", "description", "theme__title"]
    readonly_fields = ["created_at", "created_by"]
  # ✨ Можно выбирать/создавать вопросы inline

    fieldsets = (
        ("Основная информация", {
            "fields": ("theme", "title", "description", "is_active", "order"),
            "description": "Создайте билет, а затем добавьте или выберите вопросы ниже"
        }),
        ("Дополнительные параметры", {
            "fields": ("is_temporary", "original_ticket"),
            "classes": ["collapse"]
        }),
        ("Служебная информация", {
            "fields": ("created_at", "created_by"),
            "classes": ["collapse"]
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('theme', 'created_by').prefetch_related('questions')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Автоматически устанавливаем created_by для inline вопросов"""
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Question) and not instance.pk:
                instance.created_by = request.user
            instance.save()
        formset.save_m2m()

    @display(description="Вопросы", label=True)
    def questions_count_display(self, obj):
        count = obj.questions.count()
        return count


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    list_display = [
        "text_preview",
        "ticket",
        "created_by",
        "created_at",
        "is_active",
        "answers_count",
        "image_preview",
    ]
    list_filter = ["is_active", "created_at", "ticket__theme", "created_by"]
    search_fields = ["text", "ticket__title"]
    readonly_fields = ["created_at", "created_by"]
    inlines = [AnswerInline]  # ✨ Можно создавать ответы inline!

    fieldsets = (
        ("Основная информация", {
            "fields": ("ticket", "text", "image", "is_active", "order"),
            "description": "Создайте вопрос и добавьте варианты ответов ниже"
        }),
        ("Служебная информация", {
            "fields": ("created_at", "created_by"),
            "classes": ["collapse"]
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ticket', 'created_by').prefetch_related('answers')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @display(description="Текст вопроса")
    def text_preview(self, obj):
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text

    @display(description="Ответы", label=True)
    def answers_count(self, obj):
        return obj.answers.count()

    @display(description="Изображение")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 5px;" />',
                obj.image.url,
            )
        return "—"


@admin.register(Answer)
class AnswerAdmin(ModelAdmin):
    list_display = ["text_preview", "question", "is_correct", "is_active", "order"]
    list_filter = ["is_correct", "is_active", "question__ticket__theme"]
    search_fields = ["text", "question__text"]

    fieldsets = (
        ("Основная информация", {
            "fields": ("question", "text", "is_correct", "is_active", "order")
        }),
    )

    @display(description="Текст ответа")
    def text_preview(self, obj):
        return obj.text[:80] + "..." if len(obj.text) > 80 else obj.text


@admin.register(UserAnswer)
class UserAnswerAdmin(ModelAdmin):
    list_display = ["user", "question_preview", "is_correct", "answered_at"]
    list_filter = ["is_correct", "answered_at", "question__ticket__theme"]
    search_fields = ["user__username", "question__text"]
    readonly_fields = ["answered_at"]
    filter_horizontal = ["selected_answers"]  # Для ManyToMany поля

    @display(description="Вопрос")
    def question_preview(self, obj):
        return obj.question.text[:80] + "..." if len(obj.question.text) > 80 else obj.question.text


@admin.register(TicketProgress)
class TicketProgressAdmin(ModelAdmin):
    list_display = [
        "user",
        "ticket",
        "current_question_index",
        "is_completed",
        "correct_answers",
        "total_questions",
        "progress_percentage",
        "started_at",
    ]
    list_filter = ["is_completed", "started_at", "ticket__theme"]
    search_fields = ["user__username", "ticket__title"]
    readonly_fields = ["started_at", "completed_at", "time_spent"]

    @display(description="Прогресс")
    def progress_percentage(self, obj):
        if obj.total_questions > 0:
            percentage = (obj.current_question_index / obj.total_questions) * 100
            return f"{percentage:.1f}%"
        return "0%"


@admin.register(Favorites)
class FavoritesAdmin(ModelAdmin):
    list_display = ["user", "content_object", "content_type", "added_at"]
    list_filter = ["content_type", "added_at"]
    search_fields = ["user__username"]
    readonly_fields = ["added_at"]


# ============================================================================
# МАССОВЫЕ ДЕЙСТВИЯ
# ============================================================================

@admin.action(description="✅ Активировать выбранные объекты")
def make_active(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f"Активировано объектов: {updated}")


@admin.action(description="❌ Деактивировать выбранные объекты")
def make_inactive(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"Деактивировано объектов: {updated}")


# Добавляем действия к моделям
ThemeAdmin.actions = [make_active, make_inactive]
TicketAdmin.actions = [make_active, make_inactive]
QuestionAdmin.actions = [make_active, make_inactive]
AnswerAdmin.actions = [make_active, make_inactive]