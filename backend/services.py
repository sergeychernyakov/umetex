# backend/services.py

import os
import fitz  # PyMuPDF
from openai import OpenAI
from fpdf import FPDF
from django.conf import settings
import django

# Ensure the Django settings module is configured
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "umetex_config.settings")

# Now set up Django
django.setup()

class PDFTranslator:  
    def __init__(self, document, temperature=0.2, max_tokens=2000):
        """
        Initialize the PDFTranslator with a Document instance.

        :param document: Document instance containing the original PDF and translation details.
        """
        self.document = document
        self.original_pdf_path = document.original_file.path
        self.translated_file_name = f"translated_{document.pk}.pdf"
        self.translations_dir = os.path.join(settings.MEDIA_ROOT, str(document.pk), 'translations')
        self.translated_file_path = os.path.join(self.translations_dir, self.translated_file_name)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def translate_text(self, text: str) -> str:
        """
        Translate text using the OpenAI API.

        :param text: The text to translate.
        :return: Translated text.
        """
        prompt = "You are a helpful assistant for medical documents translations."
        message = f"Translate the following text to {self.document.get_translation_language_display()}: {text}",

        print(f"OPENAI_API_KEY: {settings.OPENAI_API_KEY}")
        print(f"Sending prompt to OpenAI API: {prompt}")
        print(f"Sending message to OpenAI API: {message}")
        
        completion = self.client.chat.completions.create(
          model="gpt-4o",
          messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
          ]
        )

        print(completion.choices[0].message)
        
        # response = self.client.chat.completions.create(
        #     model="gpt-4o",
        #     messages=[
        #         {"role": "system", "content": prompt},
        #         {"role": "user", "content": message}
        #     ],
        #     temperature=self.temperature,
        #     max_tokens=self.max_tokens
        # )
        # print(f"Received response from OpenAI API: {response}")
        return completion.choices[0].message

    def translate_pdf(self) -> str:
        """
        Translate the PDF file and save the translated content while preserving the format.

        :return: The name of the translated PDF file.
        """
        os.makedirs(self.translations_dir, exist_ok=True)

        pdf_document = fitz.open(self.original_pdf_path)
        translated_pdf = FPDF()

        for page_number in range(len(pdf_document)):
            page = pdf_document[page_number]
            text = page.get_text()

            # Translate the text
            translated_text = self.translate_text(text)

            # Add the translated text to the new PDF, maintaining the original layout
            translated_pdf.add_page()
            translated_pdf.set_font("Arial", size=12)
            translated_pdf.multi_cell(0, 10, translated_text)

        translated_pdf.output(self.translated_file_path)
        pdf_document.close()

        return self.translated_file_name

    def save_translated_pdf(self):
        """
        Translate the document and update the Document model instance with the translated file.
        """
        translated_file_name = self.translate_pdf()

        # Update the translated_file field and save the instance
        self.document.translated_file.name = f'{self.document.pk}/translations/{translated_file_name}'
        self.document.save()

# Example usage
# python3 -m backend.services
if __name__ == "__main__":
    from backend.models import Document

    # Assume we have a Document instance
    document = Document.objects.get(pk=139)  # Replace 1 with your actual document ID
    
    document.recreate()
    
    print(document)

    print(f'self.translated_file : {document.translated_file}')
    
    # translator = PDFTranslator(document)
    
    # # Translate the PDF and save the translated file
    # translator.save_translated_pdf()
