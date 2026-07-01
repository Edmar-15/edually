from django import forms
from django.test import TestCase

from .forms import LoginForm


class LoginFormTests(TestCase):
    def test_login_username_field_uses_email_input(self):
        form = LoginForm()

        self.assertIsInstance(form.fields["username"].widget, forms.EmailInput)
        self.assertEqual(form.fields["username"].widget.attrs["autocomplete"], "username")
