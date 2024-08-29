# src/services/image_translator.py

import os
import logging
import pytesseract
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps
from django.conf import settings
from backend.services.text_translator import TextTranslator
import re
import itertools
from collections import defaultdict
import statistics

# Set up logging
logger = logging.getLogger(__name__)

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
        self.processed_image_name = f"processed_{document.pk}{file_extension}"
        self.translations_dir = os.path.join(settings.MEDIA_ROOT, str(document.pk), 'translations')
        os.makedirs(self.translations_dir, exist_ok=True)
        self.translated_image_path = os.path.join(self.translations_dir, self.translated_image_name)
        self.processed_image_path = os.path.join(self.translations_dir, self.processed_image_name)
        self.translator = TextTranslator(self.document.translation_language)
        self.font_path = os.path.join(settings.BASE_DIR, 'fonts', 'Arial Bold.ttf')

        logger.info(f"Initialized ImageTranslator for document ID: {document.pk}")

    def process_image(self, brightness: float = 1.0, contrast: float = 1.0, noise_filter_size: int = 3, threshold: int = 128) -> Image:
        """
        Process the image with specified parameters.

        :param brightness: Brightness enhancement factor.
        :param contrast: Contrast enhancement factor.
        :param noise_filter: Apply noise reduction if True.
        :param threshold: Threshold value for binary conversion.
        :return: Processed image.
        """
        try:
            original_image = Image.open(self.original_image_path).convert('RGB')
            processed_image = ImageOps.autocontrast(original_image)

            processed_image = processed_image.convert('L')

            # Enhance brightness
            processed_image = ImageEnhance.Brightness(processed_image).enhance(brightness)
            logger.debug(f"Brightness enhanced by a factor of {brightness}")

            # Enhance contrast
            processed_image = ImageEnhance.Contrast(processed_image).enhance(contrast)
            logger.debug(f"Contrast enhanced by a factor of {contrast}")

            # Apply noise reduction if specified
            if noise_filter_size > 0:
                processed_image = processed_image.filter(ImageFilter.MedianFilter(size=noise_filter_size))
                logger.debug("Noise reduction applied using MedianFilter")

            # Apply thresholding
            processed_image = processed_image.point(lambda p: p > threshold and 255)
            logger.debug(f"Thresholding applied with a value of {threshold}")

            # Save the processed image
            processed_image.save(self.processed_image_path)
            logger.info(f"Processed image saved at: {self.processed_image_path}")

            return processed_image
        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            raise

    def extract_text(self, image: Image, oem: int = 3, psm: int = 4) -> tuple[list, list]:
        """
        Extract text from the image using OCR.

        :param image: Image to perform OCR on.
        :param oem: OCR Engine Mode.
        :param psm: Page Segmentation Mode.
        :return: Tuple of extracted texts and their positions.
        """
        custom_config = f'--oem {oem} --psm {psm}'
        logger.debug(f"Using OCR config: {custom_config}")
        ocr_data = pytesseract.image_to_data(image, config=custom_config, lang='eng', output_type=pytesseract.Output.DICT)

        extracted_texts = []
        text_positions = []
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            if text:
                x, y, width, height = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                extracted_texts.append(text)
                text_positions.append((x, y, width, height))
                logger.debug(f"Extracted text: '{text}' at position ({x}, {y}, {width}, {height})")

        return extracted_texts, text_positions

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
            # Remove special characters and retain texts with at least 60% alphabetic characters
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
            blur_area = (max(x - blur_margin, 0), max(y - blur_margin, 0), min(x + width + blur_margin, image.width), min(y + height + blur_margin, image.height))
            text_area = image.crop(blur_area)
            blurred_area = text_area.filter(ImageFilter.GaussianBlur(radius=20))

            mask = Image.new('L', blurred_area.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, blurred_area.size[0], blurred_area.size[1]), fill=200)

            blurred_area_with_oval = Image.composite(blurred_area, text_area, mask)
            image.paste(blurred_area_with_oval, blur_area)

    def overlay_text(self, image: Image, text_positions: list, translated_texts: list) -> None:
        """
        Overlay translated text onto the image.

        :param image: Image to draw text on.
        :param text_positions: List of positions to draw text at.
        :param translated_texts: List of translated texts to draw.
        """
        draw = ImageDraw.Draw(image)
        for (x, y, width, height), translated_text in zip(text_positions, translated_texts):
            font_size = max(10, int(height * 0.8))
            font = ImageFont.truetype(self.font_path, font_size)
            text_bbox = draw.textbbox((0, 0), translated_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]

            while text_width > width and font_size > 1:
                font_size -= 1
                font = ImageFont.truetype(self.font_path, font_size)
                text_bbox = draw.textbbox((0, 0), translated_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]

            while text_width < width and font_size < 100:
                font_size += 1
                font = ImageFont.truetype(self.font_path, font_size)
                text_bbox = draw.textbbox((0, 0), translated_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]

            draw.text((x, y), translated_text, font=font, fill="black")
            logger.debug(f"Applied translated text: '{translated_text}' at position ({x}, {y}) with font size {font_size}")

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

    def is_overlapping_with_filtered(self, position: tuple, used_positions: set) -> bool:
        """
        Check if the given position overlaps significantly with already used positions.

        :param position: Position of the current text.
        :param used_positions: Set of positions that have already been used.
        :return: True if there is a significant overlap, False otherwise.
        """
        x, y, width, height = position
        for (ux, uy, uwidth, uheight) in used_positions:
            # Define overlap criteria (e.g., 50% overlap)
            if (ux < x + width and ux + uwidth > x and
                    uy < y + height and uy + uheight > y):
                return True
        return False

    def translate_image(self, debug = False) -> str:
        """
        Translate image by processing with specific parameter sets, extracting text, and overlaying translated text.

        :return: Path to the translated image file.
        """
        self.document.update_progress(0, 1)

        # Define specific parameter combinations to process
        parameter_combinations = [
            {'brightness': 1.2, 'contrast': 1.0, 'noise_filter_size': 3, 'threshold': 100, 'oem': 3, 'psm': 4},
            {'brightness': 1.5, 'contrast': 1.0, 'noise_filter_size': 3, 'threshold': 128, 'oem': 3, 'psm': 4},
            {'brightness': 1.2, 'contrast': 2.0, 'noise_filter_size': 3, 'threshold': 128, 'oem': 3, 'psm': 4},
        ]

        all_texts_positions = []

        # Iterate over the specific parameter combinations
        for params in parameter_combinations:
            # Process image with the current set of parameters
            processed_image = self.process_image(
                brightness=params['brightness'],
                contrast=params['contrast'],
                noise_filter_size=params['noise_filter_size'],
                threshold=params['threshold']
            )

            extracted_texts, text_positions = self.extract_text(processed_image, oem=params['oem'], psm=params['psm'])
            cleaned_texts, cleaned_positions = self.cleanup_texts(extracted_texts, text_positions)

            # Store results for later filtering
            all_texts_positions.append((cleaned_texts, cleaned_positions))

            if debug:
                # Load the original image in RGB for final overlay and saving
                original_image = Image.open(self.original_image_path).convert('RGB')

                # Apply blur and overlay text onto the original image
                self.apply_blur(original_image, cleaned_positions)
                self.overlay_text(original_image, cleaned_positions, cleaned_texts)

                # Construct filename with parameters
                params_filename = (
                    f"original_b{params['brightness']}_c{params['contrast']}_n{params['noise_filter_size']}_t{params['threshold']}_o{params['oem']}_p{params['psm']}.png"
                )
                params_image_path = os.path.join(self.translations_dir, params_filename)

                try:
                    # Save the original image with effects using parameters in the filename
                    original_image.save(params_image_path)
                    logger.info(f"Original image saved with parameters at: {params_image_path}")
                except Exception as e:
                    logger.error(f"Failed to save original image with parameters: {e}")
                    continue

        # Filter duplicate texts to keep only the most accurate ones
        filtered_texts, filtered_positions = self.filter_duplicate_texts(all_texts_positions)

        if debug:
            translated_texts = filtered_texts  # For now, using filtered texts directly
        else:
            translated_texts = self.translator.translate_texts(filtered_texts)  # Replace with actual translation logic

        # Load the original image in RGB for final overlay and saving
        final_original_image = Image.open(self.original_image_path).convert('RGB')

        # Apply blur and overlay text onto the original image
        self.apply_blur(final_original_image, filtered_positions)
        self.overlay_text(final_original_image, filtered_positions, translated_texts)

        try:
            final_original_image.save(self.translated_image_path)
            self.document.translated_file.name = f'{self.document.pk}/translations/{self.translated_image_name}'
            self.document.save()
            logger.info(f"Final translated image saved at: {self.translated_image_path}")
        except Exception as e:
            logger.error(f"Failed to save final translated image: {e}")
            raise

        self.document.update_progress(1, 1)
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
