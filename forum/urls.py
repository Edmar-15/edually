# forum/urls.py
from django.urls import path
from . import views

app_name = "forum"

urlpatterns = [
    path("feeds/", views.feed, name="feed"),
    path("post/<int:pk>/", views.post_detail, name="post_detail"),
    path("post/new/", views.post_create, name="post_create"),
    path("upvote/<int:pk>/", views.upvote, name="upvote"),
]
