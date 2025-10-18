from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from medic_card.models import Theme, Ticket, Question


class Site:
    domain = 'test-med.ru'

class StaticViewSitemap(Sitemap):
    """Sitemap для статических страниц"""
    priority = 0.8
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        return ['medic_card:home', 'medic_card:search', 'medic_card:favorites']

    def get_urls(self, site=None, **kwargs):
        site = Site()
        return super(StaticViewSitemap, self).get_urls(site=site, **kwargs)

    def location(self, item):
        return reverse(item)


class ThemeSitemap(Sitemap):
    """Sitemap для тем"""
    changefreq = 'weekly'
    priority = 0.9
    protocol = 'https'


    def items(self):
        return Theme.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.created_at  # Лучше использовать updated_at если есть

    def get_urls(self, site=None, **kwargs):
        site = Site()
        return super(ThemeSitemap, self).get_urls(site=site, **kwargs)


    def location(self, obj):
        return reverse('medic_card:theme_detail', args=[obj.id])


class TicketSitemap(Sitemap):
    """Sitemap для билетов"""
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'


    def items(self):
        return Ticket.objects.filter(is_active=True, is_temporary=False)

    def lastmod(self, obj):
        return obj.created_at

    def get_urls(self, site=None, **kwargs):
        site = Site()
        return super(TicketSitemap, self).get_urls(site=site, **kwargs)


    def location(self, obj):
        return reverse('medic_card:ticket_detail', args=[obj.id])


class QuestionSitemap(Sitemap):
    """Sitemap для вопросов"""
    changefreq = 'monthly'
    priority = 0.6
    protocol = 'https'


    def items(self):
        return Question.objects.filter(
            is_active=True,
            ticket__is_active=True,
            ticket__is_temporary=False
        ).select_related('ticket', 'ticket__theme')

    def lastmod(self, obj):
        return obj.created_at

    def get_urls(self, site=None, **kwargs):
        site = Site()
        return super(QuestionSitemap, self).get_urls(site=site, **kwargs)


    def location(self, obj):
        return reverse('medic_card:question_detail', args=[obj.id])


# Словарь всех sitemap для использования в urls.py
sitemaps = {
    'static': StaticViewSitemap,
    'themes': ThemeSitemap,
    'tickets': TicketSitemap,
    'questions': QuestionSitemap,
}