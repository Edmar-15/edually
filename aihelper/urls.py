from __future__ import annotations

from  django.urls import path
from . import views

app_name = 'aihelper'

urlpatterns = [
    path('helper/', views.helper, name='helper'),
]
