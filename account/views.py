# account/views.py
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from .forms import PublicRegisterForm

User = get_user_model()

def register(request):
    if request.method == "POST":
        form = PublicRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            raw_password = form.cleaned_data["password1"]
            user = authenticate(request, email=user.email, password=raw_password)
            if user is not None:
                auth_login(request, user)
                messages.success(request, "Welcome! Your account has been created.")
                return redirect(reverse_lazy("account:dashboard"))
            else:
                messages.warning(request, "Account created but auto‑login failed. Please log in.")
                return redirect(reverse_lazy("account:login"))
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = PublicRegisterForm()
    return render(request, "account/register.html", {"form": form})

def landing(request):
    return render(request, "account/landing.html")

@login_required(login_url='account:login')
def dashboard(request):
    return render(request, 'dashboard.html')

@login_required(login_url='account:login')
def profile(request):
    return render(request, 'account/profile.html')