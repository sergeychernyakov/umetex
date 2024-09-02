# src/services/yandex_image_translator.py

import os

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'umetex_config.settings')
django.setup()


import logging
import json
import base64
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps
from django.conf import settings
from dotenv import load_dotenv
from backend.services.text_translator import TextTranslator
import re

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
        self.processed_image_name = f"processed_{document.pk}{file_extension}"
        self.translations_dir = os.path.join(settings.MEDIA_ROOT, str(document.pk), 'translations')
        os.makedirs(self.translations_dir, exist_ok=True)
        self.translated_image_path = os.path.join(self.translations_dir, self.translated_image_name)
        self.processed_image_path = os.path.join(self.translations_dir, self.processed_image_name)
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

    # def process_image(self, brightness: float = 1.0, contrast: float = 1.0, noise_filter_size: int = 3, threshold: int = 128) -> Image:
    #     """
    #     Process the image with specified parameters.

    #     :param brightness: Brightness enhancement factor.
    #     :param contrast: Contrast enhancement factor.
    #     :param noise_filter: Apply noise reduction if True.
    #     :param threshold: Threshold value for binary conversion.
    #     :return: Processed image.
    #     """
    #     try:
    #         original_image = Image.open(self.original_image_path).convert('RGB')
    #         processed_image = ImageOps.autocontrast(original_image)

    #         processed_image = processed_image.convert('L')

    #         # Enhance brightness
    #         processed_image = ImageEnhance.Brightness(processed_image).enhance(brightness)
    #         logger.debug(f"Brightness enhanced by a factor of {brightness}")

    #         # Enhance contrast
    #         processed_image = ImageEnhance.Contrast(processed_image).enhance(contrast)
    #         logger.debug(f"Contrast enhanced by a factor of {contrast}")

    #         # Apply noise reduction if specified
    #         if noise_filter_size > 0:
    #             processed_image = processed_image.filter(ImageFilter.MedianFilter(size=noise_filter_size))
    #             logger.debug("Noise reduction applied using MedianFilter")

    #         # Apply thresholding
    #         processed_image = processed_image.point(lambda p: p > threshold and 255)
    #         logger.debug(f"Thresholding applied with a value of {threshold}")

    #         # Save the processed image
    #         processed_image.save(self.processed_image_path)
    #         logger.info(f"Processed image saved at: {self.processed_image_path}")

    #         return processed_image
    #     except Exception as e:
    #         logger.error(f"Failed to process image: {e}")
    #         raise

    def extract_text(self, image: Image) -> tuple[list, list]:
        """
        Extract text from the image using Yandex Cloud OCR API.

        :param image: Image to perform OCR on.
        :return: Tuple of extracted texts and their positions.
        """
        try:
            encoded_image = self._encode_file(self.processed_image_path)
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

            # Process the API response and extract text and positions
            if 'result' in response_data and 'text_annotation' in response_data['result']:
                text_annotation = response_data['result']['text_annotation']
                for block in text_annotation.get('blocks', []):
                    for line in block.get('lines', []):
                        for alternative in line.get('alternatives', []):
                            text = alternative.get('text', '').strip()
                            if text:
                                bounding_box = line.get('bounding_box', {})
                                vertices = bounding_box.get('vertices', [])
                                if len(vertices) == 4:
                                    x = vertices[0]['x']
                                    y = vertices[0]['y']
                                    width = vertices[2]['x'] - x
                                    height = vertices[2]['y'] - y
                                    extracted_texts.append(text)
                                    text_positions.append((x, y, width, height))
                                    logger.debug(f"Extracted text: '{text}' at position ({x}, {y}, {width}, {height})")

            return extracted_texts, text_positions
        except Exception as e:
            logger.error(f"Failed to extract text using Yandex OCR API: {e}")
            raise

    def cleanup_texts(self, extracted_texts: list, text_positions: list) -> tuple[list, list]:
        """
        Clean up texts by removing unnecessary texts like short texts, numbers, or special characters.

        :param extracted_texts: List of extracted texts.
        :param text_positions: List of text positions.
        :return: Filtered texts and their corresponding positions.
        """
        cleaned_texts = []
        cleaned_positions = []
        for text, position in zip(extracted_texts, text_positions):
            cleaned_text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
            if len(cleaned_text) > 1 and (len(re.findall(r'[a-zA-Z]', cleaned_text)) / len(cleaned_text) > 0.6):
                cleaned_texts.append(cleaned_text)
                cleaned_positions.append(position)
                logger.debug(f"Text '{cleaned_text}' retained for translation")
            else:
                logger.debug(f"Text '{text}' skipped during cleanup")

        return cleaned_texts, cleaned_positions

    def apply_blur(self, image: Image, text_positions: list) -> None:
        """
        Apply blur effect to areas around text positions.

        :param image: Image to apply blur on.
        :param text_positions: List of text positions to blur around.
        """
        for (x, y, width, height) in text_positions:
            blur_margin = 30
            blur_area = (
                max(x - blur_margin, 0), 
                max(y - blur_margin, 0), 
                min(x + width + blur_margin, image.width), 
                min(y + height + blur_margin, image.height)
            )
            text_area = image.crop(blur_area)
            blurred_area = text_area.filter(ImageFilter.GaussianBlur(radius=20))

            mask = Image.new('L', blurred_area.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, blurred_area.size[0], blurred_area.size[1]), fill=245)

            blurred_area_with_oval = Image.composite(blurred_area, text_area, mask)
            image.paste(blurred_area_with_oval, blur_area)

    def overlay_text(self, image: Image, text_positions: list, original_texts: list, translated_texts: list) -> None:
        """
        Overlay translated text onto the image.

        :param image: Image to draw text on.
        :param text_positions: List of positions to draw text at.
        :param original_texts: List of original texts (not used in the current implementation).
        :param translated_texts: List of translated texts to draw.
        """
        draw = ImageDraw.Draw(image)
        for (x, y, width, height), translated_text in zip(text_positions, translated_texts):
            font_size = max(10, int(height * 0.8))
            font = ImageFont.truetype(self.font_path, font_size-2)
            draw.text((x, y), translated_text, font=font, fill="black")
            logger.debug(f"Applied translated text: '{translated_text}' at position ({x}, {y})")

    def filter_duplicate_texts(self, all_texts_positions: list) -> tuple[list, list]:
        """
        Filter duplicate texts at the same positions, keeping only the first occurrence.

        :param all_texts_positions: List of all extracted texts with positions from different parameter settings.
        :return: List of unique texts and their corresponding positions.
        """
        seen_texts_positions = set()
        filtered_texts = []
        filtered_positions = []

        for texts, positions in all_texts_positions:
            for text, position in zip(texts, positions):
                cleaned_text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
                if cleaned_text and (cleaned_text, position) not in seen_texts_positions:
                    seen_texts_positions.add((cleaned_text, position))
                    filtered_texts.append(text)
                    filtered_positions.append(position)
                    logger.debug(f"Added unique text '{text}' at position {position}")

        return filtered_texts, filtered_positions

    def translate_image(self, debug=False) -> str:
        """
        Translate image by processing with specific parameter sets, extracting text, and overlaying translated text.

        :return: Path to the translated image file.
        """
        self.document.update_progress(0, 1)

        all_texts_positions = []

        filtered_texts, filtered_positions = self.filter_duplicate_texts(all_texts_positions)
        # translated_texts = self.translator.translate_texts(filtered_texts) do not delete this line
        translated_texts = filtered_texts

        final_image = Image.open(self.original_image_path).convert('RGB')
        self.apply_blur(final_image, filtered_positions)
        self.overlay_text(final_image, filtered_positions, filtered_texts, translated_texts)

        try:
            final_image.save(self.translated_image_path)
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

    document = Document.objects.get(pk=236)  # Replace with actual document ID
    yandex_translator = YandexImageTranslator(document)
    translated_image_path = yandex_translator.translate_image()
    print(f'Translated image saved at: {translated_image_path}')
