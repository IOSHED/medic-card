from django.urls import path

from . import views

app_name = "medic_auth"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("profile/change-password/", views.change_password, name="change_password"),
    path(
        "profile/change-hint/", views.change_password_hint, name="change_password_hint"
    ),
]
