from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from .forms import (
    CustomAuthenticationForm,
    CustomPasswordChangeForm,
    CustomUserCreationForm,
    PasswordHintChangeForm,
)
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


@login_required
def profile(request):
    """Личный кабинет пользователя"""
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(user=request.user)

    # Формы для изменения данных
    password_form = CustomPasswordChangeForm(user=request.user)
    # Создаем форму с пустым полем для фразы-подсказки
    hint_form = PasswordHintChangeForm(initial={"password_hint": ""})

    context = {
        "user_profile": user_profile,
        "password_form": password_form,
        "hint_form": hint_form,
    }

    return render(request, "medic_auth/profile.html", context)


@login_required
def change_password(request):
    """Изменение пароля"""
    if request.method == "POST":
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, "Пароль успешно изменен!")
            return redirect("medic_auth:profile")
        else:
            messages.error(
                request, "Ошибка при изменении пароля. Проверьте введенные данные."
            )
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return redirect("medic_auth:profile")


@login_required
def change_password_hint(request):
    """Изменение фразы-подсказки"""
    if request.method == "POST":
        try:
            user_profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            user_profile = UserProfile.objects.create(user=request.user)

        form = PasswordHintChangeForm(request.POST, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Фраза-подсказка успешно обновлена!")
            return redirect("medic_auth:profile")
        else:
            messages.error(request, "Ошибка при обновлении фразы-подсказки.")

    return redirect("medic_auth:profile")
