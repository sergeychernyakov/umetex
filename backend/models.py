# backend/models.py

from django.db import models
from uuid import uuid4

class Document(models.Model):
    # Define a list of main languages
    LANGUAGES = [
        ('EN', 'Английский'),       # English
        ('ES', 'Испанский'),        # Spanish
        ('KZ', 'Казахский'),        # Kazakh
        ('DE', 'Немецкий'),         # German
        ('FR', 'Французский'),      # French
        # Add more languages if needed
    ]

    title = models.CharField(max_length=255)
    original_file = models.FileField(upload_to='documents/%Y/%m/%d/originals/')
    translated_file = models.FileField(upload_to='documents/%Y/%m/%d/translations/', blank=True, null=True)
    translation_language = models.CharField(max_length=2, choices=LANGUAGES, blank=False, null=False)  # Required field
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Ensure the files are stored in subfolders named after the document ID
        if not self.pk:
            super().save(*args, **kwargs)  # Save to get a primary key

        original_path = self.get_upload_to('original')
        translation_path = self.get_upload_to('translation')

        self.original_file.field.upload_to = original_path
        self.translated_file.field.upload_to = translation_path

        super().save(*args, **kwargs)

    def get_upload_to(self, file_type):
        """ Returns the upload path for the file depending on its type. """
        folder_name = f'documents/{self.pk}/{file_type}s/'
        return folder_name

    def __str__(self):
        return self.title
