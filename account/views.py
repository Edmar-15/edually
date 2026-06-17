# account/views.py
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.conf import settings
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from .models import UserConsent
from django.urls import reverse

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
        
        policy_context = {
            "policy_version": settings.POLICY_VERSION,
            "effective_date": datetime.strptime(
                settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
            ),
        }
    return render(request, "account/register.html", {"form": form, **policy_context})

def landing(request):
    return render(request, "account/landing.html")

@login_required(login_url='account:login')
def dashboard(request):
    return render(request, 'dashboard.html')

@login_required(login_url='account:login')
def profile(request):
    return render(request, 'account/profile.html')


class PolicyBaseView(TemplateView):
    """Common base for both policies – inject version & effective date."""
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["policy_version"] = settings.POLICY_VERSION
        # Convert string → date for nicer display
        context["effective_date"] = datetime.strptime(
            settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
        )
        return context
    

class ConsentRequiredView(TemplateView):
    template_name = "account/consent_required.html"

    @method_decorator(login_required(login_url='account:login'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        # User clicked the "I Agree" button
        UserConsent.objects.update_or_create(
            user=request.user,
            defaults={
                "version": settings.POLICY_VERSION,
                "accepted_at": timezone.now(),
            },
        )
        # Redirect back to where they originally wanted to go
        next_url = request.session.pop("post_consent_redirect", reverse("account:dashboard"))
        return redirect(next_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["policy_version"] = settings.POLICY_VERSION
        ctx["effective_date"] = datetime.strptime(
            settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
        )
        return ctx