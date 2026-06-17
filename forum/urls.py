from __future__ import annotations

from django.urls import path
from . import views

app_name = 'forum'

urlpatterns = [
    path('feeds/', views.feed, name='feed'),
]
