# backend/models.py

import os
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.core.files.storage import FileSystemStorage
from django.core.files import File
import io
import fitz
from fpdf import FPDF
import shutil

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
    original_file = models.FileField(upload_to='tmp/originals/')
    translated_file = models.FileField(upload_to='tmp/translations/', blank=True, null=True)
    translation_language = models.CharField(max_length=2, choices=LANGUAGES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Save first to get the primary key (if not already set)
        if not self.pk:
            super().save(*args, **kwargs)  # Save to generate a primary key

        # Determine the new paths and rename the original file
        original_file_new_name = f'original_{self.pk}.pdf'
        original_file_new_path = f'{self.pk}/originals/{original_file_new_name}'
        translated_file_new_path = f'{self.pk}/translations/{os.path.basename(self.translated_file.name)}' if self.translated_file else None

        print(f"Original file new path: {original_file_new_path}")  # Debug print
        print(f"Translated file new path: {translated_file_new_path}")  # Debug print

        # Ensure the directories exist
        original_dir = os.path.join(settings.MEDIA_ROOT, f'{self.pk}/originals/')
        translated_dir = os.path.join(settings.MEDIA_ROOT, f'{self.pk}/translations/')

        os.makedirs(original_dir, exist_ok=True)
        os.makedirs(translated_dir, exist_ok=True)

        # Move and rename the original file
        if self.original_file and self.original_file.name.startswith('tmp/originals/'):
            try:
                original_source_path = self.original_file.path
                original_destination_path = os.path.join(settings.MEDIA_ROOT, original_file_new_path)
                shutil.move(original_source_path, original_destination_path)
                self.original_file.name = original_file_new_path
                print(f"Moved original file to: {original_destination_path}")
            except Exception as e:
                print(f"Error moving original file: {e}")

        # Move the translated file if it exists
        if self.translated_file and self.translated_file.name.startswith('tmp/translations/'):
            try:
                translated_source_path = self.translated_file.path
                translated_destination_path = os.path.join(settings.MEDIA_ROOT, translated_file_new_path)
                shutil.move(translated_source_path, translated_destination_path)
                self.translated_file.name = translated_file_new_path
                print(f"Moved translated file to: {translated_destination_path}")
            except Exception as e:
                print(f"Error moving translated file: {e}")

        # Save again with the updated paths
        super().save(*args, **kwargs)



    # def translate(self):
    #     """
    #     Translate the document using the PDFTranslator class and update the translated_file field.
    #     """
    #     from .services import PDFTranslator

    #     translator = PDFTranslator(self)
    #     translated_file_name = translator.translate_pdf()  # Perform the translation and get the file name

    #     # Update the translated_file field with the new translated file path
    #     self.translated_file.name = f'{self.pk}/translations/{translated_file_name}'
    #     self.save()  # Save the updated model

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

    def recreate(self):
        """
        Recreate the PDF by copying all text elements from the original PDF file to a new PDF file with fonts and sizes.
        """
        document_dir = os.path.join(settings.MEDIA_ROOT, str(self.pk))
        translations_dir = os.path.join(document_dir, 'translations')
        os.makedirs(translations_dir, exist_ok=True)

        recreated_file_name = f"recreated_{self.pk}.pdf"
        recreated_file_path = os.path.join(translations_dir, recreated_file_name)

        original_pdf_path = self.original_file.path
        original_pdf = fitz.open(original_pdf_path)
        recreated_pdf = fitz.open()

        default_font = "helv"  # Default fallback font
        default_color = (0, 0, 0)  # Default color is black

        for page_number in range(len(original_pdf)):
            original_page = original_pdf[page_number]
            new_page = recreated_pdf.new_page(width=original_page.rect.width, height=original_page.rect.height)

            text = original_page.get_text("dict")

            y_position = 50  # Start text placement a bit lower

            for block in text['blocks']:
                if block['type'] == 0:  # Only process text blocks
                    for line in block['lines']:
                        for span in line['spans']:
                            try:
                                font_size = span.get('size', 12)  # Use span's font size
                                fontname = span.get('font', default_font)  # Use span's font or fallback
                                color = normalize_color(span.get('color', default_color))  # Get color, normalized

                                new_page.insert_text(
                                    (50, y_position),
                                    span['text'],
                                    fontsize=font_size,
                                    fontname=fontname,
                                    color=color
                                )
                                y_position += font_size + 2  # Adjust spacing based on font size
                            except Exception as e:
                                print(f"Error rendering text span on page {page_number}: {e}")
                                # Fallback to default font if error occurs
                                new_page.insert_text(
                                    (50, y_position),
                                    span['text'],
                                    fontsize=font_size,
                                    fontname=default_font,
                                    color=default_color
                                )
                                y_position += font_size + 2  # Adjust spacing

        recreated_pdf.save(recreated_file_path)
        recreated_pdf.close()
        original_pdf.close()

        self.translated_file.name = f'{self.pk}/translations/{recreated_file_name}'
        self.save()

        print(f"Recreated file saved at: {recreated_file_path}")



    def normalize_color(color):
        """
        Normalize color from integer or tuple form to (r, g, b) with values between 0 and 1.
        """
        if isinstance(color, int):  # If color is an integer
            r = (color >> 16) & 0xff
            g = (color >> 8) & 0xff
            b = color & 0xff
            return (r / 255.0, g / 255.0, b / 255.0)
        elif isinstance(color, tuple) and len(color) == 3:
            return tuple(c / 255.0 for c in color)
        return (0, 0, 0)  # Default to black if color is invalid




    def __str__(self):
        return self.title

# Signal to delete associated files when a Document is deleted
@receiver(post_delete, sender=Document)
def delete_files_on_document_delete(sender, instance, **kwargs):
    if instance.original_file:
        instance.original_file.delete(save=False)
    if instance.translated_file:
        instance.translated_file.delete(save=False)
