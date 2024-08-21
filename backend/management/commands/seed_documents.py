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
        document_dir = os.path.join('documents')
        os.makedirs(document_dir, exist_ok=True)

        # Optional: Clears existing documents
        Document.objects.all().delete()

        languages = ['EN', 'ES', 'KZ', 'DE', 'FR']  # Language codes

        for i in range(30):  # Change to 40 if you need 40 documents
            title = fake.sentence(nb_words=3)
            file_name = f"{title.replace(' ', '_')}_{i}.pdf"
            file_path = os.path.join(document_dir, file_name)

            # Create a simple PDF file
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=title, ln=True, align='C')
            pdf.output(file_path)

            translated = random.choice([True, False])
            translation_language = random.choice(languages)

            Document.objects.create(
                title=title,
                file=file_path,
                translated=translated,
                translation_language=translation_language,
            )

        self.stdout.write(self.style.SUCCESS('Successfully seeded the database with sample documents and PDFs'))
