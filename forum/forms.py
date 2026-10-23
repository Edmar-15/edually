from django import forms

from .models import Post, Reply, Category


class PostForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=True,
    )

    class Meta:
        model = Post
        fields = ('title', 'content', 'category')
        widgets = {
            'content': forms.Textarea(
                attrs={
                    'class': 'edit-content-textarea',
                    'rows': 4,
                    'placeholder': 'Write your discussion content...',
                }
            ),
        }


class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ('content',)
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Share your thoughts, insights, or solutions...',
            }),
        }