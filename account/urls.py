# account/urls.py
from __future__ import annotations

from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from . import views
from .views import (
    ConsentRequiredView,
    TermsView,
    PrivacyView,
    RoleBasedLoginView,
    EmailVerificationRequiredView,
    change_password,
    anonymous_required,
    verify_email,
)

app_name = "account"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("contact/", views.contact_page, name="contact"),
    path("register/", views.register, name="register"),
    path("login/", anonymous_required(RoleBasedLoginView.as_view()), name="login"),
    path("login/verify-2fa/", views.verify_2fa, name="verify_2fa"),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page=reverse_lazy("landing")),
        name="logout",
    ),
    path("logout-confirm/", views.logout_confirm, name="logout_confirm"),
    path("consent-required/", ConsentRequiredView.as_view(), name="consent_required"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name='profile'),
    path("profile/edit/", views.profile_edit, name='profile_edit'),
    path("profile/password-change/", change_password, name='password_change'),
    path("settings/add-password/", views.add_password, name="add_password"),
    path("profile/modal/<int:pk>/", views.profile_modal, name='profile_modal'),
    path("settings/", views.settings, name='settings'),
    path("settings/delete-modal/", views.delete_account_modal, name="delete_account_modal"),
    path("settings/delete/", views.delete_account, name="delete_account"),
    path("api/set-theme/", views.api_set_theme, name='api_set_theme'),
    path("api/push-subscribe/", views.api_push_subscribe, name='api_push_subscribe'),
    path("api/push-unsubscribe/", views.api_push_unsubscribe, name='api_push_unsubscribe'),
    
    # -----------------------------------------------------------------
    #   EMAIL VERIFICATION
    # -----------------------------------------------------------------
    path(
        "email-verification-required/",
        EmailVerificationRequiredView.as_view(),
        name="email_verification_required",
    ),
    path(
        "verify-email/<str:token>/",
        verify_email,
        name="verify_email",
    ),

    # ---------------------------------------------------------
    # OAuth
    # ---------------------------------------------------------
    path("login/google/", views.google_login, name="google_login"),
    path("login/google/callback/", views.google_callback, name="google_callback"),

    # ---------------------------------------------------------
    # Policy pages (real URLs – useful for SEO / screen readers)
    # ---------------------------------------------------------
    path("terms/", TermsView.as_view(), name="terms"),
    path("privacy/", PrivacyView.as_view(), name="privacy"),
    
    # -------------------------------------------------------------
    # ARCHIVE – separate pages for each type
    # -------------------------------------------------------------
    path('archives/', views.archives_home, name='archives-home'),

    #  --- Forum posts ---
    path('archives/forum-posts/', views.archive_forum_post_list,
        name='archive-forum-posts'),
    path('archives/forum-posts/<int:pk>/', views.archive_forum_post_detail,
        name='archive-forum-post-detail'),

    #  --- Modules ---
    path('archives/modules/', views.archive_module_list,
        name='archive-modules'),
    path('archives/modules/<int:pk>/', views.archive_module_detail,
        name='archive-module-detail'),

    #  --- Personal Materials ---
    path('archives/personal-materials/', views.archive_personal_material_list,
        name='archive-personal-materials'),
    path('archives/personal-materials/<int:pk>/',
        views.archive_personal_material_detail,
        name='archive-personal-material-detail'),
    
    # Forum‑post
    path('archives/forum-posts/<int:pk>/delete-modal/',
        views.archive_forum_post_delete_modal,
        name='archive-forum-post-delete-modal'),

    path('archives/forum-posts/<int:pk>/delete/',
        views.archive_forum_post_delete,
        name='archive-forum-post-delete'),

    # Module
    path('archives/modules/<int:pk>/delete-modal/',
        views.archive_module_delete_modal,
        name='archive-module-delete-modal'),

    path('archives/modules/<int:pk>/delete/',
        views.archive_module_delete,
        name='archive-module-delete'),

    # Personal material
    path('archives/personal-materials/<int:pk>/delete-modal/',
        views.archive_personal_material_delete_modal,
        name='archive-personal-material-delete-modal'),

    path('archives/personal-materials/<int:pk>/delete/',
        views.archive_personal_material_delete,
        name='archive-personal-material-delete'),
    path("password-reset/", views.password_reset_request, name="password_reset_request"),
    path("reset-password/", views.password_reset_confirm, name="password_reset_confirm"),
]
