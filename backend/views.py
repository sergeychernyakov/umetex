# backend/views.py

from rest_framework import viewsets
from django.conf import settings
from django.shortcuts import render
from django.core.paginator import Paginator
from .models import Document
from .serializers import DocumentSerializer

class DocumentViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing documents.
    """
    queryset = Document.objects.all().order_by('-uploaded_at')
    serializer_class = DocumentSerializer

# View for rendering the main index.html page
def index(request):
    documents = Document.objects.all().order_by('-uploaded_at')
    paginator = Paginator(documents, 10)  # Show 10 documents per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        'index.html',
        {
            'page_obj': page_obj,
            'supported_formats': settings.SUPPORTED_FILE_FORMATS,
        }
    )
