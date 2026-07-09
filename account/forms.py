# account/forms.py
from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm as DjangoUserCreationForm,
    UserChangeForm as DjangoUserChangeForm,
)
from django.utils import timezone
from django.conf import settings
from .models import UserConsent

User = get_user_model()


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget = forms.EmailInput(
            attrs={"placeholder": "Email Address", "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update(
            {"placeholder": "Password", "autocomplete": "current-password"}
        )


class UserCreationForm(DjangoUserCreationForm):
    class Meta(DjangoUserCreationForm.Meta):
        model = User
        fields = (
            "email",
            "username",
            "first_name",
            "last_name",
            "avatar",
            "student_id",
            "program",
            "year_level",
        )


class UserChangeForm(DjangoUserChangeForm):
    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = "__all__"


class PublicRegisterForm(forms.ModelForm):

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Create a password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm your password"}),
    )

    accept_terms = forms.BooleanField(
        label=(
            "I have read and agree to the "
            "<a href=\"{% url 'account:terms' %}\" target=\"_blank\">Terms &amp; Conditions</a> "
            "and the <a href=\"{% url 'account:privacy' %}\" target=\"_blank\">Privacy Notice</a>."
        ),
        required=True,
    )

    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "first_name",
            "last_name",
            "avatar",
            "student_id",
            "program",
            "year_level",
        )
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "username": forms.TextInput(attrs={"placeholder": "Optional username"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        """
        Save the user and also create a UserConsent record with the current policy version.
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            # Record consent
            UserConsent.objects.create(
                user=user,
                version=settings.POLICY_VERSION,
                accepted_at=timezone.now(),
            )
        return user


# -----------------------------------------------------------------
# NEW – PROFILE FORM (used on the profile page)
# -----------------------------------------------------------------
class ProfileForm(forms.ModelForm):
    """Form displayed on the profile page for editing allowed fields."""
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "avatar",
            "student_id",
            "program",
            "year_level",
        )
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
            "avatar": forms.ClearableFileInput(),
            "student_id": forms.TextInput(attrs={"placeholder": "e.g. 0323‑4526"}),
            "program": forms.TextInput(attrs={"placeholder": "e.g. Information Technology"}),
            "year_level": forms.TextInput(attrs={"placeholder": "e.g. 3rd Year"}),
        }

    def clean(self):
        cleaned = super().clean()
        # No special validation needed now, but you can add checks here.
        return cleaned
