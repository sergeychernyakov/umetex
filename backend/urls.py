# backend/urls.py

from django.urls import path
from rest_framework.routers import DefaultRouter
from backend import views

# Set up the routers
router = DefaultRouter()
router.register(r'documents', views.DocumentViewSet)

urlpatterns = [
    path('', views.index, name='index'),  # Assuming index.html is your main page
    path('upload/', views.upload_document, name='upload_document'),  # URL for uploading documents
    path('progress/<int:document_id>/', views.check_translation_progress, name='check_translation_progress'),
]
