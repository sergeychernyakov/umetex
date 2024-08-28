# backend/services/pdf_translator.py

import re
import os
import fitz  # PyMuPDF
from openai import OpenAI
from django.conf import settings
import django
from typing import Tuple, Optional, List, Dict
import logging
import json
import random
import math
from fontTools.ttLib import TTFont
from django.db.models import Q
from backend.models.document import LANGUAGES, TEXT_ENCODING_CYRILLIC

logger = logging.getLogger(__name__)

# Ensure the Django settings module is configured
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "umetex_config.settings")

# Now set up Django
django.setup()

class PDFTranslator:
    cyrillic_support_cache: Dict[str, bool] = {}

    def __init__(self, document, temperature=0, max_tokens=4096):
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
        # Regular expression to detect non-translatable segments (document numbers, section numbers)
        non_translatable_pattern = re.compile(r"^\s*[\d\-\/.:]+[\d\w\-\/.:]*\s*$")

        # Filter out non-translatable segments but keep their positions
        translatable_texts = []
        indices_mapping = []  # To map filtered texts back to their original position
        all_texts = [None] * len(texts)  # To store both translated and non-translated texts

        for i, text in enumerate(texts):
            # Check if text is translatable (not just numbers or document codes)
            if non_translatable_pattern.match(text):
                # If it's not translatable, add it directly to the results
                all_texts[i] = text
                logger.debug(f"Keeping non-translatable text segment as is: text_{i}: [{text}]")
            else:
                translatable_texts.append(text)
                indices_mapping.append(i)

        # Shuffle the text segments to avoid order bias
        shuffled_indices = list(range(len(translatable_texts)))
        random.shuffle(shuffled_indices)
        shuffled_texts = [translatable_texts[i] for i in shuffled_indices]

        # Create patterns for extracted data
        patterns = {
            f"text_{indices_mapping[i]}": rf"text_{indices_mapping[i]}: \[([^\]]*?)\]" 
            for i in shuffled_indices
        }

        # Enhanced prompt to guide the translation process
        prompt = f"You are a helpful assistant for translating documents into {self.document.translation_language}."
        message = (
            "The following is a list of text segments extracted from a medical document. "
            "Translate each text segment into the target language, ensuring that each translation directly replaces the placeholder "
            "and retains the same numbering format for consistency. Please only provide the translated text within the brackets.\n\n"
        )

        for i, text in zip(shuffled_indices, shuffled_texts):
            original_index = indices_mapping[i]
            message += f"text_{original_index}: [{text}]\n"
            logger.debug(f"Prepared shuffled text segment for translation: text_{original_index}: [{text}]")

        # Initialize the dictionary to hold the extracted data
        translated_text = self.translate_text(prompt, message)
        logger.debug(f"Translated text received: {translated_text}")

        # Extract and filter matches for each pattern, and strip spaces from the strings
        for key, pattern in patterns.items():
            matches = re.findall(pattern, translated_text)
            logger.debug(f"Pattern for {key}: {pattern}, Matches found: {matches}")

            # Get the original index from the pattern key
            index = int(key.split('_')[1])
            non_empty_matches = [match.strip() for match in matches if match.strip()]
            if non_empty_matches:
                all_texts[index] = non_empty_matches[0]
            else:
                print(f"No match found for text_{index}, keeping original text: {texts[index]}")
                all_texts[index] = texts[index]  # Fallback to original if translation is missing

        return all_texts

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

        :return: Path to the translated PDF file.
        """
        original_pdf = fitz.open(self.original_pdf_path)
        translated_pdf = fitz.open()
        total_pages = len(original_pdf)
        self.update_progress(1, total_pages) # don't remove that

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
                            font_size = round(span.get("size", 12))-2
                            color = self.normalize_color(span.get("color", 0))
                            origin = span.get("origin", (0, 0))
                            ascender = span.get("ascender", 0)
                            descender = span.get("descender", 0)
                            
                            # Determine the rotation angle based on the direction
                            dir_x, dir_y = line.get('dir', (1.0, 0.0))
                            rotate_angle = self.calculate_rotation_angle(dir_x, dir_y)

                            # Get font name and path
                            fontname = self.clean_font_name(span.get("font", "Arial"))
                            font_path = self.find_font_path(fontname)

                            # Check if the font file exists
                            if not os.path.exists(font_path):
                                logger.warning(f"Font '{fontname}' not found. Using Arial as default.")
                                fontname = 'Arial'
                                font_path = os.path.join(self.fonts_dir, 'Arial.ttf')

                            # Register the font dynamically
                            new_page.insert_font(fontname=fontname, fontfile=font_path)

                            if re.search(r'[A-Za-z0-9]', original_text):
                                translated_text = translated_texts[text_index] if text_index < len(translated_texts) else original_text
                                text_index += 1
                                
                                fmt = "{:g} {:g} {:g} rg /{f:s} {s:g} Tf"
                                da_str = fmt.format(*color, f='helv', s=font_size)
                                logger.debug(f"Adding redaction annotation on page {page_number + 1}")
                                new_page._add_redact_annot(quad=bbox, da_str=da_str)

                                # Apply redactions and insert translated text with rotation
                                new_page.apply_redactions()  # Apply changes per page

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
                                    overlay=True
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

    def clean_font_name(self, fontname: str) -> str:
        """
        Clean up font name to ensure it is valid for use in PyMuPDF's insert_font method.

        :param fontname: Original font name from the PDF.
        :return: Cleaned font name suitable for PyMuPDF.
        """
        # Replace spaces and special characters with underscores
        cleaned_fontname = re.sub(r'[^A-Za-z0-9]', '_', fontname)
        return cleaned_fontname

    def calculate_rotation_angle(self, dir_x: float, dir_y: float) -> int:
        """
        Calculate the rotation angle based on the text direction.

        :param dir_x: X direction component.
        :param dir_y: Y direction component.
        :return: Rotation angle in degrees.
        """
        # Calculate the angle in radians and then convert to degrees
        rotate_angle = math.degrees(math.atan2(dir_y, dir_x))

        # Normalize the angle to a positive value between 0 and 360 degrees
        if rotate_angle < 0:
            rotate_angle += 360

        # Round the angle to the nearest integer
        rotate_angle = round(rotate_angle)

        # Special cases for exact directions
        if (dir_x, dir_y) == (0.0, 1.0):
            rotate_angle = 270
        elif (dir_x, dir_y) == (0.0, -1.0):
            rotate_angle = 90
        elif (dir_x, dir_y) == (-1.0, 0.0):
            rotate_angle = 180
        elif (dir_x, dir_y) == (1.0, 0.0):
            rotate_angle = 0

        # Log the calculated angle for debugging purposes
        return rotate_angle

    def find_font_path(self, fontname: str) -> str:
        """
        Find the appropriate font file based on the provided font name by searching through available font files.
        
        :param fontname: The name of the font to find.
        :return: Path to the font file if found, else default to Arial.
        """
        logger.debug(f"Searching for font: {fontname}")

        # Normalize the font name by removing common suffixes, spaces, and converting to lowercase
        normalized_fontname = re.sub(r'(MT|PSMT|[-\s]+)', '', fontname).lower()

        best_match = None
        best_match_score = 0
        style_penalty = {
            "bold": 2,
            "italic": 2,
            "bolditalic": 3
        }
        match_threshold = 1  # Minimum score to consider a font a good match

        # Получаем список всех языков, поддерживающих кириллицу
        cyrillic_languages = [lang[0] for lang in LANGUAGES if lang[2] == TEXT_ENCODING_CYRILLIC]

        for root, _, files in os.walk(self.fonts_dir):
            for file in files:
                # Normalize the filename similarly to match against fontname
                normalized_filename = re.sub(r'[-\s]+', '', file).lower().replace('.ttf', '').replace('.ttc', '').replace('.otf', '')

                # Calculate match score based on name similarity
                match_score = sum(part in normalized_filename for part in normalized_fontname.split('_'))

                # Add penalties if the styles (bold/italic) do not match
                if "bold" in normalized_fontname and "bold" not in normalized_filename:
                    match_score -= style_penalty["bold"]
                if "italic" in normalized_fontname and "italic" not in normalized_filename:
                    match_score -= style_penalty["italic"]
                if "bold" not in normalized_fontname and "bold" in normalized_filename:
                    match_score -= style_penalty["bold"]
                if "italic" not in normalized_fontname and "italic" in normalized_filename:
                    match_score -= style_penalty["italic"]

                # Update best match if this file has a better score
                if match_score > best_match_score:
                    best_match = os.path.join(root, file)
                    best_match_score = match_score

            if best_match and best_match_score >= match_threshold:
                # Check for the cyrillic support
                if self.document.translation_language in cyrillic_languages and not self.supports_cyrillic(best_match):
                    logger.debug(f"Font '{fontname}' does not support Cyrillic. Using Arial as default.")
                    return os.path.join(self.fonts_dir, 'Arial.ttf')
                else:
                    logger.debug(f"Best match found: {os.path.basename(best_match)} with score: {best_match_score}")
                    break

        # Use Arial if no match is found or if the best match score is below the threshold
        if not best_match or best_match_score < match_threshold:
            logger.error(f"Font '{fontname}' not found or match is too weak. Using Arial as default.")
            return os.path.join(self.fonts_dir, 'Arial.ttf')

        return best_match

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

    @staticmethod
    def supports_cyrillic(font_path: str) -> bool:
        """
        Проверяет, поддерживает ли шрифт кириллицу с использованием кэширования.

        :param font_path: Путь к файлу шрифта.
        :return: True, если шрифт поддерживает кириллицу, иначе False.
        """
        # Check if the result is already cached
        if font_path in PDFTranslator.cyrillic_support_cache:
            return PDFTranslator.cyrillic_support_cache[font_path]

        try:
            font = TTFont(font_path)
            # Кириллический диапазон Unicode: U+0400 to U+04FF
            cyrillic_range = range(0x0400, 0x0500)

            # Получаем список всех глифов (символов) в шрифте
            for table in font['cmap'].tables:
                if any(ord_char in cyrillic_range for ord_char in table.cmap.keys()):
                    # Cache the result
                    PDFTranslator.cyrillic_support_cache[font_path] = True
                    return True
        except Exception as e:
            logger.error(f"Ошибка при проверке шрифта {font_path}: {e}")

        # Cache the negative result
        PDFTranslator.cyrillic_support_cache[font_path] = False
        return False

    def __str__(self):
        return self.title

# Example usage
# python manage.py shell
if __name__ == "__main__":
    
    # python manage.py shell

    from backend.models import Document
    from backend.services import PDFTranslator

    # Получите экземпляр документа
    document = Document.objects.get(pk=191) # 201

    # Создайте экземпляр PDFTranslator и запустите перевод
    translator = PDFTranslator(document)
    translator.translate_pdf()
    print(f'self.translated_file : {document.translated_file}')
