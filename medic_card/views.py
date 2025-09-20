from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from medic_auth.models import UserProfile

from .models import Answer, Question, Theme, Ticket, TicketProgress, UserAnswer


def update_user_profile(user, progress):
    """Обновляет профиль пользователя после завершения билета"""
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)

    # Обновляем статистику
    profile.tickets_solved += 1
    profile.correct_answers += progress.correct_answers
    profile.mistakes_made += progress.total_questions - progress.correct_answers
    profile.last_activity = timezone.now()
    profile.save()


def update_original_ticket_from_temp(user, temp_ticket, temp_progress):
    """Обновляет оригинальный билет результатами из временного билета"""
    original_ticket = temp_ticket.original_ticket

    # Получаем прогресс оригинального билета
    try:
        original_progress = TicketProgress.objects.get(
            user=user, ticket=original_ticket
        )
    except TicketProgress.DoesNotExist:
        return

    # Обновляем ответы в оригинальном билете
    temp_questions = temp_ticket.questions.filter(is_active=True)
    for temp_question in temp_questions:
        # Находим соответствующий вопрос в оригинальном билете
        original_question = original_ticket.questions.filter(
            text=temp_question.text
        ).first()

        if original_question:
            # Получаем ответы пользователя на временный вопрос
            temp_user_answer = UserAnswer.objects.filter(
                user=user, question=temp_question
            ).first()

            if temp_user_answer:
                # Обновляем или создаем ответ в оригинальном билете
                original_user_answer, created = UserAnswer.objects.get_or_create(
                    user=user,
                    question=original_question,
                    defaults={"is_correct": temp_user_answer.is_correct},
                )

                if not created:
                    original_user_answer.is_correct = temp_user_answer.is_correct
                    original_user_answer.answered_at = temp_user_answer.answered_at
                    original_user_answer.save()

                # Обновляем выбранные ответы
                original_user_answer.selected_answers.set(
                    temp_user_answer.selected_answers.all()
                )

    # Пересчитываем статистику оригинального билета
    original_questions = original_ticket.questions.filter(is_active=True)
    original_user_answers = UserAnswer.objects.filter(
        user=user, question__in=original_questions
    )
    original_progress.correct_answers = original_user_answers.filter(
        is_correct=True
    ).count()
    original_progress.total_questions = original_questions.count()
    original_progress.save()


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


@login_required
def start_ticket(request, ticket_id):
    """Начать прохождение билета"""
    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)

    # Получаем или создаем прогресс
    progress, created = TicketProgress.objects.get_or_create(
        user=request.user,
        ticket=ticket,
        defaults={
            "total_questions": ticket.questions.filter(is_active=True).count(),
            "current_question_index": 0,
        },
    )

    if not created and progress.is_completed:
        # Если билет уже завершен, предлагаем перерешать
        return redirect("medic_card:ticket_result", ticket_id=ticket_id)

    # Если это новый прогресс или билет не завершен, обновляем время начала
    if created or not progress.is_completed:
        progress.started_at = timezone.now()
        progress.save()

    return redirect(
        "medic_card:take_question",
        ticket_id=ticket_id,
        question_index=progress.current_question_index,
    )


@login_required
def take_question(request, ticket_id, question_index):
    """Страница вопроса для прохождения билета"""
    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
    progress = get_object_or_404(TicketProgress, user=request.user, ticket=ticket)

    questions = ticket.questions.filter(is_active=True).order_by("order", "created_at")
    question_index = int(question_index)

    if question_index >= questions.count():
        # Билет завершен
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.calculate_time_spent()
        progress.save()

        # Обновляем профиль пользователя
        update_user_profile(request.user, progress)

        # Если это временный билет, обновляем оригинальный билет и удаляем временный
        if ticket.is_temporary and ticket.original_ticket:
            update_original_ticket_from_temp(request.user, ticket, progress)
            # Удаляем временный билет
            ticket.delete()
            # Перенаправляем на результаты оригинального билета
            return redirect(
                "medic_card:ticket_result", ticket_id=ticket.original_ticket.id
            )

        return redirect("medic_card:ticket_result", ticket_id=ticket_id)

    question = questions[question_index]
    answers = question.answers.filter(is_active=True).order_by("order", "id")

    # Проверяем, есть ли уже ответ на этот вопрос
    user_answer = UserAnswer.objects.filter(
        user=request.user, question=question
    ).first()

    context = {
        "ticket": ticket,
        "question": question,
        "answers": answers,
        "question_index": question_index,
        "total_questions": questions.count(),
        "progress": progress,
        "user_answer": user_answer,
        "show_result": user_answer is not None,
    }
    return render(request, "medic_card/take_question.html", context)


@login_required
def submit_answer(request, ticket_id, question_index):
    """Обработка ответа пользователя"""
    if request.method != "POST":
        return redirect(
            "medic_card:take_question",
            ticket_id=ticket_id,
            question_index=question_index,
        )

    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
    progress = get_object_or_404(TicketProgress, user=request.user, ticket=ticket)

    questions = ticket.questions.filter(is_active=True).order_by("order", "created_at")
    question_index = int(question_index)

    if question_index >= questions.count():
        return redirect("medic_card:ticket_result", ticket_id=ticket_id)

    question = questions[question_index]
    selected_answer_ids = request.POST.getlist("answers")

    if not selected_answer_ids:
        messages.error(request, "Пожалуйста, выберите хотя бы один ответ")
        return redirect(
            "medic_card:take_question",
            ticket_id=ticket_id,
            question_index=question_index,
        )

    # Получаем выбранные ответы
    selected_answers = Answer.objects.filter(
        id__in=selected_answer_ids, question=question, is_active=True
    )

    # Проверяем правильность ответа
    correct_answers = question.answers.filter(is_correct=True, is_active=True)
    is_correct = set(selected_answers.values_list("id", flat=True)) == set(
        correct_answers.values_list("id", flat=True)
    )

    # Сохраняем или обновляем ответ пользователя
    user_answer, created = UserAnswer.objects.get_or_create(
        user=request.user, question=question, defaults={"is_correct": is_correct}
    )

    # Запоминаем старое состояние для обновления прогресса
    old_correct = user_answer.is_correct

    # Обновляем ответ
    user_answer.is_correct = is_correct
    user_answer.answered_at = timezone.now()
    user_answer.save()

    # Обновляем выбранные ответы
    user_answer.selected_answers.set(selected_answers)

    # Обновляем прогресс
    if created:
        # Новый ответ
        if is_correct:
            progress.correct_answers += 1
    else:
        # Существующий ответ - пересчитываем статистику
        if is_correct and not old_correct:
            progress.correct_answers += 1
        elif not is_correct and old_correct:
            progress.correct_answers = max(0, progress.correct_answers - 1)

    progress.save()

    return redirect(
        "medic_card:take_question", ticket_id=ticket_id, question_index=question_index
    )


@login_required
def next_question(request, ticket_id, question_index):
    """Переход к следующему вопросу"""
    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
    progress = get_object_or_404(TicketProgress, user=request.user, ticket=ticket)

    question_index = int(question_index)

    # Переходим к следующему вопросу
    next_index = question_index + 1
    progress.current_question_index = next_index
    progress.save()

    return redirect(
        "medic_card:take_question", ticket_id=ticket_id, question_index=next_index
    )


@login_required
def ticket_result(request, ticket_id):
    """Результаты прохождения билета"""
    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
    progress = get_object_or_404(TicketProgress, user=request.user, ticket=ticket)

    if not progress.is_completed:
        # Если билет не завершен, завершаем его
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.calculate_time_spent()
        progress.save()

        # Обновляем профиль пользователя
        update_user_profile(request.user, progress)

        # Если это временный билет, обновляем оригинальный билет и удаляем временный
        if ticket.is_temporary and ticket.original_ticket:
            update_original_ticket_from_temp(request.user, ticket, progress)
            # Удаляем временный билет
            ticket.delete()
            # Перенаправляем на результаты оригинального билета
            return redirect(
                "medic_card:ticket_result", ticket_id=ticket.original_ticket.id
            )

    # Получаем все ответы пользователя по билету
    questions = ticket.questions.filter(is_active=True).order_by("order", "created_at")
    user_answers = UserAnswer.objects.filter(
        user=request.user, question__in=questions
    ).select_related("question")

    wrong_answers = user_answers.filter(is_correct=False)

    wrong_answers_count = progress.total_questions - progress.correct_answers

    context = {
        "ticket": ticket,
        "progress": progress,
        "user_answers": user_answers,
        "wrong_answers": wrong_answers,
        "wrong_answers_count": wrong_answers_count,
        "accuracy": (progress.correct_answers / progress.total_questions * 100)
        if progress.total_questions > 0
        else 0,
    }
    return render(request, "medic_card/ticket_result.html", context)


@login_required
def retake_ticket(request, ticket_id, mode="all"):
    """Перерешать билет (весь или только ошибки)"""
    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
    progress = get_object_or_404(TicketProgress, user=request.user, ticket=ticket)

    if mode == "errors":
        # Перерешать только ошибки - создаем временный билет
        wrong_answers = UserAnswer.objects.filter(
            user=request.user, question__ticket=ticket, is_correct=False
        )

        if wrong_answers.exists():
            # Получаем вопросы с ошибками
            wrong_questions = Question.objects.filter(
                id__in=wrong_answers.values_list("question_id", flat=True)
            )

            # Создаем временный билет
            temp_ticket = ticket.create_errors_ticket(request.user, wrong_questions)

            if temp_ticket:
                # Удаляем старые ответы на неправильные вопросы
                wrong_answers.delete()

                # Перенаправляем на временный билет
                return redirect("medic_card:start_ticket", ticket_id=temp_ticket.id)
            else:
                messages.info(request, "Нет ошибок для перерешивания")
                return redirect("medic_card:ticket_result", ticket_id=ticket_id)
        else:
            messages.info(request, "Нет ошибок для перерешивания")
            return redirect("medic_card:ticket_result", ticket_id=ticket_id)
    else:
        # Перерешать весь билет
        UserAnswer.objects.filter(user=request.user, question__ticket=ticket).delete()

        # Сбрасываем весь прогресс
        progress.current_question_index = 0
        progress.is_completed = False
        progress.completed_at = None
        progress.time_spent = None
        progress.started_at = timezone.now()  # Обновляем время начала
        progress.correct_answers = 0
        progress.save()

        # Обновляем профиль пользователя (уменьшаем статистику)
        try:
            profile = UserProfile.objects.get(user=request.user)
            profile.tickets_solved = max(0, profile.tickets_solved - 1)
            profile.correct_answers = max(
                0, profile.correct_answers - progress.correct_answers
            )
            profile.mistakes_made = max(
                0,
                profile.mistakes_made
                - (progress.total_questions - progress.correct_answers),
            )
            profile.save()
        except UserProfile.DoesNotExist:
            pass

    return redirect("medic_card:start_ticket", ticket_id=ticket_id)


def question_detail(request, question_id):
    """Страница вопроса с вариантами ответов"""
    question = get_object_or_404(Question, id=question_id, is_active=True)
    answers = question.answers.filter(is_active=True).order_by("order", "id")
    context = {"question": question, "answers": answers}
    return render(request, "medic_card/question_detail.html", context)
