# backend/management/commands/seed_documents.py

from django.core.management.base import BaseCommand
from backend.models import Document
from faker import Faker
import random
import os
from fpdf import FPDF

class Command(BaseCommand):
    help = 'Seeds the database with sample documents'

    def handle(self, *args, **kwargs):
        fake = Faker()

        # Optional: Clears existing documents
        Document.objects.all().delete()

        languages = ['EN', 'ES', 'KZ', 'DE', 'FR']  # Language codes

        for i in range(30):  # Change to 40 if you need 40 documents
            title = fake.sentence(nb_words=3)

            # Create a temporary document instance to get the ID
            temp_doc = Document(title=title)
            temp_doc.save()
            doc_id = temp_doc.id

            # Define the directory for this document based on its ID
            document_dir = os.path.join('documents', str(doc_id))
            os.makedirs(document_dir, exist_ok=True)

            # Create the original PDF file
            original_file_name = f"original_{doc_id}.pdf"
            original_file_path = os.path.join(document_dir, original_file_name)
            self.create_pdf(original_file_path, title)

            translation_language = random.choice(languages)  # Always assign a language
            translated = random.choice([True, False])
            translated_file_path = None

            if translated:
                translated_file_name = f"translated_{doc_id}.pdf"
                translated_file_path = os.path.join(document_dir, translated_file_name)
                self.create_pdf(translated_file_path, f"Translated: {title} ({translation_language})")

            # Update the document with the correct paths and translation language
            temp_doc.original_file = original_file_path
            if translated_file_path:
                temp_doc.translated_file = translated_file_path
            temp_doc.translation_language = translation_language
            temp_doc.save()

        self.stdout.write(self.style.SUCCESS('Successfully seeded the database with sample documents and PDFs'))

    def create_pdf(self, path, text):
        """ Helper function to create a PDF file with the given text. """
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=text, ln=True, align='C')
        pdf.output(path)

        # Check if the file was created successfully
        if not os.path.isfile(path):
            self.stdout.write(self.style.ERROR(f"Failed to create PDF: {path}"))
