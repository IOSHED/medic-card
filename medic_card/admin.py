from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from unfold.decorators import display
from django import forms
from django.shortcuts import redirect
from django.urls import path
from django.template.response import TemplateResponse
from django.contrib import messages
from .models import Answer, Question, Theme, Ticket, TicketProgress, UserAnswer, Favorites


# ============================================================================
# ФОРМЫ
# ============================================================================

class QuestionForm(forms.ModelForm):
    """Форма для вопроса с поддержкой множественного выбора билетов"""
    tickets = forms.ModelMultipleChoiceField(
        queryset=Ticket.objects.filter(is_active=True),
        required=True,
        label="Билеты",
        help_text="Выберите один или несколько билетов. Для каждого билета будет создана копия вопроса."
    )

    class Meta:
        model = Question
        fields = ['tickets', 'text', 'image', 'is_active', 'order']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Если редактируем существующий вопрос, показываем текущий билет в множественном выборе
        if self.instance and self.instance.pk:
            self.fields['tickets'].initial = [self.instance.ticket]

    def save(self, commit=True):
        # Сохраняем вопрос только если commit=False, иначе обрабатываем в admin
        return super().save(commit=commit)


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


class QuestionCloneInline(TabularInline):
    """Inline для отображения копий вопроса в других билетах"""
    model = Question
    extra = 0
    can_delete = False
    readonly_fields = ['ticket', 'text_preview', 'is_active']
    verbose_name = "Копия вопроса"
    verbose_name_plural = "Копии этого вопроса в других билетах"
    classes = ['collapse']

    def text_preview(self, obj):
        return obj.text[:80] + "..." if len(obj.text) > 80 else obj.text
    text_preview.short_description = "Текст вопроса"

    def has_add_permission(self, request, obj):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ============================================================================
# ОСНОВНЫЕ АДМИН-КЛАССЫ
# ============================================================================

@admin.register(Theme)
class ThemeAdmin(ModelAdmin):
    list_display = ["title", "created_by", "created_at", "is_active", "tickets_count"]
    list_filter = ["is_active", "created_at", "created_by"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "created_by"]
    inlines = [TicketInline]
    filter_horizontal = []

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
    filter_horizontal = ["themes"]
    inlines = [ThemeInline]

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
    form = QuestionForm
    list_display = [
        "text_preview",
        "ticket",
        "ticket_themes_display",
        "created_by",
        "created_at",
        "is_active",
        "answers_count",
        "image_preview",
        "is_clone_display",
    ]
    list_filter = ["is_active", "created_at", "ticket__themes", "created_by", "original_question"]
    search_fields = ["text", "ticket__title", "ticket__themes__title"]
    readonly_fields = ["created_at", "created_by", "original_question"]
    inlines = [AnswerInline, QuestionCloneInline]

    # Добавляем кастомные действия
    actions = ['clone_questions_to_tickets']

    fieldsets = (
        ("Основная информация", {
            "fields": ("tickets", "text", "image", "is_active", "order"),
            "description": "Выберите один или несколько билетов. Для каждого билета будет создана копия вопроса."
        }),
        ("Информация о клонировании", {
            "fields": ("original_question",),
            "classes": ["collapse"],
            "description": "Если этот вопрос является копией, здесь будет указан оригинал"
        }),
        ("Служебная информация", {
            "fields": ("created_at", "created_by"),
            "classes": ["collapse"]
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Скрываем поле tickets при редактировании существующего вопроса"""
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.pk:
            # При редактировании скрываем множественный выбор билетов
            form.base_fields['tickets'].widget = forms.HiddenInput()
            form.base_fields['tickets'].required = False
        return form

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ticket', 'created_by', 'original_question').prefetch_related('ticket__themes', 'answers')

    def save_model(self, request, obj, form, change):
        """Обрабатываем сохранение вопроса с множественными билетами"""

        if not change:
            # СОЗДАНИЕ НОВОГО ВОПРОСА
            tickets = form.cleaned_data.get('tickets', [])

            if not tickets:
                messages.error(request, "Необходимо выбрать хотя бы один билет")
                return

            # Создаем вопрос для первого билета
            first_ticket = tickets[0]
            obj.ticket = first_ticket
            obj.created_by = request.user

            # Сохраняем основной вопрос
            super().save_model(request, obj, form, change)

            # Создаем копии для остальных билетов
            if len(tickets) > 1:
                created_copies = 0
                for ticket in tickets[1:]:
                    self._create_question_copy(obj, ticket, request.user)
                    created_copies += 1

                if created_copies > 0:
                    messages.success(request, f"Создан вопрос и {created_copies} копий в других билетах")
                else:
                    messages.success(request, "Вопрос успешно создан")
            else:
                messages.success(request, "Вопрос успешно создан")

        else:
            # РЕДАКТИРОВАНИЕ СУЩЕСТВУЮЩЕГО ВОПРОСА
            # Обновляем только текущий вопрос
            if not obj.created_by:
                obj.created_by = request.user
            super().save_model(request, obj, form, change)

            # Также обновляем все копии этого вопроса
            if obj.original_question is None:  # Это оригинальный вопрос
                copies = Question.objects.filter(original_question=obj)
                for copy in copies:
                    copy.text = obj.text
                    copy.image = obj.image
                    copy.is_active = obj.is_active
                    copy.order = obj.order
                    copy.save()

    def _create_question_copy(self, original_question, ticket, user):
        """Создает копию вопроса для указанного билета"""
        copy = Question(
            ticket=ticket,
            text=original_question.text,
            image=original_question.image,
            is_active=original_question.is_active,
            order=original_question.order,
            original_question=original_question,
            created_by=user
        )
        copy.save()

        # Копируем ответы
        for answer in original_question.answers.all():
            Answer.objects.create(
                question=copy,
                text=answer.text,
                is_correct=answer.is_correct,
                is_active=answer.is_active,
                order=answer.order
            )

        return copy

    @display(description="Клон")
    def is_clone_display(self, obj):
        if obj.original_question:
            return "✅ Копия"
        elif obj.question_copies.exists():
            return "📖 Оригинал"
        return "—"

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

    @admin.action(description="📋 Клонировать выбранные вопросы в другие билеты")
    def clone_questions_to_tickets(self, request, queryset):
        """Массовое действие для клонирования вопросов в другие билеты"""
        if 'apply' in request.POST:
            ticket_ids = request.POST.getlist('tickets')
            if not ticket_ids:
                messages.error(request, "Необходимо выбрать билеты для клонирования")
                return redirect(request.get_full_path())

            tickets = Ticket.objects.filter(id__in=ticket_ids, is_active=True)
            cloned_count = 0

            for question in queryset:
                for ticket in tickets:
                    if question.ticket != ticket:  # Не клонируем в тот же билет
                        self._create_question_copy(question, ticket, request.user)
                        cloned_count += 1

            messages.success(request, f"Создано {cloned_count} копий вопросов")
            return redirect(request.get_full_path())

        # Показываем форму выбора билетов
        tickets = Ticket.objects.filter(is_active=True)
        context = {
            'title': "Клонирование вопросов в другие билеты",
            'questions': queryset,
            'tickets': tickets,
            'action': 'clone_questions_to_tickets'
        }
        return TemplateResponse(request, 'admin/clone_questions.html', context)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions['clone_questions_to_tickets'] = (
            QuestionAdmin.clone_questions_to_tickets,
            'clone_questions_to_tickets',
            "📋 Клонировать выбранные вопросы в другие билеты"
        )
        return actions


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


# Остальные admin-классы остаются без изменений
@admin.register(UserAnswer)
class UserAnswerAdmin(ModelAdmin):
    list_display = ["user", "question_preview", "question_ticket_display", "is_correct", "answered_at"]
    list_filter = ["is_correct", "answered_at", "question__ticket__themes"]
    search_fields = ["user__username", "question__text", "question__ticket__title"]
    readonly_fields = ["answered_at"]
    filter_horizontal = ["selected_answers"]

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
QuestionAdmin.actions = [make_active, make_inactive, QuestionAdmin.clone_questions_to_tickets]
AnswerAdmin.actions = [make_active, make_inactive]
