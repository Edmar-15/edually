"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from account.views import landing
from django.conf import settings
from django.conf.urls.static import static
from core import views as pwa_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('account/', include(('account.urls', 'account'), namespace='account')),
    path("", landing, name="landing"),
    path("forum/", include(("forum.urls", "forum"), namespace="forum")),
    path("aihelper/", include('aihelper.urls')),
    path('slm/', include('slm.urls')),
    path('offline/', pwa_views.offline, name='offline'),

    # ------------------------------------------------------------------
    # 2️⃣ Manifest (served by the view)
    # ------------------------------------------------------------------
    path('manifest.json', pwa_views.manifest, name='manifest'),

    # ------------------------------------------------------------------
    # 3️⃣ Service‑worker (served by the view at the site root)
    # ------------------------------------------------------------------
    path('service-worker.js', pwa_views.service_worker, name='service-worker'),
]

if settings.DEBUG:
    # This will map /static/... → <PROJECT_ROOT>/staticfiles/... for development
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # This will map /media/... → <PROJECT_ROOT>/media/...
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)