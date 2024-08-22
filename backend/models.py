# backend/models.py

import os
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from fpdf import FPDF

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

    def translate(self):
        # Create a directory for this document's translations if it doesn't exist
        document_dir = os.path.join(settings.MEDIA_ROOT, str(self.pk))
        translations_dir = os.path.join(document_dir, 'translations')
        os.makedirs(translations_dir, exist_ok=True)

        # Create the translated PDF file
        translated_file_name = f"translated_{self.pk}.pdf"
        translated_file_path = os.path.join(translations_dir, translated_file_name)

        # Generate the PDF content (For now, this will just be a placeholder text)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Translated: {self.title}", ln=True, align='C')
        pdf.output(translated_file_path)

        # Save the translated file path to the model
        self.translated_file.name = f'{self.pk}/translations/{translated_file_name}'
        self.save()

    def __str__(self):
        return self.title

# Signal to delete associated files when a Document is deleted
@receiver(post_delete, sender=Document)
def delete_files_on_document_delete(sender, instance, **kwargs):
    if instance.original_file:
        instance.original_file.delete(save=False)
    if instance.translated_file:
        instance.translated_file.delete(save=False)
