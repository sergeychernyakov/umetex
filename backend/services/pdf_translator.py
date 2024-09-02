# backend/services/pdf_translator.py

import re
import os
import fitz  # PyMuPDF
from django.conf import settings
from typing import Tuple, Optional, List, Dict
import logging
import math
from backend.models import Document
from backend.services.text_translator import TextTranslator
from backend.services.font_manager import FontManager

logger = logging.getLogger(__name__)

class PDFTranslator:
    def __init__(self, document: Document):
        """
        Initialize the PDFTranslator with a Document instance.

        :param document: Document instance containing the original PDF and translation details.
        """
        self.document = document
        self.total_pages = 1
        self.current_page = 0
        self.original_pdf_path = document.original_file.path
        self.translated_file_name = f"translated_{document.pk}.pdf"
        self.translations_dir = os.path.join(settings.MEDIA_ROOT, str(document.pk), 'translations')
        os.makedirs(self.translations_dir, exist_ok=True)
        self.translated_file_path = os.path.join(self.translations_dir, self.translated_file_name)
        self.translator = TextTranslator(self.document.translation_language)
        self.font_manager = FontManager(self.document.translation_language)

    def translate_pdf(self) -> str:
        """
        Recreate the PDF by copying each page from the original PDF into a new PDF
        and replacing all text with translated text using redaction annotations, retaining formatting.

        :return: Path to the translated PDF file.
        """
        original_pdf = fitz.open(self.original_pdf_path)
        translated_pdf = fitz.open()
        self.total_pages = len(original_pdf)
        self.document.update_progress(1, self.total_pages) # don't remove that

        for page_number in range(self.total_pages):
            self.current_page = page_number + 1
            logger.debug(f"Processing page {page_number + 1} of {self.total_pages}")

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
            translated_texts = self.translator.translate_texts(page_texts)
            # translated_texts = page_texts

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
                            fontname = self.font_manager.clean_font_name(span.get("font", "Arial"))
                            font_path = self.font_manager.find_font_path(fontname)

                            # Check if the font file exists
                            if not os.path.exists(font_path):
                                logger.warning(f"Font '{fontname}' not found. Using Arial as default.")
                                fontname = 'Arial'
                                font_path = os.path.join(self.font_manager.fonts_dir, 'Arial.ttf')

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
            self.document.update_progress(self.current_page, self.total_pages)

        # Save the translated PDF
        logger.debug(f"Saving translated PDF to {self.translated_file_path}")

        translated_pdf.save(self.translated_file_path)
        translated_pdf.close()
        original_pdf.close()

        self.document.translated_file.name = f'{self.document.pk}/translations/{self.translated_file_name}'
        self.document.save()

        logger.debug(f"Recreated file saved at: {self.translated_file_path}")
        return self.translated_file_path

    def calculate_rotation_angle(self, dir_x: float, dir_y: float) -> int:
        """
        Calculate the rotation angle based on the text direction.

        :param dir_x: X direction component.
        :param dir_y: Y direction component.
        :return: Rotation angle in degrees, rounded to nearest valid value (0, 90, 180, 270).
        """
        # Calculate the angle in radians and then convert to degrees
        rotate_angle = math.degrees(math.atan2(dir_y, dir_x))

        # Normalize the angle to a positive value between 0 and 360 degrees
        if rotate_angle < 0:
            rotate_angle += 360

        # Log the calculated angle for debugging purposes
        logger.debug(f"Calculated raw rotation angle: {rotate_angle}")

        # Map to the nearest valid angle (0, 90, 180, 270)
        if rotate_angle < 45 or rotate_angle >= 315:
            return 0
        elif 45 <= rotate_angle < 135:
            return 90
        elif 135 <= rotate_angle < 225:
            return 180
        elif 225 <= rotate_angle < 315:
            return 270

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
