# backend/services.py

import re
import os
import fitz  # PyMuPDF
from openai import OpenAI
from fpdf import FPDF
from django.conf import settings
import django
from typing import Tuple, Optional, List, Dict
from fpdf import FPDF
import logging

logger = logging.getLogger(__name__)

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
        os.makedirs(self.translations_dir, exist_ok=True)
        self.translated_file_path = os.path.join(self.translations_dir, self.translated_file_name)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def translate_texts(self, texts: List[str]) -> List[Optional[str]]:
        """
        Translate an array of messages using the OpenAI API and extract translations
        based on predefined patterns.

        :param texts: List of text messages to translate.
        :return: List of extracted translation data.
        """
        patterns = {
            f"text_{i}": rf"text_{i}: \[([^\]]*?)\]" for i in range(len(texts))
        }

        prompt = f"You are a helpful assistant for translating documents to {self.document.translation_language}."
        message = "This is a set of texts from a medical document. Translate each text to the target language, and replace the placeholders with corresponding translations:\n\n"

        for i, text in enumerate(texts):
            message += f"text_{i}: [{{text_{i}}}] with the translated text: [{text}]\n "

        # Initialize the list to hold the extracted data
        extracted_data = []

        # Translate combined texts
        translated_text = self.translate_text(prompt, message)

        # Extract and filter matches for each pattern, and strip spaces from the strings
        for key, pattern in patterns.items():
            matches = re.findall(pattern, translated_text)
            non_empty_matches = [match.strip() for match in matches if match.strip()]
            if non_empty_matches:
                extracted_data.append(non_empty_matches[0])
            else:
                extracted_data.append(None)

        return extracted_data

    def translate_text(self, prompt: str, message: str) -> str:
        """
        Translate text using the OpenAI API.

        :param prompt: The ChatGPT prompt.
        :param message: The text to translate.
        :return: Translated text.
        """
        if len(prompt) == 0 or len(message) == 0:
            return ''

        logger.debug(f"Sending prompt to OpenAI API: {prompt}")
        logger.debug(f"Sending message to OpenAI API: {message}")

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        translated_text = response.choices[0].message.content
        logger.debug(f"Received response from OpenAI API: {translated_text}")

        return translated_text

    def translate_pdf(self) -> str:
        """
        Recreate the PDF by copying each page from the original PDF into a new PDF
        and replacing all text with translated text using redaction annotations, retaining formatting.

        This method extracts all text from the original PDF, splits it into chunks of up to 20 messages,
        translates these chunks using the translate_texts method, and then applies the translations back
        onto the new PDF file.

        :return: Path to the translated PDF file.
        """
        original_pdf = fitz.open(self.original_pdf_path)
        translated_pdf = fitz.open()

        # List to store all text messages extracted from the PDF
        all_texts = []

        # Step 1: Extract all text from the original PDF
        for page_number in range(len(original_pdf)):
            original_page = original_pdf[page_number]
            text_dict = original_page.get_text("dict")

            for block in text_dict['blocks']:
                if block['type'] == 0:  # Process only text blocks
                    for line in block['lines']:
                        for span in line['spans']:
                            original_text = span["text"].strip()
                            if original_text:
                                # Check if the text contains actual characters for translation
                                if re.search(r'[A-Za-z0-9]', original_text):
                                    all_texts.append(original_text)
                                else:
                                    all_texts.append(None)  # Mark as None if no translation is needed

        # Step 2: Translate texts in chunks of up to 20
        translated_texts = self.translate_texts([text for text in all_texts if text])

        # Step 3: Apply translations back to a new PDF
        text_index = 0
        for page_number in range(len(original_pdf)):
            original_page = original_pdf[page_number]
            new_page = translated_pdf.new_page(width=original_page.rect.width, height=original_page.rect.height)
            new_page.show_pdf_page(new_page.rect, original_pdf, page_number)
            text_dict = original_page.get_text("dict")

            for block in text_dict['blocks']:
                if block['type'] == 0:  # Process only text blocks
                    for line in block['lines']:
                        for span in line['spans']:
                            original_text = span["text"].strip()
                                
                            bbox = fitz.Rect(span["bbox"])
                            fontname = 'Helv'
                            font_size = span.get("size", 12)
                            color = self.normalize_color(span.get("color", 0))

                            # Check if text requires translation and replace if translated
                            if re.search(r'[A-Za-z0-9]', original_text):
                                translated_text = translated_texts[text_index] if text_index < len(translated_texts) else original_text
                                text_index += 1
                            else:
                                translated_text = original_text

                            # Add redaction annotation with the translated text
                            fmt = "{:g} {:g} {:g} rg /{f:s} {s:g} Tf"
                            da_str = fmt.format(*color, f=fontname, s=font_size)
                            new_page._add_redact_annot(
                                quad=bbox,
                                text=translated_text, 
                                da_str=da_str
                            )

            # Apply redactions to replace text
            new_page.apply_redactions()

        translated_pdf.save(self.translated_file_path)
        translated_pdf.close()
        original_pdf.close()

        self.document.translated_file.name = f'{self.document.pk}/translations/{self.translated_file_name}'
        self.document.save()

        logger.debug(f"Recreated file saved at: {self.translated_file_path}")
        return self.translated_file_path

    @staticmethod
    def normalize_color(color: Optional[int]) -> Tuple[float, float, float]:
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

# Example usage
# python3 -m backend.services
if __name__ == "__main__":
    from backend.models import Document

    # Assume we have a Document instance
    document = Document.objects.get(pk=139)

    print(document.translation_language)

    document.translate()
    print(f'self.translated_file : {document.translated_file}')
