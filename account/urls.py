# account/urls.py
from __future__ import annotations

from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from . import views

app_name = "account"

urlpatterns = [
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="account/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(
            next_page=reverse_lazy("landing")
        ), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name='profile'),
]
