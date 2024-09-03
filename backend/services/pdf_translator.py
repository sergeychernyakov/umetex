# backend/services/pdf_translator.py

import os
import re
import fitz  # PyMuPDF
import logging
import math
from PIL import Image
from io import BytesIO
from typing import Optional, Tuple
from django.conf import settings
from backend.models import Document
from backend.services.text_translator import TextTranslator
from backend.services.font_manager import FontManager
from backend.services.yandex_image_translator import YandexImageTranslator  # Import YandexImageTranslator

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
        self.yandex_translator = YandexImageTranslator(self.document.translation_language)  # Initialize YandexImageTranslator

    def translate_pdf(self) -> str:
        """
        Translate the PDF by processing text and image blocks, inserting translated content into a new PDF.

        :return: Path to the translated PDF file.
        """
        original_pdf = fitz.open(self.original_pdf_path)
        translated_pdf = fitz.open()
        self.total_pages = len(original_pdf)
        self.document.update_progress(0, self.total_pages)  # Update progress

        for page_number in range(self.total_pages):
            self.current_page = page_number + 1
            logger.debug(f"Processing page {page_number + 1} of {self.total_pages}")

            original_page = original_pdf[page_number]
            new_page = translated_pdf.new_page(width=original_page.rect.width, height=original_page.rect.height)
            new_page.show_pdf_page(new_page.rect, original_pdf, page_number)

            text_dict = original_page.get_text("dict")
            page_texts = []  # Reset text list for each page

            # Extract and process each block on the page
            for block in text_dict['blocks']:
                if block['type'] == 0:  # Text block
                    for line in block['lines']:
                        for span in line['spans']:
                            original_text = span["text"].strip()
                            if original_text and re.search(r'[A-Za-z0-9]', original_text):
                                page_texts.append(original_text)

                elif block['type'] == 1:  # Image block
                    logger.debug(f"Processing image block on page {page_number + 1}")
                    self._process_image_block(block, new_page)

            # Translate extracted texts from the current page
            translated_texts = self.translator.translate_texts(page_texts)
            # Apply translated texts back to the current page
            self._apply_translated_texts(text_dict, new_page, translated_texts)

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

    def _process_image_block(self, block, new_page):
        """
        Process an image block, translate it and insert back to the PDF page.

        :param block: The block containing image data.
        :param new_page: The page in the new PDF to insert the translated image into.
        """
        image_data = block.get("image")
        if not image_data:
            return

        # Convert the image data bytes into a PIL Image
        image = Image.open(BytesIO(image_data))  # Directly use image_data as bytes

        # Save the image temporarily for translation
        temp_image_path = os.path.join(self.translations_dir, "temp_image.png")
        image.save(temp_image_path)

        # Translate the image using YandexImageTranslator
        # self.document.original_file.path = temp_image_path  # Update document with temp image path
        translated_image_path = self.yandex_translator.translate_image(image)

        # Insert the translated image back into the PDF
        with Image.open(translated_image_path) as translated_image:
            translated_image = translated_image.convert('RGB')
            img_rect = fitz.Rect(block["bbox"])
            new_page.insert_image(img_rect, filename=translated_image_path)
        logger.debug(f"Inserted translated image at position {img_rect}")

    def _apply_translated_texts(self, text_dict, new_page, translated_texts):
        """
        Apply translated texts to the new page, replacing original texts.

        :param text_dict: The text dictionary containing text blocks.
        :param new_page: The page in the new PDF to insert the translated texts.
        :param translated_texts: List of translated texts.
        """
        text_index = 0
        for block in text_dict['blocks']:
            if block['type'] == 0:  # Text block
                for line in block['lines']:
                    for span in line['spans']:
                        original_text = span["text"].strip()
                        bbox = fitz.Rect(span["bbox"])
                        font_size = round(span.get("size", 12)) - 2
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

    def calculate_rotation_angle(self, dir_x: float, dir_y: float) -> int:
        """
        Calculate the rotation angle based on the text direction.

        :param dir_x: X direction component.
        :param dir_y: Y direction component.
        :return: Rotation angle in degrees, rounded to nearest valid value (0, 90, 180, 270).
        """
        rotate_angle = math.degrees(math.atan2(dir_y, dir_x))

        if rotate_angle < 0:
            rotate_angle += 360

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

        :param color: Color value as integer or tuple.
        :return: Normalized (r, g, b) color.
        """
        if isinstance(color, int):
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
# python3 -m backend.services.pdf_translator
if __name__ == "__main__":
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'umetex.settings')
    django.setup()

    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    from backend.models import Document

    # Get a document instance
    document = Document.objects.get(pk=191)  # Replace with actual document ID

    # Create an instance of PDFTranslator and translate the document
    pdf_translator = PDFTranslator(document)
    translated_pdf_path = pdf_translator.translate_pdf()
    print(f'Translated PDF saved at: {translated_pdf_path}')
