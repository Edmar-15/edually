from __future__ import annotations

from django.urls import path
from . import views

app_name = 'slm'

urlpatterns = [
    path('slm-lists/', views.slmlists, name='slmlists'),
    path('api/subjects/',               views.api_subject_list,   name='subject-list'),
    path('api/subjects/create/',        views.api_subject_create, name='subject-create'),
    path('api/subjects/<int:pk>/',      views.api_subject_update, name='subject-update'),
    path('api/subjects/<int:pk>/delete/', views.api_subject_delete, name='subject-delete'),
    path('subjects/<int:subject_id>/modules/', views.subject_modules, name='subject-modules'),
    path('api/subjects/year-choices/', views.api_subject_year_choices, name='subject-year-choices'),
    # ---- MODULE API -------------------------------------------------
    # List + create modules for a given subject
    path(
        "api/subjects/<int:subject_id>/modules/",
        views.api_module_list,
        name="module-list",
    ),
    path(
        "api/subjects/<int:subject_id>/modules/create/",
        views.api_module_create,
        name="module-create",
    ),

    # CRUD for a single module (outside the subject nesting)
    path(
        "api/modules/<int:pk>/",
        views.api_module_update,
        name="module-update",
    ),
    path(
        "api/modules/<int:pk>/delete/",
        views.api_module_delete,
        name="module-delete",
    ),
    # optional file‑replace endpoint
    path("api/modules/<int:pk>/file/", views.api_module_file_replace, name="module-file-replace"),
]
