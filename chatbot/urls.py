from django.urls import path

from . import views


app_name = "chatbot"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/chat/", views.send_message, name="send_message"),
    path("api/chat/clear/", views.clear_chat, name="clear_chat"),
    path("api/bundle/", views.get_bundle_details, name="get_bundle_details"),
]