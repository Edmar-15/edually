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
    PasswordChangeForm,
    SetPasswordForm,
)
from django.utils import timezone
from django.forms import DateTimeInput

# -----------------------------------------------------------------
# Local imports
# -----------------------------------------------------------------
from .models import UserConsent, StudentProfile
from .utils import add_user_to_group
from .constants import GROUP_STUDENT

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
#  PUBLIC REGISTRATION FORM – **students only**
# -----------------------------------------------------------------
class PublicRegisterForm(forms.ModelForm):
    """
    Public registration form that creates a StudentProfile, adds the user
    to the Student group, and records the initial consent.
    """
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
        fields = (
            "email",
            "username",
            "first_name",
            "last_name",
            "avatar",
        )
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "username": forms.TextInput(attrs={"placeholder": "Username"}),
        }

    username = forms.CharField(
        required=True,
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={"placeholder": "Username"}),
    )

    # -----------------------------------------------------------------
    #  STUDENT‑ONLY extra fields (these live only on the form)
    # -----------------------------------------------------------------
    student_id = forms.CharField(
        required=True,
        max_length=30,
        label="Student ID",
        widget=forms.TextInput(attrs={"placeholder": "e.g. 20230001"}),
    )
    # PROGRAM is no longer asked – defaults to “Information Technology”

    YEAR_CHOICES = [
        ("2nd Year", "2nd Year"),
        ("3rd Year", "3rd Year"),
    ]
    year_level = forms.ChoiceField(
        required=True,
        choices=YEAR_CHOICES,
        label="Year Level",
    )

    # -----------------------------------------------------------------
    #  VALIDATORS (unchanged)
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
    #  SAVE – always creates a StudentProfile and assigns the Student group
    # -----------------------------------------------------------------
    def save(self, commit=True):
        """
        Create the User, a StudentProfile, assign the student group,
        and record the initial consent.
        """
        # ----------- Pull the student‑only extra fields -------------
        student_id = self.cleaned_data.pop("student_id", "")
        year_level = self.cleaned_data.pop("year_level", "")

        # ----------- Create the core User object ------------------
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()

            # ---------- Create the StudentProfile ----------
            StudentProfile.objects.create(
                user=user,
                student_id=student_id,
                # program defaults automatically to “Information Technology”
                year_level=year_level,
            )
            add_user_to_group(user, GROUP_STUDENT)

            # ---------- Record consent ----------
            UserConsent.objects.create(
                user=user,
                version=settings.POLICY_VERSION,
                accepted_at=timezone.now(),
            )
        return user


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label="Confirm your password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Enter your password to confirm",
                "autocomplete": "current-password",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if self.user is None or not self.user.check_password(password):
            raise forms.ValidationError("Password is incorrect.")
        return password


# -----------------------------------------------------------------
#  PROFILE FORM – unchanged (still edits the Student profile fields)
# -----------------------------------------------------------------
class ProfileForm(forms.ModelForm):
    """Form displayed on the profile page for editing allowed fields."""

    # Extra fields that belong to the StudentProfile
    student_id = forms.CharField(
        required=False, 
        max_length=30, 
        label="Student ID",
        widget=forms.TextInput(attrs={"placeholder": ""})
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "avatar")  # core fields only
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": ""}),
            "last_name": forms.TextInput(attrs={"placeholder": ""}),
        }

    def __init__(self, *args, **kwargs):
        """Populate the extra profile fields if they exist."""
        super().__init__(*args, **kwargs)

        # Set initial values and placeholders to current values
        if self.instance.pk:
            # First name
            if self.instance.first_name:
                self.fields["first_name"].initial = self.instance.first_name
                self.fields["first_name"].widget.attrs["placeholder"] = self.instance.first_name
            
            # Last name
            if self.instance.last_name:
                self.fields["last_name"].initial = self.instance.last_name
                self.fields["last_name"].widget.attrs["placeholder"] = self.instance.last_name
        
        # Student ID from StudentProfile
        if self.instance.pk and hasattr(self.instance, "student_profile"):
            profile = self.instance.student_profile
            if profile.student_id:
                self.fields["student_id"].initial = profile.student_id
                self.fields["student_id"].widget.attrs["placeholder"] = profile.student_id

    def save(self, commit=True):
        """Save core user fields **and** the linked StudentProfile."""
        user = super().save(commit=commit)

        profile, _ = StudentProfile.objects.get_or_create(user=user)
        profile.student_id = self.cleaned_data["student_id"]
        if commit:
            profile.save()
        return user
    
    
class PasswordResetRequestForm(forms.Form):
    """
    First step – ask for the e‑mail address that belongs to
    an existing user.
    """
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}),
        label="E‑mail address",
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if not User.objects.filter(email__iexact=email).exists():
            # Do not reveal whether the e‑mail exists – avoid user‑enumeration.
            raise forms.ValidationError(
                "If an account with that e‑mail exists we will send an OTP."
            )
        return email


class PasswordResetConfirmForm(forms.Form):
    """
    Second step – verify the OTP and set a new password.
    """
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"placeholder": "6‑digit code"}),
        label="One‑time password (OTP)",
    )
    password1 = forms.CharField(
        label="New password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"placeholder": "Create a new password"}
        ),
    )
    password2 = forms.CharField(
        label="Confirm new password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"placeholder": "Confirm your new password"}
        ),
    )

    # -----------------------------------------------------------------
    #  PASSWORD VALIDATORS – exactly the same rules used during registration
    # -----------------------------------------------------------------
    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if not password:
            return password

        if len(password) < 8:
            raise forms.ValidationError(
                "Password must be at least 8 characters long."
            )
        if not re.search(r"[A-Z]", password):
            raise forms.ValidationError(
                "Password must include at least one uppercase letter."
            )
        if not re.search(r"\d", password):
            raise forms.ValidationError(
                "Password must include at least one number."
            )
        if not re.search(r"[!@#$%^&*()_+\-=[\]{};':\\\|,.<>\/?~`]", password):
            raise forms.ValidationError(
                "Password must include at least one special character."
            )
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned
    
    
class ChangePasswordForm(PasswordChangeForm):
    """
    Uses the same password‑strength rules as registration / reset.
    The ``old_password`` field is rendered by the base class; we only
    need to enforce the custom validators on the new passwords.
    """

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1")
        if not password:
            return password

        # ---- validations – identical to those in PublicRegisterForm ----
        if len(password) < 8:
            raise forms.ValidationError(
                "Password must be at least 8 characters long."
            )
        if not re.search(r"[A-Z]", password):
            raise forms.ValidationError(
                "Password must include at least one uppercase letter."
            )
        if not re.search(r"\d", password):
            raise forms.ValidationError(
                "Password must include at least one number."
            )
        if not re.search(r"[!@#$%^&*()_+\-=[\]{};':\\\|,.<>\/?~`]", password):
            raise forms.ValidationError(
                "Password must include at least one special character."
            )
        return password
    

# -------------------------------------------------
#  ADD / SET PASSWORD FORM (OAuth‑only accounts)
# -------------------------------------------------
class AddPasswordForm(SetPasswordForm):
    """
    Same validation rules as ``ChangePasswordForm`` but does NOT
    ask for the old password – perfect for users whose account was
    created with an unusable password (OAuth flow).
    """
    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1")
        if not password:
            return password

        # ---- replicate the custom strength checks from ChangePasswordForm ----
        if len(password) < 8:
            raise forms.ValidationError(
                "Password must be at least 8 characters long."
            )
        if not re.search(r"[A-Z]", password):
            raise forms.ValidationError(
                "Password must include at least one uppercase letter."
            )
        if not re.search(r"\d", password):
            raise forms.ValidationError(
                "Password must include at least one number."
            )
        if not re.search(
            r"[!@#$%^&*()_+\-=[\]{};':\\\|,.<>\/?~`]", password
        ):
            raise forms.ValidationError(
                "Password must include at least one special character."
            )
        return password
