from django.urls import path

from . import views

app_name = "medic_card"

urlpatterns = [
    path("", views.home, name="home"),
    path("theme/<int:theme_id>/", views.theme_detail, name="theme_detail"),
    path("ticket/<int:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path("question/<int:question_id>/", views.question_detail, name="question_detail"),
]
