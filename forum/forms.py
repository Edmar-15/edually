# forum/forms.py
from django import forms
from .models import Post, Reply, Category


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["category", "title", "content"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "input", "placeholder": "Enter a concise title"}
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "textarea",
                    "rows": 6,
                    "placeholder": "Describe your question in detail…",
                }
            ),
            "category": forms.Select(attrs={"class": "select"}),
        }


class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "textarea",
                    "rows": 3,
                    "placeholder": "Write your reply…",
                }
            )
        }
