# aihelper/urls.py
from django.urls import path
from . import views

app_name = "aihelper"

urlpatterns = [
    path("helper/", views.helper, name="helper"),
    path("helper/api/", views.helper_api, name="helper_api"),
    path("helper/list_conversations/", views.list_conversations, name="list_conversations"),
    path(
        "helper/get_conversation/<int:pk>/",
        views.get_conversation,
        name="get_conversation",
    ),
]
