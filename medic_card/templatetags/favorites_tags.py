from django import template
from django.contrib.contenttypes.models import ContentType

from ..models import Favorites

register = template.Library()


@register.filter
def is_favorite(obj, user):
    """Проверяет, добавлен ли объект в избранное"""
    return Favorites.is_favorite(user, obj)


@register.filter
def content_type_id(obj):
    """Возвращает ID типа контента для объекта"""
    return ContentType.objects.get_for_model(obj).id


@register.filter
def get_progress_color(obj, user):
    """Возвращает цвет прогресса для объекта"""
    return obj.get_progress_color(user)


@register.filter
def get_progress_stats(obj, user):
    """Возвращает статистику прогресса для объекта"""
    return obj.get_user_progress_stats(user)
