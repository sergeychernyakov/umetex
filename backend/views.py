# backend/views.py

from rest_framework import viewsets
from django.shortcuts import render
from .models import Document
from .serializers import DocumentSerializer

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

# New view to serve the React frontend
def index(request):
    return render(request, 'index.html')
