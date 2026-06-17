from __future__ import annotations

from django.urls import path
from . import views

app_name = 'slm'

urlpatterns = [
    path('slm-lists/', views.slmlists, name='slmlists'),
]
