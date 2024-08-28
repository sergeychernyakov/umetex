# src/services/image_translator.py

import os
import logging
import pytesseract
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from backend.services.text_translator import TextTranslator

# Set up logging
logger = logging.getLogger(__name__)

# Create a console handler and set the level to debug
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create a formatter and set it for the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(console_handler)

class ImageTranslator:
    def __init__(self, document):
        """
        Initialize the ImageTranslator with a Document instance.

        :param document: Document instance containing the original image and translation details.
        """
        self.document = document
        self.original_image_path = document.original_file.path
        file_extension = os.path.splitext(self.document.original_file.name)[1].lower()
        self.translated_image_name = f"translated_{document.pk}{file_extension}"
        self.translations_dir = os.path.join(settings.MEDIA_ROOT, str(document.pk), 'translations')
        os.makedirs(self.translations_dir, exist_ok=True)
        self.translated_image_path = os.path.join(self.translations_dir, self.translated_image_name)
        self.translator = TextTranslator(self.document.translation_language)
        self.font_path = os.path.join(settings.BASE_DIR, 'fonts', 'Arial Bold.ttf')  # Adjust font path as necessary

        logger.info(f"Initialized ImageTranslator for document ID: {document.pk}")

    def translate_image(self) -> str:
        """
        Process the image, extract text, translate it, and overlay the translated text.

        :return: Path to the translated image file.
        """
        self.document.update_progress(0, 1)  # don't remove that

        # Load the image
        try:
            original_image = Image.open(self.original_image_path)
            draw = ImageDraw.Draw(original_image)
            logger.info(f"Loaded image from path: {self.original_image_path}")
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            raise

        # Extract text and bounding boxes using OCR
        ocr_data = pytesseract.image_to_data(original_image, output_type=pytesseract.Output.DICT)
        logger.debug(f"OCR data extracted: {ocr_data}")

        extracted_texts = []
        text_positions = []

        # Collect texts and their positions
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            if text and text.isalnum():  # Only consider non-empty, alphanumeric text
                x, y, width, height = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                extracted_texts.append(text)
                text_positions.append((x, y, width, height))
                logger.debug(f"Extracted text: '{text}' at position ({x}, {y}, {width}, {height})")

        # Translate the extracted texts
        translated_texts = self.translator.translate_texts(extracted_texts)
        logger.info(f"Translated texts: {translated_texts}")

        # Apply translated text back to the image
        for (x, y, width, height), translated_text in zip(text_positions, translated_texts):
            # Draw a filled rectangle (white background) behind the text
            draw.rectangle([x, y, x + width, y + height], fill="white")
            draw.rectangle([x, y, x + width, y + height], outline="red", width=1)  # Optional: for debugging

            # Adjust the font size to fit the text within the original width
            font_size = max(10, int(height * 0.8))  # Start with a base font size
            font = ImageFont.truetype(self.font_path, font_size)
            text_bbox = draw.textbbox((0, 0), translated_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]

            # Decrease font size if translated text is too wide
            while text_width > width and font_size > 1:
                font_size -= 1
                font = ImageFont.truetype(self.font_path, font_size)
                text_bbox = draw.textbbox((0, 0), translated_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]

            # Check if further fine adjustment is needed
            while text_width < width and font_size < 100:
                font_size += 1
                font = ImageFont.truetype(self.font_path, font_size)
                text_bbox = draw.textbbox((0, 0), translated_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
            # Draw the translated text on top of the white background
            draw.text((x, y), translated_text, font=font, fill="black")
            logger.debug(f"Applied translated text: '{translated_text}' at position ({x}, {y}) with font size {font_size}")

        # Save the translated image
        try:
            original_image.save(self.translated_image_path)
            self.document.translated_file.name = f'{self.document.pk}/translations/{self.translated_image_name}'
            self.document.save()
            logger.info(f"Translated image saved at: {self.translated_image_path}")
        except Exception as e:
            logger.error(f"Failed to save translated image: {e}")
            raise

        self.document.update_progress(1, 1) # don't remove that
        return self.translated_image_path

# Example usage
# python3 -m backend.services.image_translator
if __name__ == '__main__':

    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'umetex_config.settings')
    django.setup()

    logger.setLevel(logging.DEBUG)  # Set the logging level to debug

    # Create a console handler and set the level to debug
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Create a formatter and set it for the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(console_handler)

    from backend.models import Document

    document = Document.objects.get(pk=236)  # Replace with actual document ID
    image_translator = ImageTranslator(document)
    translated_image_path = image_translator.translate_image()
    print(f'Translated image saved at: {translated_image_path}')
    
    