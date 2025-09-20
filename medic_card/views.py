from django.shortcuts import get_object_or_404, render

from .models import Question, Theme, Ticket


def home(request):
    """Главная страница со списком тем"""
    themes = Theme.objects.filter(is_active=True).order_by("order", "created_at")
    context = {"themes": themes}
    return render(request, "medic_card/home.html", context)


def theme_detail(request, theme_id):
    """Страница темы со списком билетов"""
    theme = get_object_or_404(Theme, id=theme_id, is_active=True)
    tickets = theme.tickets.filter(is_active=True).order_by("order", "created_at")
    context = {"theme": theme, "tickets": tickets}
    return render(request, "medic_card/theme_detail.html", context)


def ticket_detail(request, ticket_id):
    """Страница билета со списком вопросов"""
    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
    questions = ticket.questions.filter(is_active=True).order_by("order", "created_at")
    context = {"ticket": ticket, "questions": questions}
    return render(request, "medic_card/ticket_detail.html", context)


def question_detail(request, question_id):
    """Страница вопроса с вариантами ответов"""
    question = get_object_or_404(Question, id=question_id, is_active=True)
    answers = question.answers.filter(is_active=True).order_by("order", "id")
    context = {"question": question, "answers": answers}
    return render(request, "medic_card/question_detail.html", context)
