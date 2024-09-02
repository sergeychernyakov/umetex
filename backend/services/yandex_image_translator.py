# src/services/yandex_image_translator.py

import os
import logging
import json
import base64
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from django.conf import settings
from dotenv import load_dotenv
from backend.services.text_translator import TextTranslator

# Load environment variables from .env file
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class YandexImageTranslator:
    def __init__(self, document):
        """
        Initialize the YandexImageTranslator with a Document instance.

        :param document: Document instance containing the original image and translation details.
        """
        self.document = document
        self.total_pages = 1
        self.current_page = 0
        self.original_image_path = document.original_file.path
        file_extension = os.path.splitext(self.document.original_file.name)[1].lower()
        self.translated_image_name = f"translated_{document.pk}{file_extension}"
        self.translations_dir = os.path.join(settings.MEDIA_ROOT, str(document.pk), 'translations')
        os.makedirs(self.translations_dir, exist_ok=True)
        self.translated_image_path = os.path.join(self.translations_dir, self.translated_image_name)
        self.translator = TextTranslator(self.document.translation_language)
        self.font_path = os.path.join(settings.BASE_DIR, 'fonts', 'Arial Bold.ttf')
        self.iam_token = os.getenv('YANDEX_IAM_TOKEN')  # Get IAM token from .env file
        self.folder_id = os.getenv('YANDEX_FOLDER_ID')  # Replace with your folder ID

        if not self.iam_token:
            logger.error("IAM token not found. Please set YANDEX_IAM_TOKEN in the .env file.")
            raise ValueError("IAM token not found")

        logger.info(f"Initialized YandexImageTranslator for document ID: {document.pk}")

    def _encode_file(self, file_path: str) -> str:
        """
        Encodes an image file to Base64.

        :param file_path: The path to the image file.
        :return: Base64 encoded string of the image.
        """
        try:
            with open(file_path, "rb") as file:
                file_content = file.read()
            encoded_content = base64.b64encode(file_content).decode("utf-8")
            logger.debug(f"File encoded successfully: {file_path}")
            return encoded_content
        except Exception as e:
            logger.error(f"Failed to encode file {file_path}: {e}")
            raise

    def get_font_size(self, text: str, width: int, scaling_factor: float = 1.0) -> int:
        """
        Определяет оптимальный размер шрифта, чтобы текст максимально заполнил заданную ширину блока,
        с учетом коэффициента масштабирования.

        :param text: Текст, для которого определяется размер шрифта.
        :param width: Ширина блока для текста.
        :param scaling_factor: Коэффициент масштабирования для расчета размера шрифта.
        :return: Определенный размер шрифта.
        """
        # Начальный размер шрифта
        font_size = 10
        max_font_size = 200  # Допустимый максимальный размер шрифта
        font = ImageFont.truetype(self.font_path, int(font_size * scaling_factor))
        temp_image = Image.new('RGB', (width, 100))
        draw = ImageDraw.Draw(temp_image)

        # Увеличиваем размер шрифта, пока текст помещается в указанный блок по ширине
        while draw.textbbox((0, 0), text, font=font)[2] < width and font_size < max_font_size:
            font_size += 1
            font = ImageFont.truetype(self.font_path, int(font_size * scaling_factor))

        # Если размер шрифта превысил ширину, уменьшаем его на 1
        if draw.textbbox((0, 0), text, font=font)[2] > width:
            font_size -= 1

        font = ImageFont.truetype(self.font_path, int(font_size * scaling_factor))
        logger.debug(f"Определен оптимальный размер шрифта: {font_size} для текста '{text}' и блока шириной {width}")
        return font_size

    def extract_text(self) -> tuple[list, list, list]:
        """
        Extract text from the image using Yandex Cloud OCR API.

        :return: Tuple of extracted texts, their positions, and calculated font sizes.
        """
        encoded_image = self._encode_file(self.original_image_path)
        url = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"
        data = {
            "mimeType": "JPEG",
            "languageCodes": ["*"],
            "model": "page",
            "content": encoded_image
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.iam_token}",
            "x-folder-id": self.folder_id,
            "x-data-logging-enabled": "true"
        }

        response = requests.post(url=url, headers=headers, data=json.dumps(data))
        response_data = response.json()


        extracted_texts = []
        text_positions = []
        font_sizes = []

        if 'result' in response_data and 'textAnnotation' in response_data['result']:
            text_annotation = response_data['result']['textAnnotation']
            if 'blocks' in text_annotation:
                for block in text_annotation['blocks']:
                    if 'lines' in block:
                        for line in block['lines']:
                            # Extracting text directly from line level
                            text = line.get('text', '').strip()
                            if text:
                                # Collecting bounding box info
                                bounding_box = line.get('boundingBox', {})
                                vertices = bounding_box.get('vertices', [])
                                if len(vertices) == 4:
                                    x = int(vertices[0]['x'])
                                    y = int(vertices[0]['y'])
                                    width = int(vertices[2]['x']) - x
                                    height = int(vertices[2]['y']) - y
                                    font_size = self.get_font_size(text, width)
                                    extracted_texts.append(text)
                                    text_positions.append((x, y, width, height))
                                    font_sizes.append(font_size)
                                    logger.debug(f"Extracted text: '{text}' at position ({x}, {y}, {width}, {height}) with font size {font_size}")


        logger.info(f"Extracted {len(extracted_texts)} texts from the image.")
        return extracted_texts, text_positions, font_sizes

    def apply_blur(self, image: Image, text_positions: list, font_sizes: list) -> None:
        """
        Apply blur effect to areas around text positions, with blur margin proportional to the font size.

        :param image: Image to apply blur on.
        :param text_positions: List of text positions to blur around.
        :param font_sizes: List of font sizes corresponding to each text position.
        """
        for (x, y, width, height), font_size in zip(text_positions, font_sizes):
            # Устанавливаем значение blur_margin пропорционально размеру шрифта
            blur_margin = int(font_size * 0.5)  # Половина размера шрифта

            # Определяем область размытия с учетом поля
            blur_area = (
                max(x - blur_margin, 0), 
                max(y - blur_margin, 0), 
                min(x + width + blur_margin, image.width), 
                min(y + height + blur_margin, image.height)
            )

            # Создаем копию области и применяем размытие
            text_area = image.crop(blur_area)
            blurred_area = text_area.filter(ImageFilter.GaussianBlur(radius=20))

            # Создаем маску для овального размытия
            mask = Image.new('L', blurred_area.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, blurred_area.size[0], blurred_area.size[1]), fill=235)

            # Наложение размытой области на исходное изображение с маской
            blurred_area_with_oval = Image.composite(blurred_area, text_area, mask)
            image.paste(blurred_area_with_oval, blur_area)

    def overlay_text(self, image: Image, text_positions: list, original_texts: list, translated_texts: list, font_sizes: list) -> None:
        """
        Наложить переведенный текст на изображение и отобразить границы блоков.

        :param image: Изображение, на котором рисуется текст.
        :param text_positions: Список позиций для рисования текста.
        :param original_texts: Список оригинальных текстов (не используется в текущей реализации).
        :param translated_texts: Список переведенных текстов для рисования.
        :param font_sizes: Список размеров шрифта для каждого текста.
        """
        draw = ImageDraw.Draw(image)
        for (x, y, width, height), translated_text, font_size in zip(text_positions, translated_texts, font_sizes):
            # Применяем размер шрифта напрямую из списка font_sizes
            font = ImageFont.truetype(self.font_path, font_size)
            
            # Вычисляем смещение по оси y для центрирования текста
            text_bbox = draw.textbbox((0, 0), translated_text, font=font)
            text_height = text_bbox[3] - text_bbox[1]
            y_offset = text_height / 2

            # Нарисовать переведенный текст внутри блока
            draw.text((x, y - y_offset), translated_text, font=font, fill="black")

            logger.debug(f"Применен переведенный текст: '{translated_text}' в позиции ({x}, {y + y_offset}) с размером шрифта {font_size} и нарисован ограничивающий прямоугольник")

    def translate_image(self, debug=False) -> str:
        """
        Translate image by extracting text, cleaning it, and overlaying translated text.

        :param debug: If True, enables debug mode.
        :return: Path to the translated image file.
        """
        self.document.update_progress(0, 1)

        # Load the original image
        original_image = Image.open(self.original_image_path).convert('RGB')

        # Extract text from the original image using the extract_text method
        extracted_texts, text_positions, font_sizes = self.extract_text()

        # Translate texts (using the original for now)
        if debug:
            translated_texts = extracted_texts  # For now, using filtered texts directly
        else:
            translated_texts = self.translator.translate_texts(extracted_texts)  # Replace with actual translation logic


        # Apply blur effect on the original image based on text positions
        self.apply_blur(original_image, text_positions, font_sizes)

        # Overlay translated text onto the original image
        self.overlay_text(original_image, text_positions, extracted_texts, translated_texts, font_sizes)

        try:
            original_image.save(self.translated_image_path)
            self.document.translated_file.name = f'{self.document.pk}/translations/{self.translated_image_name}'
            self.document.save()
            logger.info(f"Final translated image saved at: {self.translated_image_path}")
        except Exception as e:
            logger.error(f"Failed to save final translated image: {e}")
            raise

        self.document.update_progress(1, 1)
        return self.translated_image_path

# Example usage
# python3 -m backend.services.yandex_image_translator
if __name__ == '__main__':
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

    document = Document.objects.get(pk=293)  # Replace with actual document ID
    yandex_translator = YandexImageTranslator(document)
    translated_image_path = yandex_translator.translate_image()
    print(f'Translated image saved at: {translated_image_path}')
