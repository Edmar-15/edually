# account/forms.py
from __future__ import annotations

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm as DjangoUserCreationForm,
    UserChangeForm as DjangoUserChangeForm,
)
from django.utils import timezone

from .models import UserConsent, StudentProfile
from .utils import add_user_to_group
from .constants import GROUP_STUDENT

User = get_user_model()


class LoginForm(AuthenticationForm):
    """
    The default authentication form, but we replace the username widget with an
    EmailInput so the placeholder reads “Email address”.  The backend that
    authenticates will still accept username or email.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget = forms.EmailInput(
            attrs={"placeholder": "Email Address", "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update(
            {"placeholder": "Password", "autocomplete": "current-password"}
        )


class UserCreationForm(DjangoUserCreationForm):
    """
    Admin‑side form – only the core authentication fields are exposed.
    """
    class Meta(DjangoUserCreationForm.Meta):
        model = User
        fields = ("email", "username", "first_name", "last_name", "avatar")


class UserChangeForm(DjangoUserChangeForm):
    """
    Admin‑side change form – again only core fields.
    """
    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = "__all__"


class PublicRegisterForm(forms.ModelForm):
    """
    Public registration form that creates a **User** *and* a related
    ``StudentProfile``, then adds the user to the ``Student`` group.
    """
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
            '<a href="{% url "account:terms" %}" target="_blank">Terms &amp; Conditions</a> '
            "and the "
            '<a href="{% url "account:privacy" %}" target="_blank">Privacy Notice</a>.'
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

    # -----------------------------------------------------------------
    # The three student‑specific fields are **not** on the User model
    # any more, but we keep them in the form so we can capture them.
    # -----------------------------------------------------------------
    student_id = forms.CharField(required=False, max_length=30, label="Student ID")
    program = forms.CharField(required=False, max_length=100, label="Program / Course")
    year_level = forms.CharField(required=False, max_length=20, label="Year Level")

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
        Create the ``User`` and the related ``StudentProfile``,
        add the user to the ``Student`` group, and create the initial
        ``UserConsent`` record.
        """
        # Grab the student‑specific data **before** we pop them from cleaned_data.
        student_id = self.cleaned_data.pop("student_id", "")
        program = self.cleaned_data.pop("program", "")
        year_level = self.cleaned_data.pop("year_level", "")

        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()

            # ---- 1️⃣  Create the StudentProfile ----
            StudentProfile.objects.create(
                user=user,
                student_id=student_id,
                program=program,
                year_level=year_level,
            )

            # ---- 2️⃣  Assign the Student group ----
            add_user_to_group(user, GROUP_STUDENT)

            # ---- 3️⃣  Record consent ----
            UserConsent.objects.create(
                user=user,
                version=settings.POLICY_VERSION,
                accepted_at=timezone.now(),
            )
        return user


# -----------------------------------------------------------------
#   PROFILE FORM – used on the “My profile” page.  It edits both the
#   core User fields *and* the related StudentProfile fields.
# -----------------------------------------------------------------
class ProfileForm(forms.ModelForm):
    """Form displayed on the profile page for editing allowed fields."""

    # Extra fields that belong to the StudentProfile
    student_id = forms.CharField(required=False, max_length=30, label="Student ID")
    program = forms.CharField(required=False, max_length=100, label="Program / Course")
    year_level = forms.CharField(required=False, max_length=20, label="Year Level")

    class Meta:
        model = User
        fields = ("first_name", "last_name", "avatar")  # core fields only

    def __init__(self, *args, **kwargs):
        """Populate the extra profile fields if they exist."""
        super().__init__(*args, **kwargs)

        if self.instance.pk and hasattr(self.instance, "student_profile"):
            profile = self.instance.student_profile
            self.fields["student_id"].initial = profile.student_id
            self.fields["program"].initial = profile.program
            self.fields["year_level"].initial = profile.year_level

    def save(self, commit=True):
        """Save core user fields **and** the linked StudentProfile."""
        user = super().save(commit=commit)

        profile, _ = StudentProfile.objects.get_or_create(user=user)
        profile.student_id = self.cleaned_data["student_id"]
        profile.program = self.cleaned_data["program"]
        profile.year_level = self.cleaned_data["year_level"]
        if commit:
            profile.save()
        return user
