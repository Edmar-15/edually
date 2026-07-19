from __future__ import annotations

from django.urls import path
from . import views

app_name = 'slm'

urlpatterns = [
    path('slm-lists/', views.slmlists, name='slmlists'),

    # -----------------------------------------------------------------
    # SUBJECT API
    # -----------------------------------------------------------------
    path('api/subjects/',               views.api_subject_list,   name='subject-list'),
    path('api/subjects/create/',        views.api_subject_create, name='subject-create'),
    path('api/subjects/<int:pk>/',      views.api_subject_update, name='subject-update'),
    path('api/subjects/<int:pk>/delete/', views.api_subject_delete, name='subject-delete'),
    path('api/subjects/year-choices/', views.api_subject_year_choices, name='subject-year-choices'),

    # -----------------------------------------------------------------
    # SUBJECT > MODULES (list/create)
    # -----------------------------------------------------------------
    path('subjects/<int:subject_id>/modules/', views.subject_modules, name='subject-modules'),

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

    # -----------------------------------------------------------------
    # MODULE CRUD (outside the subject nesting)
    # -----------------------------------------------------------------
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
    path("api/modules/<int:pk>/file/", views.api_module_file_replace, name="module-file-replace"),

    path(
        "subjects/<int:subject_id>/modules/<int:module_id>/",
        views.module_detail,
        name="module-detail",
    ),

    # -----------------------------------------------------------------
    # PERSONAL MATERIAL – CRUD + file‑replace
    # -----------------------------------------------------------------
    path(
        "api/personal-materials/",
        views.api_personal_material_list,
        name="personalmaterial-list",
    ),
    path(
        "api/personal-materials/create/",
        views.api_personal_material_create,
        name="personalmaterial-create",
    ),
    path(
        "api/personal-materials/<int:pk>/",
        views.api_personal_material_update,
        name="personalmaterial-update",
    ),
    path(
        "api/personal-materials/<int:pk>/delete/",
        views.api_personal_material_delete,
        name="personalmaterial-delete",
    ),
    path(
        "api/personal-materials/<int:pk>/file/",
        views.api_personal_material_file_replace,
        name="personalmaterial-file-replace",
    ),

    # -----------------------------------------------------------------
    # NEW – Detail page (preview) for a PersonalMaterial
    # -----------------------------------------------------------------
    path(
        "personal-material/<int:pk>/",
        views.personal_material_detail,
        name="personalmaterial-detail",
    ),
    
    path(
    "api/personal-materials/<int:pk>/highlight/",
    views.api_highlight,
    {"target_type": "personal"},
    name="personalmaterial-highlight",
    ),

    # keep the original, just point it to the same view
    path(
        "api/modules/<int:pk>/highlight/",
        views.api_highlight,
        {"target_type": "module"},
        name="module-highlight",
    ),
    path('module-management/', views.management, name='management'),
    
    # ----- modal endpoints -------------------------------------------------
    path(
        "api/subjects/<int:pk>/edit-modal/",
        views.subject_edit_modal,
        name="subject-edit-modal",
    ),
    path(
        "api/subjects/<int:pk>/delete-modal/",
        views.subject_delete_modal,
        name="subject-delete-modal",
    ),

    path(
        "api/modules/<int:pk>/edit-modal/",
        views.module_edit_modal,
        name="module-edit-modal",
    ),
    path(
        "api/modules/<int:pk>/delete-modal/",
        views.module_delete_modal,
        name="module-delete-modal",
    ),

    path(
        "api/personal-materials/<int:pk>/edit-modal/",
        views.personal_material_edit_modal,
        name="personalmaterial-edit-modal",
    ),
    path(
        "api/personal-materials/<int:pk>/delete-modal/",
        views.personal_material_delete_modal,
        name="personalmaterial-delete-modal",
    ),
]
