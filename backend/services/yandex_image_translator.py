# backend/services/yandex_image_translator.py

import os
import logging
import json
import base64
import requests
import subprocess

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'umetex_config.settings')
django.setup()
    
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
                        file.write(f"YANDEX_IAM_TOKEN='{new_token}'\n")
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

    def get_font_size(self, text: str, width: int, scaling_factor: float = 1.0) -> int:
        """
        Determine the optimal font size to fit the text within the given width, considering a scaling factor.

        :param text: Text for which to determine the font size.
        :param width: Width of the block for the text.
        :param scaling_factor: Scaling factor for font size calculation.
        :return: Calculated font size.
        """
        font_size = 10
        max_font_size = 200
        font = ImageFont.truetype(self.font_path, int(font_size * scaling_factor))
        temp_image = Image.new('RGB', (width, 100))
        draw = ImageDraw.Draw(temp_image)

        while draw.textbbox((0, 0), text, font=font)[2] < width and font_size < max_font_size:
            font_size += 1
            font = ImageFont.truetype(self.font_path, int(font_size * scaling_factor))

        if draw.textbbox((0, 0), text, font=font)[2] > width:
            font_size -= 1

        font = ImageFont.truetype(self.font_path, int(font_size * scaling_factor))
        logger.debug(f"Optimal font size determined: {font_size} for text '{text}' and width {width}")
        return font_size

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
        logger.debug(f"Yandex OCR API response: {response.text}")

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

    def apply_blur(self, image: Image, text_positions: list, font_sizes: list) -> None:
        """
        Apply blur effect to areas around text positions, with blur margin proportional to the font size.

        :param image: Image to apply blur on.
        :param text_positions: List of text positions to blur around.
        :param font_sizes: List of font sizes corresponding to each text position.
        """
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        for (x, y, width, height), font_size in zip(text_positions, font_sizes):
            blur_margin = int(font_size * 0.5)
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
            mask_draw.ellipse((0, 0, blurred_area.size[0], blurred_area.size[1]), fill=235)

            blurred_area_with_oval = Image.composite(blurred_area, text_area, mask)
            image.paste(blurred_area_with_oval, blur_area)

    def overlay_text(self, image: Image, text_positions: list, original_texts: list, translated_texts: list, font_sizes: list) -> None:
        """
        Overlay translated text onto the image and draw boundaries around text blocks.

        :param image: Image to overlay text on.
        :param text_positions: List of positions to draw text.
        :param original_texts: List of original texts (not used in current implementation).
        :param translated_texts: List of translated texts to draw.
        :param font_sizes: List of font sizes for each text.
        """
        draw = ImageDraw.Draw(image)
        for (x, y, width, height), translated_text, font_size in zip(text_positions, translated_texts, font_sizes):
            font = ImageFont.truetype(self.font_path, font_size)
            text_bbox = draw.textbbox((0, 0), translated_text, font=font)
            text_height = text_bbox[3] - text_bbox[1]
            y_offset = text_height / 2

            draw.text((x, y - y_offset), translated_text, font=font, fill="black")
            logger.debug(f"Applied translated text: '{translated_text}' at position ({x}, {y - y_offset}) with font size {font_size}")

    def translate_image(self, image: Image, debug=False) -> str:
        """
        Translate the provided image by extracting text, cleaning it, and overlaying translated text.

        :param image: The PIL Image object to be translated.
        :param debug: If True, uses extracted texts directly without actual translation.
        :return: Path to the translated image file.
        """
        extracted_texts, text_positions, font_sizes = self.extract_text(image)

        translated_texts = extracted_texts if debug else self.translator.translate_texts(extracted_texts)
        #translated_texts = extracted_texts


        self.apply_blur(image, text_positions, font_sizes)
        self.overlay_text(image, text_positions, extracted_texts, translated_texts, font_sizes)

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir='/tmp') as temp_file:
                image.save(temp_file, format='PNG')
                temp_file_path = temp_file.name
            logger.info(f"Translated image saved at temporary path: {temp_file_path}")
        except Exception as e:
            logger.error(f"Failed to save translated image: {e}")
            raise

        return temp_file_path

# Example usage
# python3 -m backend.services.yandex_image_translator
if __name__ == '__main__':


    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)


    from PIL import Image
    # Specify the path to the image file you want to translate
    image_file_path = 'files_for_translation/anatomy-of-the-human-stomach-medical-poster-with-detailed-diagram-of-the-structure-of-the-internal-stomach-medical-infographic-banner-vector.jpg'
    
    # Set the translation language, e.g., 'en' for English
    translation_language = 'en'

    # Create an instance of YandexImageTranslator with the specified language
    yandex_translator = YandexImageTranslator(translation_language=translation_language)

    # Open the image using PIL
    with Image.open(image_file_path) as img:
        # Translate the image
        translated_image_path = yandex_translator.translate_image(img)
        print(f'Translated image saved at: {translated_image_path}')
