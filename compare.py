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
        self.fonts_dir = os.path.join(settings.BASE_DIR, 'fonts')

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
            message += f"text_{i}: [{text}]\n"

        # Translate combined texts
        translated_text = self.translate_text(prompt, message)

        # Extract and filter matches for each pattern, and strip spaces from the strings
        extracted_data = []
        for key, pattern in patterns.items():
            matches = re.findall(pattern, translated_text)
            non_empty_matches = [match.strip() for match in matches if match.strip()]
            extracted_data.append(non_empty_matches[0] if non_empty_matches else None)

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
                            origin = span.get("origin", (0, 0))
                            ascender = span.get("ascender", 0)
                            descender = span.get("descender", 0)
                            dir_x, dir_y = span.get('dir', (1.0, 0.0))
                            rotate_angle = 0 if dir_x == 1.0 else 90

                            # Get font name and path
                            fontname = span.get("font", "Arial")
                            font_path = self.find_font_path(fontname)

                            if not os.path.exists(font_path):
                                logger.warning(f"Font '{fontname}' not found. Using Arial as default.")
                                fontname = 'Arial'
                                font_path = os.path.join(self.fonts_dir, 'Arial.ttf')
                            
                            # Register the font dynamically
                            new_page.insert_font(fontname=fontname, fontfile=font_path)

                            if re.search(r'[A-Za-z0-9]', original_text):
                                translated_text = translated_texts[text_index] if text_index < len(translated_texts) else original_text
                                text_index += 1
                            else:
                                translated_text = original_text

                            # Calculate the adjusted position using origin, ascender, and descender
                            adjusted_origin = (origin[0], origin[1] - ascender + descender)
                            
                            # Use the insert_text method directly on the page
                            rc = new_page.insert_text(
                                point=adjusted_origin,
                                text=translated_text,
                                fontsize=font_size,
                                fontname=fontname,
                                fontfile=font_path,
                                color=color,
                                rotate=rotate_angle,
                                overlay=True  # Overlay text on top of existing content
                            )
                            if rc < 0:
                                logger.error(f"Failed to insert text at {bbox.tl} on page {page_number + 1}")

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

    def find_font_path(self, fontname: str) -> str:
        """
        Find the appropriate font file based on the provided font name.

        :param fontname: The name of the font to find.
        :return: Path to the font file if found, else default to Arial.
        """
        font_map = {
            'ArialMT': 'Arial.ttf',
            'Arial-BoldMT': 'Arial Bold.ttf',
            'TimesNewRomanPSMT': 'Times New Roman.ttf',
            'TimesNewRomanPS-BoldMT': 'Times New Roman Bold.ttf',
            'SymbolMT': 'Symbol.ttf',
            # Add more mappings as needed
        }
        font_filename = font_map.get(fontname, 'Arial.ttf')
        return os.path.join(self.fonts_dir, font_filename)

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
        progress_file = os.path.join(settings.MEDIA_ROOT, f'{self.document.pk}', f'{self.document