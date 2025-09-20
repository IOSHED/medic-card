from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from .forms import CustomAuthenticationForm, CustomUserCreationForm
from .models import UserProfile


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация прошла успешно!")
            return redirect("medic_card:home")
    else:
        form = CustomUserCreationForm()
    return render(request, "medic_auth/register.html", {"form": form})


def user_login(request):
    if request.method == "POST":
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            # Сброс счетчика неудачных попыток при успешном входе
            try:
                profile = user.userprofile
                profile.reset_failed_attempts()
            except UserProfile.DoesNotExist:
                pass
            login(request, user)
            messages.success(request, "Вход выполнен успешно!")
            return redirect("medic_card:home")
        else:
            # Обработка неудачных попыток входа
            username = form.cleaned_data.get("username")
            if username:
                try:
                    user = User.objects.get(username=username)
                    profile, created = UserProfile.objects.get_or_create(user=user)
                    profile.increment_failed_attempts()

                    # Если 3 или больше неудачных попыток, показываем подсказку
                    if profile.failed_login_attempts >= 3 and profile.password_hint:
                        messages.warning(
                            request,
                            f"⚠️ Подсказка для восстановления пароля: {profile.password_hint}",
                        )
                except User.DoesNotExist:
                    pass
    else:
        form = CustomAuthenticationForm()
    return render(request, "medic_auth/login.html", {"form": form})


def user_logout(request):
    logout(request)
    messages.info(request, "Вы вышли из системы.")
    return redirect("medic_card:home")
