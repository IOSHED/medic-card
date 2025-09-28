from django.urls import path

from . import views

app_name = "medic_card"

urlpatterns = [
    path("", views.home, name="home"),
    path('search/', views.search, name='search'),
    path("theme/<int:theme_id>/", views.theme_detail, name="theme_detail"),
    path("ticket/<int:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path("question/<int:question_id>/", views.question_detail, name="question_detail"),
    # Интерактивное прохождение билетов
    path("ticket/<int:ticket_id>/start/", views.start_ticket, name="start_ticket"),
    path(
        "ticket/<int:ticket_id>/question/<int:question_index>/",
        views.take_question,
        name="take_question",
    ),
    path(
        "ticket/<int:ticket_id>/question/<int:question_index>/submit/",
        views.submit_answer,
        name="submit_answer",
    ),
    path(
        "ticket/<int:ticket_id>/question/<int:question_index>/next/",
        views.next_question,
        name="next_question",
    ),
    path("ticket/<int:ticket_id>/result/", views.ticket_result, name="ticket_result"),
    path(
        "ticket/<int:ticket_id>/retake/<str:mode>/",
        views.retake_ticket,
        name="retake_ticket",
    ),
    # Избранное
    path("favorites/", views.favorites_list, name="favorites"),
    path("toggle-favorite/", views.toggle_favorite, name="toggle_favorite"),
    # AJAX эндпоинты
    path("get-errors-count/", views.get_errors_count, name="get_errors_count"),
    # Работа над ошибками
    path("errors-work/", views.errors_work, name="errors_work"),
    path(
        "errors-work/result/",
        views.errors_work_result,
        name="errors_work_result",
    ),
]
