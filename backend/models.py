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
    file = models.FileField(upload_to='documents/')
    translated = models.BooleanField(default=False)
    translation_language = models.CharField(max_length=2, choices=LANGUAGES, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
