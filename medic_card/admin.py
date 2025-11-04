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

class QuestionCreateForm(forms.ModelForm):
    """Форма для СОЗДАНИЯ вопроса с поддержкой множественного выбора билетов"""
    tickets = forms.ModelMultipleChoiceField(
        queryset=Ticket.objects.filter(is_active=True),
        required=True,
        label="Билеты",
        help_text="Выберите один или несколько билетов. Для каждого билета будет создана копия вопроса."
    )

    class Meta:
        model = Question
        fields = ['text', 'image', 'is_active', 'order']


class QuestionEditForm(forms.ModelForm):
    """Форма для РЕДАКТИРОВАНИЯ существующего вопроса"""

    class Meta:
        model = Question
        fields = ['text', 'image', 'is_active', 'order']


# ============================================================================
# INLINE КЛАССЫ
# ============================================================================

class AnswerInline(TabularInline):
    """Inline для создания ответов при создании/редактировании вопроса"""
    model = Answer
    extra = 4
    min_num = 2
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
    model = Ticket.themes.through
    extra = 1
    verbose_name = "Билет"
    verbose_name_plural = "Билеты в этой теме"
    classes = ['collapse']
    autocomplete_fields = ['ticket']


class ThemeInline(TabularInline):
    """Inline для отображения тем в билете"""
    model = Ticket.themes.through
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
    readonly_fields = ['ticket', 'text_preview', 'is_active', 'created_at']
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

    def get_queryset(self, request):
        # Показываем только копии этого вопроса
        qs = super().get_queryset(request)
        if hasattr(self, 'parent_object') and self.parent_object:
            return qs.filter(original_question=self.parent_object)
        return qs.none()


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
    readonly_fields = ["created_at", "created_by", "original_question", "ticket"]
    inlines = [AnswerInline, QuestionCloneInline]

    actions = ['clone_questions_to_tickets']

    def get_form(self, request, obj=None, **kwargs):
        """
        Используем разные формы для создания и редактирования
        """
        if obj is None:
            # СОЗДАНИЕ нового вопроса
            kwargs['form'] = QuestionCreateForm
        else:
            # РЕДАКТИРОВАНИЕ существующего вопроса
            kwargs['form'] = QuestionEditForm

        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        """
        Разные fieldsets для создания и редактирования
        """
        if obj is None:
            # СОЗДАНИЕ - показываем поле tickets
            return (
                ("Основная информация", {
                    "fields": ("tickets", "text", "image", "is_active", "order"),
                    "description": "Выберите один или несколько билетов. Для каждого билета будет создана копия вопроса."
                }),
            )
        else:
            # РЕДАКТИРОВАНИЕ - показываем обычные поля + информацию о клонировании
            return (
                ("Основная информация", {
                    "fields": ("ticket", "text", "image", "is_active", "order"),
                    "description": "Редактирование вопроса. Изменения применятся ко всем копиям этого вопроса."
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

    def get_inline_instances(self, request, obj=None):
        """
        Передаем parent_object в inline для правильного отображения копий
        """
        inline_instances = super().get_inline_instances(request, obj)
        for inline in inline_instances:
            if isinstance(inline, QuestionCloneInline):
                inline.parent_object = obj
        return inline_instances

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ticket', 'created_by', 'original_question').prefetch_related('ticket__themes', 'answers')

    def save_model(self, request, obj, form, change):
        """Обрабатываем сохранение вопроса с множественными билетами"""

        if not change:
            # ========== СОЗДАНИЕ НОВОГО ВОПРОСА ==========
            tickets = form.cleaned_data.get('tickets', [])

            if not tickets:
                messages.error(request, "Необходимо выбрать хотя бы один билет")
                return

            # Создаем вопрос для первого билета (это будет оригинал)
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

                messages.success(request, f"Создан вопрос и {created_copies} копий в других билетах")
            else:
                messages.success(request, "Вопрос успешно создан")

        else:
            # ========== РЕДАКТИРОВАНИЕ СУЩЕСТВУЮЩЕГО ВОПРОСА ==========
            if not obj.created_by:
                obj.created_by = request.user
            super().save_model(request, obj, form, change)

            # Также обновляем все копии этого вопроса
            if obj.original_question is None:  # Это оригинальный вопрос
                copies = Question.objects.filter(original_question=obj)
                update_count = 0
                for copy in copies:
                    copy.text = obj.text
                    copy.image = obj.image
                    copy.is_active = obj.is_active
                    copy.order = obj.order
                    copy.save()
                    update_count += 1

                if update_count > 0:
                    messages.info(request, f"Обновлено {update_count} копий этого вопроса")

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
            return format_html(
                '✅ Копия (<a href="{}">{}</a>)',
                f'../question/{obj.original_question.id}/change/',
                obj.original_question.text[:50] + "..." if len(obj.original_question.text) > 50 else obj.original_question.text
            )
        elif obj.question_copies.exists():
            copy_count = obj.question_copies.count()
            return format_html('📖 Оригинал ({} копий)', copy_count)
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
