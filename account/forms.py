# account/forms.py
from __future__ import annotations

import re

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm as DjangoUserCreationForm,
    UserChangeForm as DjangoUserChangeForm,
)
from django.utils import timezone

# -----------------------------------------------------------------
# Local imports
# -----------------------------------------------------------------
from .models import UserConsent, StudentProfile, TeacherProfile
from .utils import add_user_to_group
from .constants import GROUP_STUDENT, GROUP_TEACHER

User = get_user_model()


# -----------------------------------------------------------------
#  LOGIN FORM (unchanged)
# -----------------------------------------------------------------
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


# -----------------------------------------------------------------
#  ADMIN‑SIDE USER CREATION / CHANGE FORMS (unchanged)
# -----------------------------------------------------------------
class UserCreationForm(DjangoUserCreationForm):
    """Admin‑side form – only the core authentication fields are exposed."""
    class Meta(DjangoUserCreationForm.Meta):
        model = User
        fields = ("email", "username", "first_name", "last_name", "avatar")


class UserChangeForm(DjangoUserChangeForm):
    """Admin‑side change form – again only core fields."""
    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = "__all__"


# -----------------------------------------------------------------
#  PUBLIC REGISTRATION FORM – works for BOTH students AND teachers
# -----------------------------------------------------------------
class PublicRegisterForm(forms.ModelForm):
    """
    Public registration form that can create either a StudentProfile **or**
    a TeacherProfile, then adds the user to the matching group.
    """
    # ──────  ROLE selector (radio buttons)  ──────
    ROLE_CHOICES = (
        (GROUP_STUDENT, "Student"),
        (GROUP_TEACHER, "Teacher"),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect,
        initial=GROUP_STUDENT,
        label="I am a",
        required=True,
    )

    # ──────  PASSWORD fields  ──────
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

    # ──────  TERMS & CONDITIONS checkbox  ──────
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
        # NOTE: we *don’t* include the profile‑specific fields here – they are extra fields only.
        fields = (
            "email",
            "username",
            "first_name",
            "last_name",
            "avatar",
        )
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "username": forms.TextInput(attrs={"placeholder": "Optional username"}),
        }

    # -----------------------------------------------------------------
    #  STUDENT‑ONLY extra fields (these live only on the form)
    # -----------------------------------------------------------------
    student_id = forms.CharField(
        required=False,
        max_length=30,
        label="Student ID",
        widget=forms.TextInput(attrs={"placeholder": "Enter your student id"}),
    )
    program = forms.CharField(
        required=False,
        max_length=100,
        label="Program / Course",
        widget=forms.TextInput(attrs={"placeholder": "Enter your Program/Course"}),
    )
    year_level = forms.CharField(
        required=False,
        max_length=20,
        label="Year Level",
        widget=forms.TextInput(attrs={"placeholder": "Enter your year level (1st Year)"}),
    )

    # -----------------------------------------------------------------
    #  TEACHER‑ONLY extra fields (these live only on the form)
    # -----------------------------------------------------------------
    employee_id = forms.CharField(
        required=False,
        max_length=30,
        label="Employee ID",
        widget=forms.TextInput(attrs={"placeholder": "Enter your employee id"}),
    )
    department = forms.CharField(
        required=False,
        max_length=100,
        label="Department",
        widget=forms.TextInput(attrs={"placeholder": "Enter your department (CSS)"}),
    )

    # -----------------------------------------------------------------
    #  VALIDATORS
    # -----------------------------------------------------------------
    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if not password:
            return password

        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")

        if not re.search(r"[A-Z]", password):
            raise forms.ValidationError("Password must include at least one uppercase letter.")
        if not re.search(r"\d", password):
            raise forms.ValidationError("Password must include at least one number.")
        if not re.search(r"[!@#$%^&*()_+\-=[\]{};':\\\|,.<>\/?~`]", password):
            raise forms.ValidationError("Password must include at least one special character.")

        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned

    # -----------------------------------------------------------------
    #  SAVE – branch on role and create the correct profile + group
    # -----------------------------------------------------------------
    def save(self, commit=True):
        """
        Create the User, the role‑specific profile, assign the proper group,
        and record the initial consent.
        """
        # ----------- 1️⃣  Pull the role & the extra fields -------------
        role = self.cleaned_data.get("role")   # "Student" or "Teacher"

        # student‑only
        student_id = self.cleaned_data.pop("student_id", "")
        program = self.cleaned_data.pop("program", "")
        year_level = self.cleaned_data.pop("year_level", "")

        # teacher‑only
        employee_id = self.cleaned_data.pop("employee_id", "")
        department = self.cleaned_data.pop("department", "")

        # ----------- 2️⃣  Create the core User object ------------------
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()

            # ---------- 3️⃣  Create the role‑specific profile ----------
            if role == GROUP_STUDENT:
                StudentProfile.objects.create(
                    user=user,
                    student_id=student_id,
                    program=program,
                    year_level=year_level,
                )
                add_user_to_group(user, GROUP_STUDENT)

            elif role == GROUP_TEACHER:
                TeacherProfile.objects.create(
                    user=user,
                    employee_id=employee_id,
                    department=department,
                )
                add_user_to_group(user, GROUP_TEACHER)

            # ---------- 4️⃣  Record consent (unchanged) ----------------
            UserConsent.objects.create(
                user=user,
                version=settings.POLICY_VERSION,
                accepted_at=timezone.now(),
            )
        return user


# -----------------------------------------------------------------
#  PROFILE FORM – unchanged (still edits the Student profile fields)
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
