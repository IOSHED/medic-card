from django.contrib import admin
from django.utils.html import format_html

from .models import Answer, Question, Theme, Ticket, UserAnswer


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 1
    fields = ["text", "is_correct", "is_active", "order"]


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ["title", "created_by", "created_at", "is_active", "tickets_count"]
    list_filter = ["is_active", "created_at", "created_by"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at"]

    def tickets_count(self, obj):
        return obj.get_tickets_count()

    tickets_count.short_description = "Количество билетов"


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ["text", "image", "is_active", "order"]
    readonly_fields = ["created_at"]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "theme",
        "created_by",
        "created_at",
        "is_active",
        "questions_count",
    ]
    list_filter = ["is_active", "created_at", "theme", "created_by"]
    search_fields = ["title", "description", "theme__title"]
    readonly_fields = ["created_at"]
    inlines = [QuestionInline]

    def questions_count(self, obj):
        return obj.get_questions_count()

    questions_count.short_description = "Количество вопросов"


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
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
    search_fields = ["text", "ticket__title", "ticket__theme__title"]
    readonly_fields = ["created_at"]
    inlines = [AnswerInline]

    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

    text_preview.short_description = "Текст вопроса"

    def answers_count(self, obj):
        return obj.get_answers_count()

    answers_count.short_description = "Количество ответов"

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 5px;" />',
                obj.image.url,
            )
        return "Нет изображения"

    image_preview.short_description = "Изображение"


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["text_preview", "question", "is_correct", "is_active", "order"]
    list_filter = ["is_correct", "is_active", "question__ticket__theme"]
    search_fields = ["text", "question__text"]

    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

    text_preview.short_description = "Текст ответа"


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ["user", "question_preview", "is_correct", "answered_at"]
    list_filter = ["is_correct", "answered_at", "question__ticket__theme"]
    search_fields = ["user__username", "question__text"]
    readonly_fields = ["answered_at"]

    def question_preview(self, obj):
        return (
            obj.question.text[:50] + "..."
            if len(obj.question.text) > 50
            else obj.question.text
        )

    question_preview.short_description = "Вопрос"
