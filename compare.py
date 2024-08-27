# backend/services.py

import re
import os
import fitz  # PyMuPDF
from openai import OpenAI
from django.conf import settings
import django
from typing import Tuple, Optional, List
import logging
import json

logger = logging.getLogger(__name__)

# Ensure the Django settings module is configured
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "umetex_config.settings")

# Now set up Django
django.setup()

class PDFTranslator:  
    def __init__(self, document, temperature=0.2, max_tokens=4096):
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

        # Enhanced prompt to guide the translation process
        prompt = f"You are a helpful assistant for translating documents into {self.document.translation_language}."
        message = (
            "The following is a list of text segments extracted from a medical document. "
            "Translate each text segment into the target language, ensuring that each translation directly replaces the placeholder "
            "and retains the same numbering format for consistency. Please only provide the translated text within the brackets.\n\n"
        )

        for i, text in enumerate(texts):
            # Updated message format to reinforce consistency in translation output
            message += f"text_{i}: [{text}]\n"

        # Initialize the dictionary to hold the extracted data
        extracted_data = []

        # Translate combined texts
        translated_text = self.translate_text(prompt, message)

        # Extract and filter matches for each pattern, and strip spaces from the strings
        for key, pattern in patterns.items():
            matches = re.findall(pattern, translated_text)
            # Keep the first non-empty match, if any, otherwise keep it as an empty string
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

        print(f"Sending prompt to OpenAI API: {prompt}")
        print(f"Sending message to OpenAI API: {message}")

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
        print(f"Received response from OpenAI API: {translated_text}")

        return translated_text

def translate_pdf(self) -> str:
    """
    Recreate the PDF by copying each page from the original PDF into a new PDF
    and replacing all text with translated text using redaction annotations, retaining formatting.

    :return: Path to the translated PDF file.
    """
    original_pdf = fitz.open(self.original_pdf_path)
    translated_pdf = fitz.open()
    total_pages = len(original_pdf)
    self.update_progress(1, total_pages)  # don't remove that

    # Register the custom Arial font
    font_path = os.path.join(settings.BASE_DIR, 'fonts', 'Arial.ttf')
    if not os.path.exists(font_path):
        logger.error(f"Font file not found at {font_path}")
        return

    fontname = 'Arial'
    # Register font
    fitz.TOOLS.set_option('use_glyph_cache', False)  # Ensure all glyphs are reloaded
    fitz.TOOLS.set_option('fontdir', os.path.dirname(font_path))  # Set the directory for custom fonts

    for page_number in range(total_pages):
        logger.debug(f"Processing page {page_number + 1} of {total_pages}")

        original_page = original_pdf[page_number]
        new_page = translated_pdf.new_page(width=original_page.rect.width, height=original_page.rect.height)
        
        new_page.show_pdf_page(new_page.rect, original_pdf, page_number)

        text_dict = original_page.get_text("dict")
        page_texts = []  # Reset text list for each page

        # Extract text from the current page
        for block in text_dict['blocks']:
            if block['type'] == 0:  # Text block
                for line in block['lines']:
                    for span in line['spans']:
                        original_text = span["text"].strip()
                        if original_text and re.search(r'[A-Za-z0-9]', original_text):
                            page_texts.append(original_text)

        # Translate extracted texts from the current page
        translated_texts = self.translate_texts(page_texts)

        # Apply translated texts back to the current page
        text_index = 0
        for block in text_dict['blocks']:
            if block['type'] == 0:  # Text block
                for line in block['lines']:
                    for span in line['spans']:
                        original_text = span["text"].strip()
                        bbox = fitz.Rect(span["bbox"])
                        font_size = span.get("size", 12)
                        color = self.normalize_color(span.get("color", 0))

                        if re.search(r'[A-Za-z0-9]', original_text):
                            translated_text = translated_texts[text_index] if text_index < len(translated_texts) else original_text
                            text_index += 1
                        else:
                            translated_text = original_text

                        # Removing old text (filling with white)
                        new_page.draw_rect(bbox, color=(1, 1, 1), fill=(1, 1, 1))

                        # Insert translated text
                        new_page.insert_textbox(
                            bbox, translated_text, 
                            fontsize=font_size, 
                            fontfile=font_path, 
                                color=color, 
                                fontname=fontname, 
                                encoding=fitz.TEXT_ENCODING_CYRILLIC
                            )

            logger.debug(f"Applying redactions on page {page_number + 1}")
            new_page.apply_redactions()  # Apply changes per page

            # Update progress after translating each page
            self.update_progress(page_number + 1, total_pages)

        # Save the translated PDF
        logger.debug(f"Saving translated PDF to {self.translated_file_path}")
        translated_pdf.save(self.translated_file_path)
        translated_pdf.close()
        original_pdf.close()

        self.document.translated_file.name = f'{self.document.pk}/translations/{self.translated_file_name}'
        self.document.save()

        logger.debug(f"Recreated file saved at: {self.translated_file_path}")
        return self.translated_file_path
    def update_progress(self, current_page: int, total_pages: int):
        """
        Update the progress of the translation.
        
        :param current_page: Current page number being translated.
        :param total_pages: Total number of pages in the document.
        """
        progress_data = {
            "document_id": self.document.pk,
            "current_page": current_page,
            "total_pages": total_pages
        }
        progress_file = os.path.join(settings.MEDIA_ROOT, f'{self.document.pk}', f'{self.document.pk}_progress.json')
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)

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

    # pdf_translator = PDFTranslator(document=document)
    # messages = [
    #     "Purpose",
    #     "The purpose of this document is to establish the Material Handling process and procedure for parts and finished medical devices thereby fulfilling the regulatory requirements as referenced in the Cynosure Quality Manual 931-QA01-001, as applicable.",
    #     "931-QA01-001 Cynosure Quality Manual"
    # ]
    # extracted_data = pdf_translator.translate_texts(messages)
    # print(f'Extracted dataL {extracted_data}')
