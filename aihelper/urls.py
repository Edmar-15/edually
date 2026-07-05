# urls.py
from __future__ import annotations

from django.urls import path
from . import views

app_name = "aihelper"

urlpatterns = [
    path("helper/", views.helper, name="helper"),
    # <-- the tiny JSON endpoint used by the front‑end
    path("helper/api/", views.helper_api, name="helper_api"),
]
