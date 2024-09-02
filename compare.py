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

    def get_font_size(self, text: str, width: int, scaling_factor: float = 1.0) -> int:
        """
        Определяет оптимальный размер шрифта, чтобы текст помещался в пределах заданной ширины блока,
        с учетом коэффициента масштабирования.

        :param text: Текст, для которого определяется размер шрифта.
        :param width: Ширина блока для текста.
        :param scaling_factor: Коэффициент масштабирования для расчета размера шрифта.
        :return: Определенный размер шрифта.
        """
        # Начальный размер шрифта
        font_size = 40
        font = ImageFont.truetype(self.font_path, int(font_size * scaling_factor))
        temp_image = Image.new('RGB', (width, 100))  # Используем временное изображение
        draw = ImageDraw.Draw(temp_image)

        # Уменьшение размера шрифта, пока текст не впишется в указанный блок по ширине
        while draw.textbbox((0, 0), text, font=font)[2] > width and font_size > 10:
            font_size -= 1
            font = ImageFont.truetype(self.font_path, int(font_size * scaling_factor))

        logger.debug(f"Определен оптимальный размер шрифта: {font_size} для текста '{text}' и блока шириной {width}")
        return font_size

    def extract_text(self) -> tuple[list, list, list]:
        """
        Extract text from the image using Yandex Cloud OCR API.

        :return: Tuple of extracted texts, their positions, and calculated font sizes.
        """
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

        # response = requests.post(url=url, headers=headers, data=json.dumps(data))
        # response_data = response.json()

        # Mock response_data for testing
        response_data = {'result': {'textAnnotation': {'width': '1999', 'height': '1143', 'blocks': [{'boundingBox': {'vertices': [{'x': '952', 'y': '112'}, {'x': '952', 'y': '128'}, {'x': '1036', 'y': '128'}, {'x': '1036', 'y': '112'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '952', 'y': '112'}, {'x': '952', 'y': '128'}, {'x': '1036', 'y': '128'}, {'x': '1036', 'y': '112'}]}, 'text': 'Guests', 'words': [{'boundingBox': {'vertices': [{'x': '952', 'y': '110'}, {'x': '952', 'y': '131'}, {'x': '1036', 'y': '131'}, {'x': '1036', 'y': '110'}]}, 'text': 'Guests', 'entityIndex': '-1', 'textSegments': [{'startIndex': '0', 'length': '6'}]}], 'textSegments': [{'startIndex': '0', 'length': '6'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '0', 'length': '6'}]}, {'boundingBox': {'vertices': [{'x': '473', 'y': '286'}, {'x': '473', 'y': '301'}, {'x': '554', 'y': '301'}, {'x': '554', 'y': '286'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '473', 'y': '286'}, {'x': '473', 'y': '301'}, {'x': '554', 'y': '301'}, {'x': '554', 'y': '286'}]}, 'text': 'Guest', 'words': [{'boundingBox': {'vertices': [{'x': '473', 'y': '284'}, {'x': '473', 'y': '304'}, {'x': '554', 'y': '304'}, {'x': '554', 'y': '284'}]}, 'text': 'Guest', 'entityIndex': '-1', 'textSegments': [{'startIndex': '7', 'length': '5'}]}], 'textSegments': [{'startIndex': '7', 'length': '5'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '7', 'length': '5'}]}, {'boundingBox': {'vertices': [{'x': '726', 'y': '321'}, {'x': '726', 'y': '363'}, {'x': '819', 'y': '363'}, {'x': '819', 'y': '321'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '726', 'y': '321'}, {'x': '726', 'y': '336'}, {'x': '819', 'y': '336'}, {'x': '819', 'y': '321'}]}, 'text': 'Booking', 'words': [{'boundingBox': {'vertices': [{'x': '726', 'y': '319'}, {'x': '726', 'y': '339'}, {'x': '819', 'y': '339'}, {'x': '819', 'y': '319'}]}, 'text': 'Booking', 'entityIndex': '-1', 'textSegments': [{'startIndex': '13', 'length': '7'}]}], 'textSegments': [{'startIndex': '13', 'length': '7'}], 'orientation': 'ANGLE_0'}, {'boundingBox': {'vertices': [{'x': '727', 'y': '351'}, {'x': '727', 'y': '363'}, {'x': '819', 'y': '363'}, {'x': '819', 'y': '351'}]}, 'text': 'request', 'words': [{'boundingBox': {'vertices': [{'x': '727', 'y': '349'}, {'x': '727', 'y': '366'}, {'x': '819', 'y': '366'}, {'x': '819', 'y': '349'}]}, 'text': 'request', 'entityIndex': '-1', 'textSegments': [{'startIndex': '21', 'length': '7'}]}], 'textSegments': [{'startIndex': '21', 'length': '7'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '13', 'length': '15'}]}, {'boundingBox': {'vertices': [{'x': '965', 'y': '309'}, {'x': '965', 'y': '322'}, {'x': '1034', 'y': '322'}, {'x': '1034', 'y': '309'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '965', 'y': '309'}, {'x': '965', 'y': '322'}, {'x': '1034', 'y': '322'}, {'x': '1034', 'y': '309'}]}, 'text': 'Guest', 'words': [{'boundingBox': {'vertices': [{'x': '965', 'y': '307'}, {'x': '965', 'y': '324'}, {'x': '1034', 'y': '324'}, {'x': '1034', 'y': '307'}]}, 'text': 'Guest', 'entityIndex': '-1', 'textSegments': [{'startIndex': '29', 'length': '5'}]}], 'textSegments': [{'startIndex': '29', 'length': '5'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '29', 'length': '5'}]}, {'boundingBox': {'vertices': [{'x': '1110', 'y': '305'}, {'x': '1110', 'y': '349'}, {'x': '1256', 'y': '349'}, {'x': '1256', 'y': '305'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '1137', 'y': '305'}, {'x': '1137', 'y': '323'}, {'x': '1232', 'y': '323'}, {'x': '1232', 'y': '305'}]}, 'text': 'Booking', 'words': [{'boundingBox': {'vertices': [{'x': '1137', 'y': '304'}, {'x': '1137', 'y': '326'}, {'x': '1232', 'y': '326'}, {'x': '1232', 'y': '304'}]}, 'text': 'Booking', 'entityIndex': '-1', 'textSegments': [{'startIndex': '35', 'length': '7'}]}], 'textSegments': [{'startIndex': '35', 'length': '7'}], 'orientation': 'ANGLE_0'}, {'boundingBox': {'vertices': [{'x': '1110', 'y': '336'}, {'x': '1110', 'y': '349'}, {'x': '1256', 'y': '349'}, {'x': '1256', 'y': '336'}]}, 'text': 'confirmation', 'words': [{'boundingBox': {'vertices': [{'x': '1110', 'y': '335'}, {'x': '1110', 'y': '352'}, {'x': '1256', 'y': '352'}, {'x': '1256', 'y': '335'}]}, 'text': 'confirmation', 'entityIndex': '-1', 'textSegments': [{'startIndex': '43', 'length': '12'}]}], 'textSegments': [{'startIndex': '43', 'length': '12'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '35', 'length': '20'}]}, {'boundingBox': {'vertices': [{'x': '1376', 'y': '272'}, {'x': '1376', 'y': '315'}, {'x': '1610', 'y': '315'}, {'x': '1610', 'y': '272'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '1447', 'y': '272'}, {'x': '1447', 'y': '288'}, {'x': '1555', 'y': '288'}, {'x': '1555', 'y': '272'}]}, 'text': 'External', 'words': [{'boundingBox': {'vertices': [{'x': '1447', 'y': '270'}, {'x': '1447', 'y': '291'}, {'x': '1555', 'y': '291'}, {'x': '1555', 'y': '270'}]}, 'text': 'External', 'entityIndex': '-1', 'textSegments': [{'startIndex': '56', 'length': '8'}]}], 'textSegments': [{'startIndex': '56', 'length': '8'}], 'orientation': 'ANGLE_0'}, {'boundingBox': {'vertices': [{'x': '1376', 'y': '300'}, {'x': '1376', 'y': '315'}, {'x': '1610', 'y': '315'}, {'x': '1610', 'y': '300'}]}, 'text': 'Reservation System', 'words': [{'boundingBox': {'vertices': [{'x': '1376', 'y': '298'}, {'x': '1376', 'y': '318'}, {'x': '1517', 'y': '318'}, {'x': '1517', 'y': '298'}]}, 'text': 'Reservation', 'entityIndex': '-1', 'textSegments': [{'startIndex': '65', 'length': '11'}]}, {'boundingBox': {'vertices': [{'x': '1528', 'y': '298'}, {'x': '1528', 'y': '318'}, {'x': '1610', 'y': '318'}, {'x': '1610', 'y': '298'}]}, 'text': 'System', 'entityIndex': '-1', 'textSegments': [{'startIndex': '77', 'length': '6'}]}], 'textSegments': [{'startIndex': '65', 'length': '18'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '56', 'length': '27'}]}, {'boundingBox': {'vertices': [{'x': '599', 'y': '461'}, {'x': '599', 'y': '505'}, {'x': '743', 'y': '505'}, {'x': '743', 'y': '461'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '626', 'y': '461'}, {'x': '626', 'y': '479'}, {'x': '718', 'y': '479'}, {'x': '718', 'y': '461'}]}, 'text': 'Booking', 'words': [{'boundingBox': {'vertices': [{'x': '626', 'y': '459'}, {'x': '626', 'y': '482'}, {'x': '718', 'y': '482'}, {'x': '718', 'y': '459'}]}, 'text': 'Booking', 'entityIndex': '-1', 'textSegments': [{'startIndex': '84', 'length': '7'}]}], 'textSegments': [{'startIndex': '84', 'length': '7'}], 'orientation': 'ANGLE_0'}, {'boundingBox': {'vertices': [{'x': '599', 'y': '491'}, {'x': '599', 'y': '505'}, {'x': '743', 'y': '505'}, {'x': '743', 'y': '491'}]}, 'text': 'confirmation', 'words': [{'boundingBox': {'vertices': [{'x': '599', 'y': '488'}, {'x': '599', 'y': '508'}, {'x': '743', 'y': '508'}, {'x': '743', 'y': '488'}]}, 'text': 'confirmation', 'entityIndex': '-1', 'textSegments': [{'startIndex': '92', 'length': '12'}]}], 'textSegments': [{'startIndex': '92', 'length': '12'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '84', 'length': '20'}]}, {'boundingBox': {'vertices': [{'x': '1384', 'y': '451'}, {'x': '1384', 'y': '495'}, {'x': '1485', 'y': '495'}, {'x': '1485', 'y': '451'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '1388', 'y': '451'}, {'x': '1388', 'y': '467'}, {'x': '1480', 'y': '467'}, {'x': '1480', 'y': '451'}]}, 'text': 'Booking', 'words': [{'boundingBox': {'vertices': [{'x': '1388', 'y': '449'}, {'x': '1388', 'y': '470'}, {'x': '1480', 'y': '470'}, {'x': '1480', 'y': '449'}]}, 'text': 'Booking', 'entityIndex': '-1', 'textSegments': [{'startIndex': '105', 'length': '7'}]}], 'textSegments': [{'startIndex': '105', 'length': '7'}], 'orientation': 'ANGLE_0'}, {'boundingBox': {'vertices': [{'x': '1384', 'y': '481'}, {'x': '1384', 'y': '495'}, {'x': '1485', 'y': '495'}, {'x': '1485', 'y': '481'}]}, 'text': 'request', 'words': [{'boundingBox': {'vertices': [{'x': '1384', 'y': '479'}, {'x': '1384', 'y': '498'}, {'x': '1485', 'y': '498'}, {'x': '1485', 'y': '479'}]}, 'text': 'request', 'entityIndex': '-1', 'textSegments': [{'startIndex': '113', 'length': '7'}]}], 'textSegments': [{'startIndex': '113', 'length': '7'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '105', 'length': '15'}]}, {'boundingBox': {'vertices': [{'x': '919', 'y': '557'}, {'x': '919', 'y': '575'}, {'x': '1074', 'y': '575'}, {'x': '1074', 'y': '557'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '919', 'y': '557'}, {'x': '919', 'y': '575'}, {'x': '1074', 'y': '575'}, {'x': '1074', 'y': '557'}]}, 'text': 'Book Roob', 'words': [{'boundingBox': {'vertices': [{'x': '919', 'y': '555'}, {'x': '919', 'y': '579'}, {'x': '988', 'y': '579'}, {'x': '988', 'y': '555'}]}, 'text': 'Book', 'entityIndex': '-1', 'textSegments': [{'startIndex': '121', 'length': '4'}]}, {'boundingBox': {'vertices': [{'x': '997', 'y': '555'}, {'x': '997', 'y': '578'}, {'x': '1074', 'y': '578'}, {'x': '1074', 'y': '555'}]}, 'text': 'Roob', 'entityIndex': '-1', 'textSegments': [{'startIndex': '126', 'length': '4'}]}], 'textSegments': [{'startIndex': '121', 'length': '9'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '121', 'length': '9'}]}, {'boundingBox': {'vertices': [{'x': '436', 'y': '599'}, {'x': '436', 'y': '618'}, {'x': '555', 'y': '618'}, {'x': '555', 'y': '599'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '436', 'y': '599'}, {'x': '436', 'y': '618'}, {'x': '555', 'y': '618'}, {'x': '555', 'y': '599'}]}, 'text': 'Bookings', 'words': [{'boundingBox': {'vertices': [{'x': '436', 'y': '597'}, {'x': '436', 'y': '621'}, {'x': '555', 'y': '621'}, {'x': '555', 'y': '597'}]}, 'text': 'Bookings', 'entityIndex': '-1', 'textSegments': [{'startIndex': '131', 'length': '8'}]}], 'textSegments': [{'startIndex': '131', 'length': '8'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '131', 'length': '8'}]}, {'boundingBox': {'vertices': [{'x': '722', 'y': '593'}, {'x': '722', 'y': '612'}, {'x': '814', 'y': '612'}, {'x': '814', 'y': '593'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '722', 'y': '593'}, {'x': '722', 'y': '612'}, {'x': '814', 'y': '612'}, {'x': '814', 'y': '593'}]}, 'text': 'Booking', 'words': [{'boundingBox': {'vertices': [{'x': '722', 'y': '591'}, {'x': '722', 'y': '614'}, {'x': '814', 'y': '614'}, {'x': '814', 'y': '591'}]}, 'text': 'Booking', 'entityIndex': '-1', 'textSegments': [{'startIndex': '140', 'length': '7'}]}], 'textSegments': [{'startIndex': '140', 'length': '7'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '140', 'length': '7'}]}, {'boundingBox': {'vertices': [{'x': '1459', 'y': '600'}, {'x': '1459', 'y': '616'}, {'x': '1544', 'y': '616'}, {'x': '1544', 'y': '600'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '1459', 'y': '600'}, {'x': '1459', 'y': '616'}, {'x': '1544', 'y': '616'}, {'x': '1544', 'y': '600'}]}, 'text': 'Rooms', 'words': [{'boundingBox': {'vertices': [{'x': '1459', 'y': '598'}, {'x': '1459', 'y': '619'}, {'x': '1544', 'y': '619'}, {'x': '1544', 'y': '598'}]}, 'text': 'Rooms', 'entityIndex': '-1', 'textSegments': [{'startIndex': '148', 'length': '5'}]}], 'textSegments': [{'startIndex': '148', 'length': '5'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '148', 'length': '5'}]}, {'boundingBox': {'vertices': [{'x': '1229', 'y': '647'}, {'x': '1229', 'y': '668'}, {'x': '1290', 'y': '668'}, {'x': '1290', 'y': '647'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '1229', 'y': '647'}, {'x': '1229', 'y': '668'}, {'x': '1290', 'y': '668'}, {'x': '1290', 'y': '647'}]}, 'text': 'Room', 'words': [{'boundingBox': {'vertices': [{'x': '1229', 'y': '646'}, {'x': '1229', 'y': '669'}, {'x': '1290', 'y': '669'}, {'x': '1290', 'y': '646'}]}, 'text': 'Room', 'entityIndex': '-1', 'textSegments': [{'startIndex': '154', 'length': '4'}]}], 'textSegments': [{'startIndex': '154', 'length': '4'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '154', 'length': '4'}]}, {'boundingBox': {'vertices': [{'x': '709', 'y': '737'}, {'x': '709', 'y': '779'}, {'x': '827', 'y': '779'}, {'x': '827', 'y': '737'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '709', 'y': '737'}, {'x': '709', 'y': '752'}, {'x': '826', 'y': '752'}, {'x': '826', 'y': '737'}]}, 'text': 'Payment', 'words': [{'boundingBox': {'vertices': [{'x': '709', 'y': '735'}, {'x': '709', 'y': '755'}, {'x': '826', 'y': '755'}, {'x': '826', 'y': '735'}]}, 'text': 'Payment', 'entityIndex': '-1', 'textSegments': [{'startIndex': '159', 'length': '7'}]}], 'textSegments': [{'startIndex': '159', 'length': '7'}], 'orientation': 'ANGLE_0'}, {'boundingBox': {'vertices': [{'x': '712', 'y': '767'}, {'x': '712', 'y': '779'}, {'x': '827', 'y': '779'}, {'x': '827', 'y': '767'}]}, 'text': 'validation', 'words': [{'boundingBox': {'vertices': [{'x': '712', 'y': '765'}, {'x': '712', 'y': '782'}, {'x': '827', 'y': '782'}, {'x': '827', 'y': '765'}]}, 'text': 'validation', 'entityIndex': '-1', 'textSegments': [{'startIndex': '167', 'length': '10'}]}], 'textSegments': [{'startIndex': '167', 'length': '10'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '159', 'length': '18'}]}, {'boundingBox': {'vertices': [{'x': '885', 'y': '809'}, {'x': '885', 'y': '881'}, {'x': '1001', 'y': '881'}, {'x': '1001', 'y': '809'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '891', 'y': '809'}, {'x': '891', 'y': '824'}, {'x': '999', 'y': '824'}, {'x': '999', 'y': '809'}]}, 'text': 'Payment', 'words': [{'boundingBox': {'vertices': [{'x': '891', 'y': '807'}, {'x': '891', 'y': '827'}, {'x': '999', 'y': '827'}, {'x': '999', 'y': '807'}]}, 'text': 'Payment', 'entityIndex': '-1', 'textSegments': [{'startIndex': '178', 'length': '7'}]}], 'textSegments': [{'startIndex': '178', 'length': '7'}], 'orientation': 'ANGLE_0'}, {'boundingBox': {'vertices': [{'x': '885', 'y': '838'}, {'x': '885', 'y': '851'}, {'x': '1001', 'y': '851'}, {'x': '1001', 'y': '838'}]}, 'text': 'validation', 'words': [{'boundingBox': {'vertices': [{'x': '885', 'y': '836'}, {'x': '885', 'y': '854'}, {'x': '1001', 'y': '854'}, {'x': '1001', 'y': '836'}]}, 'text': 'validation', 'entityIndex': '-1', 'textSegments': [{'startIndex': '186', 'length': '10'}]}], 'textSegments': [{'startIndex': '186', 'length': '10'}], 'orientation': 'ANGLE_0'}, {'boundingBox': {'vertices': [{'x': '892', 'y': '867'}, {'x': '892', 'y': '881'}, {'x': '993', 'y': '881'}, {'x': '993', 'y': '867'}]}, 'text': 'request', 'words': [{'boundingBox': {'vertices': [{'x': '892', 'y': '865'}, {'x': '892', 'y': '884'}, {'x': '993', 'y': '884'}, {'x': '993', 'y': '865'}]}, 'text': 'request', 'entityIndex': '-1', 'textSegments': [{'startIndex': '197', 'length': '7'}]}], 'textSegments': [{'startIndex': '197', 'length': '7'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '178', 'length': '26'}]}, {'boundingBox': {'vertices': [{'x': '1153', 'y': '788'}, {'x': '1153', 'y': '830'}, {'x': '1244', 'y': '830'}, {'x': '1244', 'y': '788'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '1153', 'y': '788'}, {'x': '1153', 'y': '801'}, {'x': '1244', 'y': '801'}, {'x': '1244', 'y': '788'}]}, 'text': 'Current', 'words': [{'boundingBox': {'vertices': [{'x': '1153', 'y': '786'}, {'x': '1153', 'y': '804'}, {'x': '1244', 'y': '804'}, {'x': '1244', 'y': '786'}]}, 'text': 'Current', 'entityIndex': '-1', 'textSegments': [{'startIndex': '205', 'length': '7'}]}], 'textSegments': [{'startIndex': '205', 'length': '7'}], 'orientation': 'ANGLE_0'}, {'boundingBox': {'vertices': [{'x': '1170', 'y': '817'}, {'x': '1170', 'y': '830'}, {'x': '1221', 'y': '830'}, {'x': '1221', 'y': '817'}]}, 'text': 'time', 'words': [{'boundingBox': {'vertices': [{'x': '1170', 'y': '816'}, {'x': '1170', 'y': '832'}, {'x': '1221', 'y': '832'}, {'x': '1221', 'y': '816'}]}, 'text': 'time', 'entityIndex': '-1', 'textSegments': [{'startIndex': '213', 'length': '4'}]}], 'textSegments': [{'startIndex': '213', 'length': '4'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '205', 'length': '12'}]}, {'boundingBox': {'vertices': [{'x': '727', 'y': '971'}, {'x': '727', 'y': '985'}, {'x': '795', 'y': '985'}, {'x': '795', 'y': '971'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '727', 'y': '971'}, {'x': '727', 'y': '985'}, {'x': '795', 'y': '985'}, {'x': '795', 'y': '971'}]}, 'text': 'Bank', 'words': [{'boundingBox': {'vertices': [{'x': '727', 'y': '969'}, {'x': '727', 'y': '988'}, {'x': '795', 'y': '988'}, {'x': '795', 'y': '969'}]}, 'text': 'Bank', 'entityIndex': '-1', 'textSegments': [{'startIndex': '218', 'length': '4'}]}], 'textSegments': [{'startIndex': '218', 'length': '4'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '218', 'length': '4'}]}, {'boundingBox': {'vertices': [{'x': '1136', 'y': '971'}, {'x': '1136', 'y': '985'}, {'x': '1337', 'y': '985'}, {'x': '1337', 'y': '971'}]}, 'lines': [{'boundingBox': {'vertices': [{'x': '1136', 'y': '971'}, {'x': '1136', 'y': '985'}, {'x': '1337', 'y': '985'}, {'x': '1337', 'y': '971'}]}, 'text': 'Time / Schedule', 'words': [{'boundingBox': {'vertices': [{'x': '1136', 'y': '969'}, {'x': '1136', 'y': '989'}, {'x': '1195', 'y': '989'}, {'x': '1195', 'y': '969'}]}, 'text': 'Time', 'entityIndex': '-1', 'textSegments': [{'startIndex': '223', 'length': '4'}]}, {'boundingBox': {'vertices': [{'x': '1206', 'y': '969'}, {'x': '1206', 'y': '988'}, {'x': '1217', 'y': '988'}, {'x': '1217', 'y': '969'}]}, 'text': '/', 'entityIndex': '-1', 'textSegments': [{'startIndex': '228', 'length': '1'}]}, {'boundingBox': {'vertices': [{'x': '1224', 'y': '968'}, {'x': '1224', 'y': '988'}, {'x': '1337', 'y': '988'}, {'x': '1337', 'y': '968'}]}, 'text': 'Schedule', 'entityIndex': '-1', 'textSegments': [{'startIndex': '230', 'length': '8'}]}], 'textSegments': [{'startIndex': '223', 'length': '15'}], 'orientation': 'ANGLE_0'}], 'languages': [{'languageCode': 'en'}], 'textSegments': [{'startIndex': '223', 'length': '15'}]}], 'entities': [], 'tables': [], 'fullText': 'Guests\nGuest\nBooking\nrequest\nGuest\nBooking\nconfirmation\nExternal\nReservation System\nBooking\nconfirmation\nBooking\nrequest\nBook Roob\nBookings\nBooking\nRooms\nRoom\nPayment\nvalidation\nPayment\nvalidation\nrequest\nCurrent\ntime\nBank\nTime / Schedule\n', 'rotate': 'ANGLE_0'}, 'page': '0'}}

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

    # def overlay_text(self, image: Image, text_positions: list, original_texts: list, translated_texts: list, font_sizes: list) -> None:
    #     """
    #     Overlay translated text onto the image.

    #     :param image: Image to draw text on.
    #     :param text_positions: List of positions to draw text at.
    #     :param original_texts: List of original texts (not used in the current implementation).
    #     :param translated_texts: List of translated texts to draw.
    #     :param font_sizes: List of font sizes to use for each text.
    #     """
    #     draw = ImageDraw.Draw(image)
    #     for (x, y, width, height), translated_text, font_size in zip(text_positions, translated_texts, font_sizes):
    #         font = ImageFont.truetype(self.font_path, font_size)
    #         draw.text((x, y), translated_text, font=font, fill="black")
    #         logger.debug(f"Applied translated text: '{translated_text}' at position ({x}, {y}) with font size {font_size}")

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

        # # Clean up extracted texts
        # cleaned_texts, cleaned_positions = self.cleanup_texts(extracted_texts, text_positions)

        # Filter duplicate texts
        # filtered_texts, filtered_positions = self.filter_duplicate_texts([(cleaned_texts, cleaned_positions)])

        # Translate texts (using the original for now)
        # translated_texts = self.translator.translate_texts(filtered_texts)  # Uncomment to use actual translation
        translated_texts = extracted_texts

        # Apply blur effect on the original image based on text positions
        # self.apply_blur(original_image, text_positions)

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

    document = Document.objects.get(pk=236)  # Replace with actual document ID
    yandex_translator = YandexImageTranslator(document)
    translated_image_path = yandex_translator.translate_image()
    print(f'Translated image saved at: {translated_image_path}')
