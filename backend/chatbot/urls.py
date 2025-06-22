
from django.urls import path
from . import views

urlpatterns = [
    path('ask/', views.ask_question, name='ask_question'),
    path('status/', views.service_status, name='service_status'),
    path('search/', views.search_documents, name='search_documents'),
    path('chat-history/', views.chat_history, name='chat_history'),
]