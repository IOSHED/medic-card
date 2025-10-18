from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.http import HttpResponse

from .sitemap import sitemaps


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        f"Sitemap: https://test-med.ru/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


urlpatterns = [
    path("admin/cucumber-with-salary/", admin.site.urls),
    path("", include("medic_card.urls")),
    path("auth/", include("medic_auth.urls")),
    # Sitemap
    path(
        'sitemap.xml',
        sitemap,
        {'sitemaps': sitemaps},
        name='django.contrib.sitemaps.views.sitemap'
    ),
    path('robots.txt', robots_txt),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)