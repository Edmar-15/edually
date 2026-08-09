# forum/forms.py
import re

from django import forms
from .models import Post, Reply, Category

BAD_WORDS = {
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "bastard",
    "damn",
    "crap",
    "dick",
    "piss",
    "hell",
    "slut",
    "putang ina",
    "puta",
    "tangina",
    "tanginang",
    "pucha",
    "pakyu",
    "gago",
    "tarantado",
    "ulol",
    "bobo",
    "tanga",
}

BAD_WORD_PATTERN = re.compile(r"\b(?:" + r"|".join(re.escape(word) for word in BAD_WORDS) + r")\b", re.IGNORECASE)


def contains_bad_word(text: str) -> bool:
    if not text:
        return False
    return bool(BAD_WORD_PATTERN.search(text))


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

    def clean_title(self):
        title = self.cleaned_data.get("title", "")
        if contains_bad_word(title):
            raise forms.ValidationError(
                "Your title contains inappropriate language. Please remove any profanity before posting."
            )
        return title

    def clean_content(self):
        content = self.cleaned_data.get("content", "")
        if contains_bad_word(content):
            raise forms.ValidationError(
                "Your post content contains inappropriate language. Please remove any profanity before posting."
            )
        return content


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

    def clean_content(self):
        content = self.cleaned_data.get("content", "")
        if contains_bad_word(content):
            raise forms.ValidationError(
                "Your reply contains inappropriate language. Please remove any profanity before posting."
            )
        return content
