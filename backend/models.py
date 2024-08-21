# backend/models.py

from django.db import models

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
    original_file = models.FileField(upload_to='%(document_id)s/originals/')
    translated_file = models.FileField(upload_to='%(document_id)s/translations/', blank=True, null=True)
    translation_language = models.CharField(max_length=2, choices=LANGUAGES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Ensure the files are stored in subfolders named after the document ID
        if not self.pk:
            super().save(*args, **kwargs)  # Save to get a primary key

        # Custom paths based on the document ID
        self.original_file.field.upload_to = f'{self.pk}/originals/'
        self.translated_file.field.upload_to = f'{self.pk}/translations/'

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
