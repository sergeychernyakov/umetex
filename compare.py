import os
import logging
import json
import base64
import requests
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from django.conf import settings
from dotenv import load_dotenv
from backend.services.text_translator import TextTranslator
import tempfile

# Load environment variables from .env file
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class YandexImageTranslator:
    def __init__(self, translation_language: str):
        """
        Initialize the YandexImageTranslator with a specified translation language.

        :param translation_language: The language into which the image text should be translated.
        """
        self.translation_language = translation_language
        self.translator = TextTranslator(translation_language)
        self.font_path = os.path.join(settings.BASE_DIR, 'fonts', 'Arial Bold.ttf')
        self.iam_token = os.getenv('YANDEX_IAM_TOKEN')
        self.folder_id = os.getenv('YANDEX_FOLDER_ID')

        if not self.iam_token:
            self._refresh_token()
        
        logger.info(f"Initialized YandexImageTranslator for language: {translation_language}")

    def _refresh_token(self):
        """
        Refresh the IAM token using the yc command line tool.
        """
        try:
            logger.info("Refreshing IAM token...")
            new_token = subprocess.check_output(["yc", "iam", "create-token"], text=True).strip()
            self.iam_token = new_token

            # Save the new token to the .env file
            with open('.env', 'r') as file:
                lines = file.readlines()

            with open('.env', 'w') as file:
                for line in lines:
                    if line.startswith('YANDEX_IAM_TOKEN'):
                        file.write(f'YANDEX_IAM_TOKEN={new_token}\n')
                    else:
                        file.write(line)

            logger.info("IAM token refreshed successfully.")
        except Exception as e:
            logger.error(f"Failed to refresh IAM token: {e}")
            raise

    def _encode_image(self, image: Image) -> str:
        """
        Encodes an image object to Base64.

        :param image: The PIL Image object.
        :return: Base64 encoded string of the image.
        """
        try:
            with tempfile.NamedTemporaryFile(suffix=".png") as temp_file:
                image.save(temp_file, format="PNG")
                temp_file.seek(0)
                file_content = temp_file.read()
            encoded_content = base64.b64encode(file_content).decode("utf-8")
            logger.debug("Image encoded successfully.")
            return encoded_content
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            raise

    def extract_text(self, image: Image) -> tuple[list, list, list]:
        """
        Extract text from the image using Yandex Cloud OCR API.

        :param image: The PIL Image object.
        :return: Tuple of extracted texts, their positions, and calculated font sizes.
        """
        encoded_image = self._encode_image(image)
        url = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"
        data = {
            "mimeType": "PNG",
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
        
        if response.status_code == 401 and 'The token has expired' in response.text:
            logger.warning("IAM token has expired. Refreshing token...")
            self._refresh_token()
            headers["Authorization"] = f"Bearer {self.iam_token}"
            response = requests.post(url=url, headers=headers, data=json.dumps(data))

        response_data = response.json()
        
        # Log the full response data for debugging
        logger.debug(f"Yandex OCR API response: {response_data}")

        extracted_texts = []
        text_positions = []
        font_sizes = []

        if 'result' in response_data and 'textAnnotation' in response_data['result']:
            text_annotation = response_data['result']['textAnnotation']
            if 'blocks' in text_annotation:
                for block in text_annotation['blocks']:
                    if 'lines' in block:
                        for line in block['lines']:
                            text = line.get('text', '').strip()
                            if text:
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

    # Rest of the methods (apply_blur, overlay_text, translate_image) remain unchanged
    # ...

# Example usage remains the same