from django.urls import path

from . import views

app_name = "medic_card"

urlpatterns = [
    path("", views.home, name="home"),
]
