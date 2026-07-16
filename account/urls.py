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
)

app_name = "account"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),
    path("login/", RoleBasedLoginView.as_view(), name="login"),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page=reverse_lazy("landing")),
        name="logout",
    ),
    path("logout-confirm/", views.logout_confirm, name="logout_confirm"),
    path("consent-required/", ConsentRequiredView.as_view(), name="consent_required"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name='profile'),
    path("profile/modal/<int:pk>/", views.profile_modal, name='profile_modal'),
    path("settings/", views.settings, name='settings'),
    path("notifications/", views.notifications_inbox, name="notifications"),
    path("api/set-theme/", views.api_set_theme, name='api_set_theme'),

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
]
