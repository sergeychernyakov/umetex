# backend/views.py

from rest_framework import viewsets
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
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
            'languages': Document.LANGUAGES
        }
    )

@csrf_exempt
def upload_document(request):
    if request.method == 'POST' and request.FILES.get('document'):
        document = request.FILES['document']
        new_document = Document(
            title=document.name,
            original_file=document,
            translation_language=request.POST.get('language', 'en')  # Capture selected language
        )
        new_document.save()

        # Call the translate method to generate and save the translated file
        new_document.translate()

        # Simulate total pages for progress simulation
        total_pages = 20  # Example, replace with actual logic

        return JsonResponse({
            'success': True,
            'file_name': new_document.title,
            'translated_file_url': new_document.translated_file.url,
            'total_pages': total_pages,
        })
    return JsonResponse({'success': False})
