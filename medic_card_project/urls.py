from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("medic_card.urls")),
    path("auth/", include("medic_auth.urls")),
]
