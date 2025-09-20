from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import UserProfile


class CustomPasswordValidator:
    def validate(self, password, user=None):
        if len(password) < 4:
            raise ValidationError("Пароль должен содержать минимум 4 символа")
        if not any(char.isdigit() for char in password):
            raise ValidationError("Пароль должен содержать минимум 1 цифру")

    def get_help_text(self):
        return "Пароль должен содержать минимум 4 символа и 1 цифру"


class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        label="Имя пользователя",
        max_length=150,
        help_text=(
            "Обязательно. Не более 150 символов. "
            "Только буквы, цифры и символы @/./+/-/_."
        ),
        error_messages={
            "required": "Это поле обязательно для заполнения",
            "unique": "Пользователь с таким именем уже существует",
        },
    )
    password1 = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput,
        help_text="Пароль должен содержать минимум 4 символа и 1 цифру",
    )
    password2 = forms.CharField(
        label="Подтверждение пароля",
        strip=False,
        widget=forms.PasswordInput,
        help_text="Введите тот же пароль, что и выше, для подтверждения",
    )
    password_hint = forms.CharField(
        label="Подсказка для пароля (необязательно)",
        max_length=200,
        required=False,
        help_text=(
            "Подсказка поможет вспомнить пароль. "
            "⚠️ ВНИМАНИЕ: Подсказка будет показана после 3 неудачных попыток входа, "
            "поэтому не указывайте в ней сам пароль!"
        ),
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    class Meta:
        model = User
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control"})
        self.fields["password1"].widget.attrs.update({"class": "form-control"})
        self.fields["password2"].widget.attrs.update({"class": "form-control"})
        self.fields["password_hint"].widget.attrs.update({"class": "form-control"})

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        validator = CustomPasswordValidator()
        validator.validate(password1)
        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Пароли не совпадают")
        return password2

    def clean_password_hint(self):
        password_hint = self.cleaned_data.get("password_hint", "")
        return password_hint

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            password_hint = self.cleaned_data.get("password_hint", "")
            try:
                profile = user.userprofile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(user=user)
            profile.password_hint = password_hint
            profile.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Имя пользователя",
        max_length=254,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    error_messages = {
        "invalid_login": "Пожалуйста, введите правильные имя пользователя и пароль.",
        "inactive": "Этот аккаунт неактивен.",
    }
