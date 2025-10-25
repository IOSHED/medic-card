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


class TicketInline(TabularInline):
    """Inline для отображения билетов в теме"""
    model = Ticket.themes.through  # Используем промежуточную модель
    extra = 1
    verbose_name = "Билет"
    verbose_name_plural = "Билеты в этой теме"
    classes = ['collapse']
    autocomplete_fields = ['ticket']


class ThemeInline(TabularInline):
    """Inline для отображения тем в билете"""
    model = Ticket.themes.through  # Используем промежуточную модель
    extra = 1
    verbose_name = "Тема"
    verbose_name_plural = "Темы билета"
    classes = ['collapse']
    autocomplete_fields = ['theme']


# ============================================================================
# ОСНОВНЫЕ АДМИН-КЛАССЫ
# ============================================================================

@admin.register(Theme)
class ThemeAdmin(ModelAdmin):
    list_display = ["title", "created_by", "created_at", "is_active", "tickets_count"]
    list_filter = ["is_active", "created_at", "created_by"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "created_by"]
    inlines = [TicketInline]  # Inline для управления билетами темы
    filter_horizontal = []  # Убрали, так как используем inline

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

    @display(description="Билеты", label=True)
    def tickets_count(self, obj):
        count = obj.tickets.count()
        return count

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tickets')


@admin.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display = [
        "title",
        "themes_display",
        "created_by",
        "created_at",
        "is_active",
        "questions_count_display",
        "is_temporary"
    ]
    list_filter = ["is_active", "themes", "created_at", "created_by", "is_temporary"]
    search_fields = ["title", "description", "themes__title"]
    readonly_fields = ["created_at", "created_by"]
    filter_horizontal = ["themes"]  # Для выбора нескольких тем
    inlines = [ThemeInline]  # Inline для управления темами билета

    fieldsets = (
        ("Основная информация", {
            "fields": ("themes", "title", "description", "is_active", "order"),
            "description": "Создайте билет и выберите темы, к которым он относится"
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
        return super().get_queryset(request).select_related('created_by').prefetch_related('themes', 'questions')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @display(description="Темы")
    def themes_display(self, obj):
        themes = obj.themes.all()
        if themes:
            return ", ".join([theme.title for theme in themes[:3]]) + ("..." if themes.count() > 3 else "")
        return "—"

    @display(description="Вопросы", label=True)
    def questions_count_display(self, obj):
        count = obj.questions.count()
        return count


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    list_display = [
        "text_preview",
        "ticket",
        "ticket_themes_display",
        "created_by",
        "created_at",
        "is_active",
        "answers_count",
        "image_preview",
    ]
    list_filter = ["is_active", "created_at", "ticket__themes", "created_by"]
    search_fields = ["text", "ticket__title", "ticket__themes__title"]
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
        return super().get_queryset(request).select_related('ticket', 'created_by').prefetch_related('ticket__themes', 'answers')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @display(description="Текст вопроса")
    def text_preview(self, obj):
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text

    @display(description="Темы билета")
    def ticket_themes_display(self, obj):
        themes = obj.ticket.themes.all()
        if themes:
            return ", ".join([theme.title for theme in themes[:2]]) + ("..." if themes.count() > 2 else "")
        return "—"

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
    list_display = ["text_preview", "question", "question_ticket_display", "is_correct", "is_active", "order"]
    list_filter = ["is_correct", "is_active", "question__ticket__themes"]
    search_fields = ["text", "question__text", "question__ticket__title"]

    fieldsets = (
        ("Основная информация", {
            "fields": ("question", "text", "is_correct", "is_active", "order")
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('question__ticket').prefetch_related('question__ticket__themes')

    @display(description="Текст ответа")
    def text_preview(self, obj):
        return obj.text[:80] + "..." if len(obj.text) > 80 else obj.text

    @display(description="Билет вопроса")
    def question_ticket_display(self, obj):
        return obj.question.ticket.title


@admin.register(UserAnswer)
class UserAnswerAdmin(ModelAdmin):
    list_display = ["user", "question_preview", "question_ticket_display", "is_correct", "answered_at"]
    list_filter = ["is_correct", "answered_at", "question__ticket__themes"]
    search_fields = ["user__username", "question__text", "question__ticket__title"]
    readonly_fields = ["answered_at"]
    filter_horizontal = ["selected_answers"]  # Для ManyToMany поля

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'question__ticket').prefetch_related('question__ticket__themes')

    @display(description="Вопрос")
    def question_preview(self, obj):
        return obj.question.text[:80] + "..." if len(obj.question.text) > 80 else obj.question.text

    @display(description="Билет")
    def question_ticket_display(self, obj):
        return obj.question.ticket.title


@admin.register(TicketProgress)
class TicketProgressAdmin(ModelAdmin):
    list_display = [
        "user",
        "ticket",
        "ticket_themes_display",
        "current_question_index",
        "is_completed",
        "correct_answers",
        "total_questions",
        "progress_percentage",
        "started_at",
    ]
    list_filter = ["is_completed", "started_at", "ticket__themes"]
    search_fields = ["user__username", "ticket__title", "ticket__themes__title"]
    readonly_fields = ["started_at", "completed_at", "time_spent"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'ticket').prefetch_related('ticket__themes')

    @display(description="Прогресс")
    def progress_percentage(self, obj):
        if obj.total_questions > 0:
            percentage = (obj.current_question_index / obj.total_questions) * 100
            return f"{percentage:.1f}%"
        return "0%"

    @display(description="Темы билета")
    def ticket_themes_display(self, obj):
        themes = obj.ticket.themes.all()
        if themes:
            return ", ".join([theme.title for theme in themes[:2]]) + ("..." if themes.count() > 2 else "")
        return "—"


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
