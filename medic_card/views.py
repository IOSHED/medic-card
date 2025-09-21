import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from medic_auth.models import UserProfile

from .models import (
    Answer,
    Favorites,
    Question,
    Theme,
    Ticket,
    TicketProgress,
    UserAnswer,
)

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

@ratelimit(key='ip', rate='200/h')
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

@ratelimit(key='ip', rate='200/h')
def home(request):
    """Главная страница со списком тем"""
    themes = Theme.objects.filter(is_active=True).order_by("order", "created_at")
    context = {"themes": themes}
    return render(request, "medic_card/home.html", context)

@ratelimit(key='ip', rate='200/h')
def theme_detail(request, theme_id):
    """Страница темы со списком билетов"""
    theme = get_object_or_404(Theme, id=theme_id, is_active=True)
    tickets = theme.tickets.filter(is_active=True).order_by("order", "created_at")
    context = {"theme": theme, "tickets": tickets}
    return render(request, "medic_card/theme_detail.html", context)

@ratelimit(key='ip', rate='200/h')
def ticket_detail(request, ticket_id):
    """Страница билета со списком вопросов"""
    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
    questions = ticket.questions.filter(is_active=True).order_by("order", "created_at")
    context = {"ticket": ticket, "questions": questions}
    return render(request, "medic_card/ticket_detail.html", context)

@ratelimit(key='ip', rate='200/h')
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

@ratelimit(key='ip', rate='200/h')
@login_required
def take_question(request, ticket_id, question_index):
    """Страница вопроса для прохождения билета"""
    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
    progress = get_object_or_404(TicketProgress, user=request.user, ticket=ticket)

    # Получаем вопросы в сохраненном порядке или создаем новый порядок
    questions = progress.get_questions_in_order()

    # Если это перерешивание (временный билет или сброс прогресса), перемешиваем вопросы
    if (
        ticket.is_temporary or progress.current_question_index == 0
    ) and not progress.question_order:
        random.shuffle(questions)
        progress.set_questions_order(questions)

    question_index = int(question_index)

    if question_index >= len(questions):
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
    # Получаем ответы и перемешиваем их
    answers = list(question.answers.filter(is_active=True).order_by("order", "id"))
    random.shuffle(answers)

    # Проверяем, есть ли уже ответ на этот вопрос
    user_answer = UserAnswer.objects.filter(
        user=request.user, question=question
    ).first()

    context = {
        "ticket": ticket,
        "question": question,
        "answers": answers,
        "question_index": question_index,
        "total_questions": len(questions),
        "progress": progress,
        "user_answer": user_answer,
        "show_result": user_answer is not None,
    }
    return render(request, "medic_card/take_question.html", context)

@ratelimit(key='ip', rate='200/h')
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

    # Получаем вопросы в сохраненном порядке
    questions = progress.get_questions_in_order()

    question_index = int(question_index)

    if question_index >= len(questions):
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

@ratelimit(key='ip', rate='200/h')
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

@ratelimit(key='ip', rate='200/h')
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

@ratelimit(key='ip', rate='200/h')
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
        progress.question_order = (
            None  # Сбрасываем порядок вопросов для нового перемешивания
        )
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

@ratelimit(key='ip', rate='200/h')
def question_detail(request, question_id):
    """Страница вопроса с вариантами ответов"""
    question = get_object_or_404(Question, id=question_id, is_active=True)
    answers = question.answers.filter(is_active=True).order_by("order", "id")
    context = {"question": question, "answers": answers}
    return render(request, "medic_card/question_detail.html", context)

@ratelimit(key='ip', rate='200/h')
@login_required
@require_http_methods(["POST"])
def toggle_favorite(request):
    """AJAX-обработчик для добавления/удаления из избранного"""
    try:
        content_type_id = request.POST.get("content_type_id")
        object_id = request.POST.get("object_id")

        if not content_type_id or not object_id:
            return JsonResponse({"success": False, "message": "Неверные параметры"})

        content_type = ContentType.objects.get(id=content_type_id)
        model_class = content_type.model_class()
        obj = get_object_or_404(model_class, id=object_id)

        is_favorite, message = Favorites.toggle_favorite(request.user, obj)

        return JsonResponse(
            {"success": True, "is_favorite": is_favorite, "message": message}
        )

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

@ratelimit(key='ip', rate='200/h')
@login_required
def favorites_list(request):
    """Страница избранного"""
    favorites = Favorites.objects.filter(user=request.user).prefetch_related(
        "content_object"
    )

    # Разделяем на темы и билеты
    themes = []
    tickets = []

    for favorite in favorites:
        if isinstance(favorite.content_object, Theme):
            themes.append(favorite.content_object)
        elif isinstance(favorite.content_object, Ticket):
            tickets.append(favorite.content_object)

    # Объединяем и сортируем по времени добавления
    all_items = []
    for favorite in favorites:
        all_items.append(
            {
                "object": favorite.content_object,
                "added_at": favorite.added_at,
                "type": "theme"
                if isinstance(favorite.content_object, Theme)
                else "ticket",
            }
        )

    # Сортируем по времени добавления (от новых к старым)
    all_items.sort(key=lambda x: x["added_at"], reverse=True)

    context = {"all_items": all_items, "themes": themes, "tickets": tickets}
    return render(request, "medic_card/favorites.html", context)

@login_required
def errors_work(request):
    """Страница работы над ошибками - показывает все ошибки пользователя"""
    # Получаем все неправильные ответы пользователя
    wrong_answers = (
        UserAnswer.objects.filter(user=request.user, is_correct=False)
        .select_related("question", "question__ticket", "question__ticket__theme")
        .order_by("-answered_at")
    )

    # Группируем ошибки по темам и билетам
    errors_by_theme = {}
    total_errors = wrong_answers.count()

    for answer in wrong_answers:
        theme = answer.question.ticket.theme
        ticket = answer.question.ticket

        if theme.id not in errors_by_theme:
            errors_by_theme[theme.id] = {"theme": theme, "tickets": {}}

        if ticket.id not in errors_by_theme[theme.id]["tickets"]:
            errors_by_theme[theme.id]["tickets"][ticket.id] = {
                "ticket": ticket,
                "errors": [],
            }

        errors_by_theme[theme.id]["tickets"][ticket.id]["errors"].append(answer)

    # Создаем временный билет со всеми ошибками
    if request.method == "POST" and wrong_answers.exists():
        # Сохраняем исходное количество ошибок в сессии
        request.session['initial_errors_count'] = total_errors

        # Получаем все вопросы с ошибками
        wrong_questions = Question.objects.filter(
            id__in=wrong_answers.values_list("question_id", flat=True)
        ).distinct()

        # Создаем временный билет
        temp_ticket = Ticket.objects.create(
            theme=Theme.objects.first(),
            title="Работа над ошибками",
            description="Временный билет для перерешивания всех ошибок пользователя",
            created_by=request.user,
            is_active=True,
            is_temporary=True,
            original_ticket=None,
        )

        # Копируем все вопросы с ошибками
        for question in wrong_questions:
            new_question = Question.objects.create(
                ticket=temp_ticket,
                text=question.text,
                image=question.image,
                created_by=request.user,
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

        # Перенаправляем на временный билет
        return redirect("medic_card:start_ticket", ticket_id=temp_ticket.id)

    context = {
        "errors_by_theme": errors_by_theme,
        "total_errors": total_errors,
        "has_errors": total_errors > 0,
    }
    return render(request, "medic_card/errors_work.html", context)

@login_required
def errors_work_result(request, errors_count):
    """Результаты работы над ошибками - показывает оставшиеся ошибки"""
    # Получаем исходное количество ошибок из сессии
    initial_errors_count = request.session.get('initial_errors_count', 0)

    # Получаем все текущие неправильные ответы пользователя
    current_wrong_answers = (
        UserAnswer.objects.filter(user=request.user, is_correct=False)
        .select_related("question", "question__ticket", "question__ticket__theme")
        .order_by("-answered_at")
    )

    current_errors_count = current_wrong_answers.count()

    # Вычисляем количество исправленных ошибок
    corrected_errors = initial_errors_count - current_errors_count

    # Группируем оставшиеся ошибки по темам и билетам
    errors_by_theme = {}

    for answer in current_wrong_answers:
        theme = answer.question.ticket.theme
        ticket = answer.question.ticket

        if theme.id not in errors_by_theme:
            errors_by_theme[theme.id] = {"theme": theme, "tickets": {}}

        if ticket.id not in errors_by_theme[theme.id]["tickets"]:
            errors_by_theme[theme.id]["tickets"][ticket.id] = {
                "ticket": ticket,
                "errors": [],
            }

        errors_by_theme[theme.id]["tickets"][ticket.id]["errors"].append(answer)

    # Обработка POST-запроса для создания нового билета
    if request.method == "POST" and current_errors_count > 0:
        # Создаем новый билет из оставшихся ошибок
        wrong_questions = Question.objects.filter(
            id__in=current_wrong_answers.values_list("question_id", flat=True)
        ).distinct()

        if wrong_questions.exists():
            temp_ticket = Ticket.objects.create(
                theme=Theme.objects.first(),
                title="Работа над ошибками",
                description="Временный билет для перерешивания оставшихся ошибок",
                created_by=request.user,
                is_active=True,
                is_temporary=True,
                original_ticket=None,
            )

            # Копируем вопросы с оставшимися ошибками
            for question in wrong_questions:
                new_question = Question.objects.create(
                    ticket=temp_ticket,
                    text=question.text,
                    image=question.image,
                    created_by=request.user,
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

            # Обновляем счетчик ошибок в сессии для следующего подхода
            request.session['initial_errors_count'] = current_errors_count

            # Перенаправляем на новый временный билет
            return redirect("medic_card:start_ticket", ticket_id=temp_ticket.id)

    context = {
        "errors_by_theme": errors_by_theme,
        "initial_errors_count": initial_errors_count,
        "current_errors_count": current_errors_count,
        "corrected_errors": corrected_errors,
        "has_errors": current_errors_count > 0,
        "errors_count": current_errors_count,  # Для использования в шаблоне
    }
    return render(request, "medic_card/errors_work_result.html", context)