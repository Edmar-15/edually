# forum/urls.py
from django.urls import path
from . import views

app_name = "forum"

urlpatterns = [
    path("feeds/", views.feed, name="feed"),
    path("post/<int:pk>/", views.post_detail, name="post_detail"),
    path("post/new/", views.post_create, name="post_create"),
    path("post/<int:pk>/edit/", views.post_edit, name="post_edit"),
    path("post/<int:pk>/delete/", views.post_delete, name="post_delete"),
    path("upvote/<int:pk>/", views.upvote, name="upvote"),
    path("reply/<int:reply_id>/upvote/", views.reply_upvote, name="reply_upvote"),
    path("reply/<int:reply_id>/edit/", views.reply_edit, name="reply_edit"),
    path("reply/<int:reply_id>/delete/", views.reply_delete, name="reply_delete"),
    path("flag/<str:content_type>/<int:content_id>/", views.flag_content, name="flag_content"),
    path("post/<int:pk>/verify/", views.verify_post, name="verify_post"),
    path("moderation/", views.moderation_dashboard, name="moderation_dashboard"),
    path("moderation/deleted/", views.moderation_deleted_history, name="moderation_deleted_history"),
    path(
        "moderation/deleted/<str:content_type>/<int:pk>/",
        views.moderation_deleted_content_detail,
        name="moderation_deleted_content_detail",
    ),
    path("moderation/report/<int:report_id>/resolve/", views.resolve_report, name="resolve_report"),
]
