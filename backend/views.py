# backend/views.py

import os
import json
import threading
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
            'languages': Document.LANGUAGES_CHOICES,
            'accept_types': ','.join(settings.SUPPORTED_FILE_FORMATS),
            'max_file_size_mb': settings.MAX_FILE_SIZE_MB
        }
    )

def async_translate(document):
    """
    Function to perform translation asynchronously.
    """
    document.translate()  # Perform the translation

@csrf_exempt
def upload_document(request):
    if request.method == 'POST' and request.FILES.get('document'):
        document = request.FILES['document']
        file_extension = os.path.splitext(document.name)[1].lower()
        file_size_mb = document.size / (1024 * 1024)  # Convert bytes to MB

        # Validate file format
        if file_extension not in settings.SUPPORTED_FILE_FORMATS:
            return JsonResponse({
                'success': False,
                'error': 'Недопустимый формат файла. Пожалуйста, загрузите файл с одним из следующих расширений: ' +
                        ', '.join(settings.SUPPORTED_FILE_FORMATS)
            })

        # Validate file size
        if file_size_mb > settings.MAX_FILE_SIZE_MB:
            return JsonResponse({
                'success': False,
                'error': f'Размер файла превышает максимальный допустимый размер в {settings.MAX_FILE_SIZE_MB} MB.'
            })

        # Save the document and start translation
        new_document = Document(
            title=document.name,
            original_file=document,
            translation_language=request.POST.get('language', 'en')  # Capture selected language
        )
        new_document.save()

        # Start the translation in a separate thread
        translation_thread = threading.Thread(target=async_translate, args=(new_document,))
        translation_thread.start()

        return JsonResponse({
            'document_id': new_document.pk,
            'success': True,
            'file_name': new_document.title
        })
    return JsonResponse({'success': False})

def check_translation_progress(request, document_id):
    """
    Check the translation progress of a specific document.

    :param request: The HTTP request object.
    :param document_id: The ID of the document to check progress for.
    :return: JsonResponse with progress data or an error message.
    """
    progress_file = os.path.join(settings.MEDIA_ROOT, f'{document_id}', f'{document_id}_progress.json')
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            progress_data = json.load(f)
        return JsonResponse(progress_data)
    else:
        return JsonResponse({"error": "Прогресс недоступен"}, status=404)
