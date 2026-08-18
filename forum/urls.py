from django.urls import path
from . import views

app_name = 'forum'

urlpatterns = [
    path('', views.forum_list, name='list'),
    path('feed/', views.feed_redirect, name='feed'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('create/', views.create_post, name='create'),
    path('post/create/', views.create_post, name='post_create'),
    path('post/<int:post_id>/reply/', views.create_reply, name='create_reply'),
    path('post/<int:post_id>/upvote/', views.upvote_post, name='upvote_post'),
    path('upvote/<int:post_id>/', views.upvote_post, name='upvote'),
    path('reply/<int:reply_id>/upvote/', views.upvote_reply, name='upvote_reply'),
    path('reply/<int:reply_id>/upvote/', views.upvote_reply, name='reply_upvote'),
    path('notifications/', views.notifications, name='notifications'),
    path('moderation/', views.moderation_dashboard, name='moderation_dashboard'),
    path('moderation/deleted-history/', views.moderation_deleted_history, name='moderation_deleted_history'),
    path('moderation/deleted-history/<str:content_type>/<int:content_id>/', views.moderation_deleted_content_detail, name='moderation_deleted_content_detail'),
    path('flag/<str:content_type>/<int:content_id>/', views.flag_content, name='flag_content'),
    path('post/<int:post_id>/edit/', views.post_edit, name='post_edit'),
    path('post/<int:post_id>/archive/', views.post_archive, name='post_archive'),
    path('post/<int:post_id>/verify/', views.verify_post, name='verify_post'),
    path('reply/<int:reply_id>/edit/', views.reply_edit, name='reply_edit'),
    path('reply/<int:reply_id>/delete/', views.reply_delete, name='reply_delete'),
    path('notification/<int:notification_id>/goto/', views.notification_goto, name='notification_goto'),
    path('notifications/mark-all-read/', views.notification_mark_all_read, name='notification_mark_all_read'),
    path('reports/<int:report_id>/resolve/', views.resolve_report, name='resolve_report'),
    path('conversation-map/<int:post_id>/', views.conversation_map_json, name='conversation_map_json'),
]
