import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import cache_page
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

# medic_card/views.py
from django.db.models import Q
from django.shortcuts import render
from django.http import JsonResponse
from .models import Theme, Ticket, Question, Answer

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

@cache_page(86400 / 4)
@ratelimit(key="ip", rate="100/h")
def home(request):
    """Главная страница со списком тем"""
    themes = Theme.objects.filter(is_active=True).order_by("order", "created_at")
    context = {"themes": themes}
    return render(request, "medic_card/home.html", context)

@cache_page(86400 / 4)
@ratelimit(key="ip", rate="100/h")
def theme_detail(request, theme_id):
    """Страница темы со списком билетов"""
    theme = get_object_or_404(Theme, id=theme_id, is_active=True)
    tickets = theme.tickets.filter(is_active=True, is_temporary=False).order_by(
        "order", "created_at"
    )
    context = {"theme": theme, "tickets": tickets}
    return render(request, "medic_card/theme_detail.html", context)

@cache_page(86400 / 4)
@ratelimit(key="ip", rate="100/h")
def ticket_detail(request, ticket_id):
    """Страница билета со списком вопросов"""
    ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
    questions = ticket.questions.filter(is_active=True).order_by("order", "created_at")
    context = {"ticket": ticket, "questions": questions}
    return render(request, "medic_card/ticket_detail.html", context)


@ratelimit(key="ip", rate="100/h")
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


@ratelimit(key="ip", rate="100/h")
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

        # Если это временный билет, обновляем оригинальный билет и удаляем временный
        if ticket.is_temporary and ticket.original_ticket:
            update_original_ticket_from_temp(request.user, ticket, progress)
            # Обновляем профиль пользователя только для обычных временных билетов
            update_user_profile(request.user, progress)
            # Удаляем временный билет
            ticket.delete()
            # Перенаправляем на результаты оригинального билета
            return redirect(
                "medic_card:ticket_result", ticket_id=ticket.original_ticket.id
            )

        # Если это работа над ошибками (временный билет без original_ticket)
        if ticket.is_temporary and not ticket.original_ticket:
            # Очищаем сессию (результаты уже обновлены в submit_answer)
            if "errors_work_question_mapping" in request.session:
                del request.session["errors_work_question_mapping"]
            if "initial_errors_count" in request.session:
                del request.session["initial_errors_count"]
            # Удаляем временный билет
            ticket.delete()
            # Перенаправляем на результаты работы над ошибками
            return redirect("medic_card:errors_work_result")

        # Обновляем профиль пользователя для обычных билетов
        update_user_profile(request.user, progress)

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


@ratelimit(key="ip", rate="100/h")
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

    # Если это работа над ошибками (временный билет без original_ticket),
    # сразу обновляем оригинальный билет
    if ticket.is_temporary and not ticket.original_ticket:
        if is_correct:
            # Если вопрос решен правильно, удаляем все неправильные ответы с таким же текстом вопроса
            UserAnswer.objects.filter(
                user=request.user, question__text=question.text, is_correct=False
            ).delete()
        else:
            # Если вопрос решен неправильно, находим оригинальный вопрос по тексту
            try:
                original_question = (
                    Question.objects.filter(text=question.text, is_active=True)
                    .exclude(ticket__is_temporary=True)
                    .first()
                )

                if original_question:
                    # Обновляем или создаем ответ в оригинальном билете
                    original_user_answer, created = UserAnswer.objects.get_or_create(
                        user=request.user,
                        question=original_question,
                        defaults={"is_correct": is_correct},
                    )

                    if not created:
                        original_user_answer.is_correct = is_correct
                        original_user_answer.answered_at = timezone.now()
                        original_user_answer.save()

                    # Обновляем выбранные ответы
                    original_user_answer.selected_answers.set(selected_answers)

            except Exception:
                pass

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


@ratelimit(key="ip", rate="100/h")
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


@ratelimit(key="ip", rate="100/h")
@login_required
def ticket_result(request, ticket_id):
    """Результаты прохождения билета"""
    try:
        ticket = Ticket.objects.get(id=ticket_id, is_active=True)
    except Ticket.DoesNotExist:
        # Если билет не найден, возможно это был временный билет для работы над ошибками
        # Проверяем, есть ли маппинг в сессии
        if "errors_work_question_mapping" in request.session:
            # Перенаправляем на результаты работы над ошибками
            return redirect("medic_card:errors_work_result")
        else:
            # Обычная 404 ошибка
            from django.http import Http404

            raise Http404("Билет не найден")

    progress = get_object_or_404(TicketProgress, user=request.user, ticket=ticket)

    if not progress.is_completed:
        # Если билет не завершен, завершаем его
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.calculate_time_spent()
        progress.save()

        # Если это временный билет, обновляем оригинальный билет и удаляем временный
        if ticket.is_temporary and ticket.original_ticket:
            update_original_ticket_from_temp(request.user, ticket, progress)
            # Обновляем профиль пользователя только для обычных временных билетов
            update_user_profile(request.user, progress)
            # Удаляем временный билет
            ticket.delete()
            # Перенаправляем на результаты оригинального билета
            return redirect(
                "medic_card:ticket_result", ticket_id=ticket.original_ticket.id
            )

        # Если это работа над ошибками (временный билет без original_ticket)
        if ticket.is_temporary and not ticket.original_ticket:
            # Очищаем сессию (результаты уже обновлены в submit_answer)
            if "errors_work_question_mapping" in request.session:
                del request.session["errors_work_question_mapping"]
            if "initial_errors_count" in request.session:
                del request.session["initial_errors_count"]
            # Удаляем временный билет
            ticket.delete()
            # Перенаправляем на результаты работы над ошибками
            return redirect("medic_card:errors_work_result")

        # Обновляем профиль пользователя для обычных билетов
        update_user_profile(request.user, progress)

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


@ratelimit(key="ip", rate="100/h")
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


@ratelimit(key="ip", rate="100/h")
def question_detail(request, question_id):
    """Страница вопроса с вариантами ответов"""
    question = get_object_or_404(Question, id=question_id, is_active=True)
    answers = question.answers.filter(is_active=True).order_by("order", "id")
    context = {"question": question, "answers": answers}
    return render(request, "medic_card/question_detail.html", context)


@ratelimit(key="ip", rate="100/h")
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


@ratelimit(key="ip", rate="100/h")
@login_required
@require_http_methods(["GET"])
def get_errors_count(request):
    """AJAX-обработчик для получения текущего количества ошибок"""
    try:
        # Получаем все текущие неправильные ответы пользователя
        current_errors_count = UserAnswer.objects.filter(
            user=request.user, is_correct=False
        ).count()

        # Получаем изначальное количество ошибок из сессии
        initial_errors_count = request.session.get("initial_errors_count", 0)

        # Вычисляем количество исправленных ошибок
        corrected_errors = max(0, initial_errors_count - current_errors_count)

        return JsonResponse(
            {
                "success": True,
                "current_errors_count": current_errors_count,
                "initial_errors_count": initial_errors_count,
                "corrected_errors": corrected_errors,
                "debug": {
                    "initial_errors_count": initial_errors_count,
                    "current_errors_count": current_errors_count,
                },
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


@ratelimit(key="ip", rate="100/h")
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
        .prefetch_related("selected_answers")
        .order_by("-answered_at")
    )

    request.session["initial_errors_count"] = len(wrong_answers)

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
        # Сохраняем изначальное количество ошибок в сессии
        request.session["initial_errors_count"] = total_errors

        # Получаем все вопросы с ошибками
        wrong_question_ids = list(
            wrong_answers.values_list("question_id", flat=True).distinct()
        )
        wrong_questions = Question.objects.filter(
            id__in=wrong_question_ids
        ).prefetch_related("answers")

        # Создаем временный билет для работы над ошибками
        temp_ticket = Ticket.objects.create(
            theme=Theme.objects.first(),
            title="Работа над ошибками",
            description="Временный билет для перерешивания всех ошибок пользователя",
            created_by=request.user,
            is_active=True,
            is_temporary=True,
            original_ticket=None,  # Специальный маркер для работы над ошибками
        )

        # Сохраняем связь между новыми вопросами и оригинальными
        question_mapping = {}

        # Копируем все вопросы с ошибками
        for question in wrong_questions:
            new_question = Question.objects.create(
                ticket=temp_ticket,
                text=question.text,
                image=question.image,
                created_by=request.user,
                is_active=True,
            )

            # Сохраняем связь между новым и оригинальным вопросом
            question_mapping[new_question.id] = question.id

            # Копируем ответы
            for answer in question.answers.filter(is_active=True):
                Answer.objects.create(
                    question=new_question,
                    text=answer.text,
                    is_correct=answer.is_correct,
                    is_active=True,
                    order=answer.order,
                )

        # Сохраняем маппинг вопросов в сессии для последующего обновления
        request.session["errors_work_question_mapping"] = question_mapping

        # Перенаправляем на временный билет
        return redirect("medic_card:start_ticket", ticket_id=temp_ticket.id)

    context = {
        "errors_by_theme": errors_by_theme,
        "total_errors": total_errors,
        "current_errors_count": total_errors,  # Добавлено для консистентности
    }
    return render(request, "medic_card/errors_work.html", context)


@login_required
def errors_work_result(request):
    """Результаты работы над ошибками - показывает оставшиеся ошибки"""
    # Получаем изначальное количество ошибок из сессии
    initial_errors_count = request.session.get("initial_errors_count", 0)

    # Получаем все текущие неправильные ответы пользователя
    current_wrong_answers = (
        UserAnswer.objects.filter(user=request.user, is_correct=False)
        .select_related("question", "question__ticket", "question__ticket__theme")
        .prefetch_related("selected_answers")
        .order_by("-answered_at")
    )

    current_errors_count = current_wrong_answers.count()

    # Вычисляем количество исправленных ошибок
    corrected_errors = max(0, initial_errors_count - current_errors_count)

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
        wrong_question_ids = current_wrong_answers.values_list(
            "question_id", flat=True
        ).distinct()
        wrong_questions = Question.objects.filter(
            id__in=wrong_question_ids
        ).prefetch_related("answers")

        if wrong_questions.exists():
            # Обновляем изначальное количество ошибок в сессии
            request.session["initial_errors_count"] = current_errors_count

            temp_ticket = Ticket.objects.create(
                theme=Theme.objects.first(),
                title="Работа над ошибками",
                description="Временный билет для перерешивания оставшихся ошибок",
                created_by=request.user,
                is_active=True,
                is_temporary=True,
                original_ticket=None,
            )

            # Сохраняем связь между новыми вопросами и оригинальными
            question_mapping = {}

            # Копируем вопросы с оставшимися ошибками
            for question in wrong_questions:
                new_question = Question.objects.create(
                    ticket=temp_ticket,
                    text=question.text,
                    image=question.image,
                    created_by=request.user,
                    is_active=True,
                )

                # Сохраняем связь между новым и оригинальным вопросом
                question_mapping[new_question.id] = question.id

                # Копируем ответы
                for answer in question.answers.filter(is_active=True):
                    Answer.objects.create(
                        question=new_question,
                        text=answer.text,
                        is_correct=answer.is_correct,
                        is_active=True,
                        order=answer.order,
                    )

            # Сохраняем маппинг вопросов в сессии для последующего обновления
            request.session["errors_work_question_mapping"] = question_mapping

            # Перенаправляем на новый временный билет
            return redirect("medic_card:start_ticket", ticket_id=temp_ticket.id)

    context = {
        "errors_by_theme": errors_by_theme,
        "initial_errors_count": initial_errors_count,
        "current_errors_count": current_errors_count,
        "corrected_errors": corrected_errors,
    }
    return render(request, "medic_card/errors_work_result.html", context)


from django.db.models import Q, Value, When, Case, IntegerField

from django.db.models import Q, Value, IntegerField, Case, When
from django.db.models.functions import Lower, Length
import difflib

def search(request):
    """Улучшенный поиск с учетом релевантности, опечаток и регистра"""
    query = request.GET.get('q', '').strip()
    results = {
        'themes': [],
        'tickets': [],
        'questions': [],
    }

    if not query:
        context = {
            'query': query,
            'results': results,
            'has_results': False,
        }
        return render(request, 'medic_card/search_results.html', context)

    # Нормализация запроса
    query_lower = query.lower().strip()
    query_words = query_lower.split()

    def create_search_q(fields, search_query):
        """Создает Q-объекты для поиска с различными стратегиями"""
        q_objects = Q()

        for field in fields:
            # Точное совпадение (игнорируя регистр)
            q_objects |= Q(**{f"{field}__iexact": search_query})

            # Начинается с запроса
            q_objects |= Q(**{f"{field}__istartswith": search_query})

            # Содержит все слова запроса (по порядку)
            q_objects |= Q(**{f"{field}__icontains": search_query})

            # Содержит любое из слов запроса
            for word in query_words:
                if len(word) > 2:  # Игнорируем короткие слова
                    q_objects |= Q(**{f"{field}__icontains": word})

        return q_objects

    def calculate_similarity(text1, text2):
        """Вычисляет схожесть между двумя строками"""
        if not text1 or not text2:
            return 0
        return difflib.SequenceMatcher(
            None,
            text1.lower(),
            text2.lower()
        ).ratio()

    def annotate_relevance(queryset, fields, search_query):
        """Аннотирует queryset релевантностью"""
        when_conditions = []

        for field in fields:
            # Высший приоритет: точное совпадение
            when_conditions.append(
                When(**{f"{field}__iexact": search_query}, then=Value(100))
            )
            # Высокий приоритет: начинается с запроса
            when_conditions.append(
                When(**{f"{field}__istartswith": search_query}, then=Value(80))
            )
            # Средний приоритет: содержит всю фразу
            when_conditions.append(
                When(**{f"{field}__icontains": search_query}, then=Value(60))
            )
            # Низкий приоритет: содержит отдельные слова
            for i, word in enumerate(query_words):
                if len(word) > 2:
                    when_conditions.append(
                        When(**{f"{field}__icontains": word}, then=Value(40 - i))
                    )

        return queryset.annotate(
            relevance=Case(
                *when_conditions,
                default=Value(0),
                output_field=IntegerField()
            ),
            title_length=Length(fields[0]) if fields else Value(0)
        ).order_by('-relevance', 'title_length')

    # Основной поиск
    themes_base = Theme.objects.filter(
        create_search_q(['title', 'description'], query_lower),
        is_active=True
    ).select_related('created_by').distinct()

    tickets_base = Ticket.objects.filter(
        create_search_q(['title', 'description'], query_lower),
        is_active=True
    ).select_related('theme', 'created_by').distinct()

    questions_base = Question.objects.filter(
        create_search_q(['text'], query_lower),
        is_active=True
    ).select_related('ticket', 'ticket__theme', 'created_by').distinct()

    # Аннотация релевантности
    results['themes'] = annotate_relevance(themes_base, ['title', 'description'], query_lower)
    results['tickets'] = annotate_relevance(tickets_base, ['title', 'description'], query_lower)
    results['questions'] = annotate_relevance(questions_base, ['text'], query_lower)

    # Подсчет общего количества результатов
    total_results = (
            results['themes'].count() +
            results['tickets'].count() +
            results['questions'].count()
    )

    # Если результатов мало, добавляем похожие
    if total_results < 8:
        similarity_threshold = 0.4

        def find_similar(model_queryset, fields, original_results):
            """Находит похожие результаты на основе схожести строк"""
            similar_results = []
            original_ids = [obj.id for obj in original_results]

            for obj in model_queryset.exclude(id__in=original_ids)[:20]:  # Ограничиваем для производительности
                max_similarity = 0
                for field in fields:
                    field_value = getattr(obj, field, '')
                    if field_value:
                        similarity = calculate_similarity(query, field_value)
                        max_similarity = max(max_similarity, similarity)

                if max_similarity >= similarity_threshold:
                    similar_results.append((obj, max_similarity))

            # Сортируем по схожести
            similar_results.sort(key=lambda x: x[1], reverse=True)
            return [result[0] for result in similar_results[:8 - total_results]]

        # Добавляем похожие результаты для каждой категории
        if len(results['themes']) < 5:
            similar_themes = find_similar(
                Theme.objects.filter(is_active=True),
                ['title', 'description'],
                results['themes']
            )
            results['themes'] = list(results['themes']) + similar_themes

        if len(results['tickets']) < 5:
            similar_tickets = find_similar(
                Ticket.objects.filter(is_active=True),
                ['title', 'description'],
                results['tickets']
            )
            results['tickets'] = list(results['tickets']) + similar_tickets

        if len(results['questions']) < 5:
            similar_questions = find_similar(
                Question.objects.filter(is_active=True),
                ['text'],
                results['questions']
            )
            results['questions'] = list(results['questions']) + similar_questions

    # Ограничиваем количество результатов если их много
    MAX_RESULTS_PER_CATEGORY = 10
    for key in results:
        if hasattr(results[key], 'count'):
            results[key] = results[key][:MAX_RESULTS_PER_CATEGORY]
        elif len(results[key]) > MAX_RESULTS_PER_CATEGORY:
            results[key] = results[key][:MAX_RESULTS_PER_CATEGORY]

    context = {
        'query': query,
        'results': results,
        'has_results': any(len(results[key]) > 0 for key in results),
        'total_results': total_results,
    }

    return render(request, 'medic_card/search_results.html', context)