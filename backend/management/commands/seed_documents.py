from django.core.management.base import BaseCommand
from backend.models import Document
from faker import Faker
import random
import os
from fpdf import FPDF
from django.conf import settings

class Command(BaseCommand):
    help = 'Seeds the database with sample documents'

    def handle(self, *args, **kwargs):
        fake = Faker()

        # Optional: Clears existing documents
        Document.objects.all().delete()

        languages = [lang[0] for lang in Document.LANGUAGES]  # Extract language codes

        for i in range(30):  # Change to 40 if you need 40 documents
            title = fake.sentence(nb_words=3)

            # Create a temporary document instance to get the ID
            temp_doc = Document(title=title, translation_language=random.choice(languages))
            temp_doc.save()
            doc_id = temp_doc.id

            # Define the directory for this document based on its ID
            document_dir = os.path.join(settings.MEDIA_ROOT, str(doc_id))
            os.makedirs(document_dir, exist_ok=True)

            # Create the original PDF file
            original_file_name = f"original_{doc_id}.pdf"
            original_file_path = os.path.join(document_dir, 'originals', original_file_name)
            self.create_pdf(original_file_path, title)

            # Save the original file path
            temp_doc.original_file.name = f'{doc_id}/originals/{original_file_name}'

            # Optionally create a translated file
            translated = random.choice([True, False])
            if translated:
                translated_file_name = f"translated_{doc_id}.pdf"
                translated_file_path = os.path.join(document_dir, 'translations', translated_file_name)
                self.create_pdf(translated_file_path, f"Translated: {title}")
                temp_doc.translated_file.name = f'{doc_id}/translations/{translated_file_name}'
            else:
                temp_doc.translated_file = None

            temp_doc.save()

        self.stdout.write(self.style.SUCCESS('Successfully seeded the database with sample documents and PDFs'))

    def create_pdf(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=text, ln=True, align='C')
        pdf.output(path)
