# backend/services/pdf_translator.py

import os
import re
import fitz  # PyMuPDF
import logging
import math
from PIL import Image
from io import BytesIO
import hashlib
from typing import Optional, Tuple, List


import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'umetex_config.settings')
django.setup()


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
        self.yandex_translator = YandexImageTranslator(self.document.translation_language)
        self.image_cache = {}  # Cache for storing translated images

    def is_big_text_block(self, block) -> bool:
        """
        Determine if a given text block is considered "big" based on the amount of text it contains.

        :param block: A dictionary representing a text block.
        :return: True if the block is considered "big", False otherwise.
        """
        if self.is_starts_with_bullet(block):
            return True

        # Criteria: Based on the number of characters in the block
        num_chars_threshold = 50 # Example threshold for the number of characters in the block

        # Extract all text from the block by concatenating text from spans
        block_text = ''.join(span["text"] for line in block.get('lines', []) for span in line.get('spans', []))

        # Check if the total number of characters in the block exceeds the threshold
        if len(block_text) > num_chars_threshold:
            return True

        return False

    def is_starts_with_bullet(self, block) -> bool:
        """
        Check if the text block starts with a bullet symbol.

        :param block: A dictionary representing a text block.
        :return: True if the block starts with a bullet, False otherwise.
        """
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                if span["text"].strip().startswith("•"):
                    return True
        return False

    def split_bullet_points(self, block_text: str) -> str:
        """
        Split a block of text into multiple parts based on bullet points (•) and 
        ensure there are line breaks between bullet points.

        :param block_text: The full text block containing multiple bullet points.
        :return: A formatted string with each bullet point on a new line.
        """
        # Split the text by the bullet character
        bullet_points = block_text.split('•')
        
        # Filter out any empty strings, re-add the bullet symbol, and ensure each point is on a new line
        bullet_points = ['• ' + self.translator.apply_format(point.strip(), point.strip()) for point in bullet_points if point.strip()]
        
        # Join the bullet points back into a single string with line breaks
        formatted_text = '\n'.join(bullet_points)
        
        return formatted_text

    def is_continuation(self, block1: dict, block2: dict, y_tolerance: float = 5.0, font_size_tolerance: float = 0.5) -> bool:
        """
        Determine if the second block is a continuation of the first block, 
        considering the font size, font name, and vertical alignment between spans.

        :param block1: The first text block.
        :param block2: The second text block.
        :param y_tolerance: The maximum vertical distance allowed between spans for them to be considered contiguous.
        :param font_size_tolerance: The allowable tolerance for font size difference.
        :return: True if the second block is a continuation of the first, False otherwise.
        """
        def get_non_empty_spans(block):
            """
            Extract non-empty spans from a block, filtering out spans with only whitespace.

            :param block: The text block containing lines and spans.
            :return: A list of non-empty spans.
            """
            return [
                span for line in block.get('lines', []) 
                for span in line.get('spans', []) 
                if span['text'].strip()  # Отфильтровываем спаны без текста
            ]

        spans1 = get_non_empty_spans(block1)
        spans2 = get_non_empty_spans(block2)

        # Логирование начальной информации о блоках
        # logger.debug(f"Comparing Block1 BBox: {block1['bbox']}, Block2 BBox: {block2['bbox']}")

        if not spans1 or not spans2:
            logger.debug(f"One of the blocks has no non-empty spans. Cannot be continuation.")
            return False  # Если один из блоков не содержит не пустых спанов, они не могут быть продолжением друг друга

        # Проверка шрифтов и размеров шрифтов между всеми спанами двух блоков
        for span1 in spans1:
            for span2 in spans2:
                font_size1, font_size2 = span1['size'], span2['size']
                font_name1, font_name2 = span1['font'], span2['font']

                # Проверяем, что имена шрифтов совпадают и размеры шрифтов равны с учетом допустимой погрешности
                is_font_size_equal = abs(font_size1 - font_size2) < font_size_tolerance
                is_font_name_equal = font_name1 == font_name2

                # Логирование проверки шрифтов и размеров шрифтов
                # logger.debug(f"Comparing spans - Font Size1: {font_size1}, Font Size2: {font_size2}, Font Name1: {font_name1}, Font Name2: {font_name2}")
                # logger.debug(f"Font Size Equal: {is_font_size_equal}, Font Name Equal: {is_font_name_equal}")

                # Если нашли хотя бы одну подходящую пару спанов, продолжаем проверку вертикальной непрерывности
                if is_font_size_equal and is_font_name_equal:
                    # Проверка вертикальной непрерывности между текущими span
                    is_vertical_continuation = span2['bbox'][1] < span1['bbox'][3] + y_tolerance

                    # Логирование результата вертикальной проверки
                    # logger.debug(f"Vertical Continuation Check - Span2 Top: {span2['bbox'][1]}, Span1 Bottom: {span1['bbox'][3]}, Tolerance: {y_tolerance}")
                    # logger.debug(f"Is Vertical Continuation: {is_vertical_continuation}")

                    # Если вертикальная непрерывность выполнена, блоки считаются продолжением
                    if is_vertical_continuation:
                        # logger.debug(f"Blocks are considered continuation.")
                        return True

        # Если не нашли ни одной подходящей пары спанов, блоки не являются продолжением
        # logger.debug(f"Blocks are not continuation.")
        return False

    def merge_text_blocks_with_continuation(self, blocks: List[dict], y_tolerance: float = 0.01) -> List[dict]:
        """
        Merge text blocks on the same page that are continuations of each other.

        :param blocks: List of text blocks from the page.
        :param y_tolerance: Maximum vertical distance between blocks to be considered for merging.
        :return: List of merged blocks.
        """
        merged_blocks = []
        current_block = None

        for block in blocks:
            # Проверяем, что у блока есть все нужные поля, иначе пропускаем
            if 'type' not in block or 'lines' not in block or 'bbox' not in block:
                continue

            # Проверяем, является ли текущий блок начальным блоком для слияния
            if current_block is None:
                current_block = block
            else:
                # Проверяем, если текущий блок является продолжением предыдущего
                if self.is_continuation(current_block, block, y_tolerance):
                    # Объединяем линии и спаны, без добавления текста в block_text
                    current_block['lines'].extend(block['lines'])

                    # Обновляем нижнюю границу bbox текущего блока
                    bbox_list = list(current_block['bbox'])
                    bbox_list[3] = block['bbox'][3]  # Обновляем нижнюю границу bbox
                    current_block['bbox'] = tuple(bbox_list)
                else:
                    # Если блоки не объединяются, добавляем текущий объединенный блок в список
                    merged_blocks.append(current_block)
                    # Переходим к следующему блоку
                    current_block = block

            # Сохраняем тип блока
            current_block['type'] = block['type']

        # Добавляем последний блок, если он не был объединен
        if current_block is not None:
            merged_blocks.append(current_block)

        return merged_blocks

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

            # Extract and process text blocks
            text_blocks = [block for block in text_dict['blocks'] if block['type'] == 0]
            # Merge blocks that are smaller continuations of each other
            merged_blocks = self.merge_text_blocks_with_continuation(text_blocks)

            # Step 1: Remove all original text blocks using redaction annotations
            for block in text_blocks:
                bbox = fitz.Rect(block['bbox'])  # Get the bounding box of the block
                font_size = block['lines'][0]['spans'][0]['size'] if block['lines'] and block['lines'][0]['spans'] else 12
                color = (1, 1, 1)  # White color to cover the original text
                fmt = "{:g} {:g} {:g} rg /{f:s} {s:g} Tf"
                da_str = fmt.format(*color, f='helv', s=font_size)
                new_page._add_redact_annot(quad=bbox, da_str=da_str)
                # logger.debug(f"Added redaction for original text block with bbox: {bbox}")

            # Apply redactions to remove original texts
            new_page.apply_redactions()

            # Extract and process each block on the page
            for block in merged_blocks:
                if block['type'] == 0:  # Text block
                    block_text = ''
                    big_text_block = self.is_big_text_block(block)
                    bbox = fitz.Rect(block['bbox']) 

                    lines = len(block['lines'])
                    for line in block['lines']:
                        spans = len(line['spans'])
                        for span in line['spans']:
                            original_text = span["text"].strip()
                            block_text += original_text + ' '
                            if not big_text_block and re.search(r'[A-Za-z0-9]', original_text):
                                page_texts.append(original_text)

                    if big_text_block and re.search(r'[A-Za-z0-9]', block_text):
                        page_texts.append(block_text.strip())


            # Prepare a new text dictionary with merged blocks for _apply_translated_texts
            merged_text_dict = {"blocks": merged_blocks}

            # Process image blocks
            for block in text_dict['blocks']:
                if block['type'] == 1:  # Image block
                    logger.debug(f"Processing image block on page {page_number + 1}")
                    self._process_image_block(block, new_page)

            # Translate extracted texts from the current page
            translated_texts = self.translator.translate_texts(page_texts)
            # translated_texts = page_texts
            # Apply translated texts back to the current page
            self._apply_translated_texts(merged_text_dict, new_page, translated_texts)

            # Update progress after translating each page
            self.document.update_progress(self.current_page, self.total_pages)

            if self.translator.source_language:
                logger.debug(f"Setting detected source language to the document: {self.translator.source_language}")
                self.document.source_language = self.translator.source_language
                self.document.save()

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
        Process an image block, translate it, and insert back to the PDF page.
        
        Small images are skipped, and if the translation process returns None, 
        the image is not inserted back into the PDF.

        :param block: The block containing image data.
        :param new_page: The page in the new PDF to insert the translated image into.
        """
        image_data = block.get("image")
        if not image_data:
            return

        # Convert the image data bytes into a PIL Image
        image = Image.open(BytesIO(image_data))  # Directly use image_data as bytes

        # Check the size of the image and skip if it's too small
        min_size = 350  # Example minimum size (in pixels) for both width and height
        logger.debug(f"image.width~:  {image.width}")
        if image.width < min_size:
            logger.debug(f"Skipping small image with dimensions {image.width}x{image.height}")
            return

        # Generate a unique hash for the image to prevent translating the same image multiple times
        image_hash = hashlib.md5(image_data).hexdigest()

        # Check if the translated image already exists in the cache
        if image_hash in self.image_cache:
            logger.debug(f"Using cached translated image for hash: {image_hash}")
            translated_image_path = self.image_cache[image_hash]
        else:
            # Save the image temporarily for translation
            temp_image_path = os.path.join(self.translations_dir, f"temp_image_{image_hash}.png")
            image.save(temp_image_path)

            # Translate the image using YandexImageTranslator
            # self.document.original_file.path = temp_image_path  # Update document with temp image path
            translated_image_path = self.yandex_translator.translate_image(image)

            # If no translation is available, skip insertion
            if translated_image_path is None:
                logger.debug("No text found in the image, skipping insertion.")
                return

            # Cache the translated image path
            self.image_cache[image_hash] = translated_image_path
            logger.debug(f"Translated and cached image with hash: {image_hash}")

        # Insert the translated image back into the PDF
        with Image.open(translated_image_path) as translated_image:
            translated_image = translated_image.convert('RGBA')
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
                # Берем bbox у блока, а не у span
                big_text_block = self.is_big_text_block(block)
                bbox = fitz.Rect(block['bbox'])  # Используем bbox непосредственно из блока
                block_text = ''
                first_span = None

                # Собираем текст из всех spans в блоке и берем характеристики текста из первого span
                for line in block['lines']:
                    for span in line['spans']:
                        if not first_span:
                            # Сохраняем характеристики из первого span
                            first_span = span

                        original_text = span["text"].strip()
                        block_text += original_text + ' '

                        if not big_text_block and re.search(r'[A-Za-z0-9]', original_text):
                            # Используем переведенный текст или оригинальный, если перевода нет
                            translated_text = translated_texts[text_index] if text_index < len(translated_texts) else original_text
                            text_index += 1

                            bbox = fitz.Rect(span['bbox'])

                            # Вставляем текст в зависимости от размера блока
                            self._apply_translated_text(new_page, span, translated_text, bbox, is_big_block=False, block=block)

                # Если есть текст в блоке, заменяем его на переведенный
                if big_text_block and first_span and re.search(r'[A-Za-z0-9]', block_text):
                    # Убираем лишние пробелы
                    block_text = block_text.strip()

                    # Используем переведенный текст или оригинальный, если перевода нет
                    translated_text = translated_texts[text_index] if text_index < len(translated_texts) else block_text
                    text_index += 1

                    if '•' in translated_text and translated_text.count('•') > 1:
                        translated_text = self.split_bullet_points(translated_text)

                    # Вставляем текст как большой блок
                    self._apply_translated_text(new_page, first_span, translated_text, bbox, is_big_block=True, block=block)

    def _apply_translated_text(self, new_page, first_span, translated_text, bbox, is_big_block, block):
        """
        Apply the translated text to the block using the properties of the first span in the block.

        :param new_page: Page object from PyMuPDF where the text will be placed.
        :param first_span: The first span of the text block that contains the text properties.
        :param translated_text: The translated version of the text to replace the original one.
        :param bbox: The bounding box of the text block.
        :param is_big_block: Flag indicating whether the block is considered big or not.
        :param block: The entire block from which we extract the rotation direction.
        """
        if not self.is_bbox_valid(bbox):
            logger.error(f"Invalid bbox encountered: {bbox}. Skipping text insertion.")
            return

        # Получаем все параметры текста из первого span
        font_size = round(first_span.get("size", 11.5)) - 2

        min_font_size = 3  # Минимальный размер шрифта, до которого уменьшаем
        if not is_big_block and font_size > 9.5:
            font_size = font_size - 1  # Ограничиваем минимальный размер шрифта

        if self.is_starts_with_bullet(block) and bbox.width < 250:
            bbox.x1 += 100

        # Начальная высота и ширина блока
        initial_bbox_height = bbox.height
        initial_bbox_width = bbox.width

        # Коэффициент увеличения высоты и ширины блока
        height_increase_step = initial_bbox_height * 0.05  # Увеличиваем высоту блока на 5%
        width_increase_step = initial_bbox_width * 0.05    # Увеличиваем ширину блока на 5%
        max_width = new_page.rect.width - 20 # Максимальная ширина с учетом отступа от края страницы

        color = self.normalize_color(first_span.get("color", 0))
        origin = first_span.get("origin", (0, 0))
        ascender = first_span.get("ascender", 0)
        descender = first_span.get("descender", 0)

        # Определяем угол поворота
        dir_x, dir_y = 1.0, 0.0  # Default values

        # Extract 'dir' from the first line or span, fallback if necessary
        if 'lines' in block and len(block['lines']) > 0:
            line = block['lines'][0]  # Take the first line
            dir_x, dir_y = line.get('dir', (1.0, 0.0))  # Get 'dir' from the line
        rotate_angle = self.calculate_rotation_angle(dir_x, dir_y)

        # Получаем шрифт и путь к файлу шрифта
        fontname = self.font_manager.clean_font_name(first_span.get("font", "Arial"))
        font_path = self.font_manager.find_font_path(fontname)

        # Проверяем наличие файла шрифта
        if not os.path.exists(font_path):
            logger.warning(f"Font '{fontname}' not found. Using Arial as default.")
            fontname = 'Arial'
            font_path = os.path.join(self.font_manager.fonts_dir, 'Arial.ttf')

        # Регистрируем шрифт
        new_page.insert_font(fontname=fontname, fontfile=font_path)

        # Форматирование для редактирования текста
        fmt = "{:g} {:g} {:g} rg /{f:s} {s:g} Tf"
        da_str = fmt.format(*color, f='helv', s=font_size)
        new_page._add_redact_annot(quad=bbox, da_str=da_str)

        # Применение редактирования и добавление переведенного текста с ротацией
        new_page.apply_redactions()

        # Попытка вставки текста с уменьшением шрифта при неудаче
        rc = -1
        while rc < 0 and font_size >= min_font_size:
            # Если блок большой, используем insert_textbox
            if is_big_block:
                rc = new_page.insert_textbox(
                    rect=bbox,  # Bounding box, где будет размещен текст
                    buffer=translated_text,  # Текст для вставки
                    fontsize=font_size,
                    fontname=fontname,
                    fontfile=font_path,
                    color=color,
                    align=fitz.TEXT_ALIGN_LEFT,  # Выравнивание текста
                    rotate=rotate_angle
                )
            else:
                # Рассчитываем скорректированную позицию текста
                adjusted_origin = (origin[0], origin[1] - ascender + descender)

                # Вставляем переведенный текст на страницу
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

            # Если вставка текста не удалась, уменьшаем размер шрифта
            # if rc < 0:
            #     font_size -= 1
            #     logger.error(f"Failed to insert text at {bbox.tl} on page {self.current_page + 1}. Retrying with smaller font size: {font_size}.")

            # Если вставка текста не удалась, уменьшаем размер шрифта или увеличиваем размеры блока
            if rc < 0:
                # Если минимальный размер шрифта достигнут, проверяем возможность расширения блока
                if bbox.width < max_width and self.is_starts_with_bullet(block):
                    # Увеличиваем ширину блока, если есть место справа
                    new_width = min(bbox.width + width_increase_step, max_width)
                    bbox.x1 += new_width - bbox.width
                    logger.error(f"Failed to insert text at {bbox.tl} on page {self.current_page + 1}. Increasing bbox width to {bbox.width}.")
                else:
                    # Если ширина блока максимальная, увеличиваем высоту блока
                    bbox.y1 += height_increase_step  # Увеличиваем нижнюю границу bbox на шаг
                    logger.error(f"Failed to insert text at {bbox.tl} on page {self.current_page + 1}. Increasing bbox height to {bbox.height}.")

        # Если не удалось вставить текст после всех попыток, логируем это как ошибку
        if rc < 0:
            logger.error(f"Unable to insert text after reducing font size. Failed at {bbox.tl} on page {self.current_page + 1}")

    def calculate_rotation_angle(self, dir_x: float, dir_y: float) -> int:
        """
        Calculate the rotation angle based on the text direction.

        :param dir_x: X direction component.
        :param dir_y: Y direction component.
        :return: Rotation angle in degrees, rounded to nearest valid value (0, 90, 180, 270).
        """
        rotate_angle = math.degrees(math.atan2(dir_y, dir_x))

        # Invert the angle to fix the incorrect rotation
        rotate_angle = -rotate_angle

        # Normalize the angle to [0, 360] degrees range
        if rotate_angle < 0:
            rotate_angle += 360

        # Snap to the nearest valid rotation (0, 90, 180, 270)
        if rotate_angle < 45 or rotate_angle >= 315:
            return 0
        elif 45 <= rotate_angle < 135:
            return 90
        elif 135 <= rotate_angle < 225:
            return 180
        elif 225 <= rotate_angle < 315:
            return 270

    def is_bbox_valid(self, bbox: fitz.Rect) -> bool:
        """
        Validate that the bounding box is finite and has positive width and height.

        :param bbox: fitz.Rect object representing the bounding box.
        :return: True if bbox is valid, False otherwise.
        """
        if not all(math.isfinite(coord) for coord in bbox):
            logger.error(f"Bounding box has non-finite coordinates: {bbox}")
            return False

        width = bbox.width
        height = bbox.height

        if width <= 0 or height <= 0:
            logger.error(f"Bounding box has non-positive dimensions: width={width}, height={height}")
            return False

        return True

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
    document = Document.objects.get(pk=391)  # Replace with actual document ID

    # Create an instance of PDFTranslator and translate the document
    pdf_translator = PDFTranslator(document)
    translated_pdf_path = pdf_translator.translate_pdf()
    print(f'Translated PDF saved at: {translated_pdf_path}')
