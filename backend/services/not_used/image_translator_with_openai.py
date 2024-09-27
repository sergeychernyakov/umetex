# src/services/image_translator_with_openai.py

import os
import logging
import base64
import json
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from openai import OpenAI
from backend.models.app_config import AppConfig

# Set up logging
logger = logging.getLogger(__name__)

class ImageTranslatorWithOpenAI:
    def __init__(self, document):
        """
        Initialize the ImageTranslatorWithOpenAI with a Document instance.

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
        self.font_path = os.path.join(settings.BASE_DIR, 'fonts', 'Arial Bold.ttf')
        self.translation_language = self.document.translation_language

        # Initialize OpenAI client with API key from Django settings
        self.prompt = self.get_prompt()
        self.api_key = self.get_api_key()
        self.model = self.get_model()
        self.client = OpenAI(api_key=self.api_key)

        logger.info(f"Initialized ImageTranslatorWithOpenAI for document ID: {document.pk}")

    def get_model(self) -> str:
        try:
            return AppConfig.objects.get(key="openai_model").value
        except AppConfig.DoesNotExist:
            return "gpt-4o"  # Default value

    def get_api_key(self) -> str:
        """
        Get the OpenAI API key from AppConfig.
        """
        try:
            return AppConfig.objects.get(key="openai_api_key").value
        except AppConfig.DoesNotExist:
            raise ValueError("OpenAI API key is not configured. Please set it in AppConfig.")

    def get_prompt(self) -> str:
        """
        Get the translation prompt for the TextTranslator, replacing placeholders with real values.
        """
        try:
            raw_prompt = AppConfig.objects.get(key="image_translator_with_openai_prompt").value
            # Replace placeholders with actual values
            return raw_prompt.format(translation_language=self.translation_language)
        except AppConfig.DoesNotExist:
            return (
            f"You are a helpful assistant for translating medical images into {self.translation_language}. "
            "Analyze the image and detect all text areas. For each text area, translate the text and provide the following details: "
            "the x and y coordinates of the top-left corner of the text box, the width and height of the text box, "
            "detect the font size (font-size) of the text area text, and the text color (text-color) and background color (text-background-color). "
            "Return the translated text in the following structured JSON format: "
            "{ 'translations': [{x: <x-coordinate>, y: <y-coordinate>, width: <box-width>, height: <box-height>, "
            "font_size: <font-size>, text_color: (<R>, <G>, <B>), text_background_color: (<R>, <G>, <B>), "
            "translated_text: '<translated text>'}], "
            "'image_size': {'width': <image-width>, 'height': <image-height>}}. "
            "Replace <x-coordinate>, <y-coordinate>, <box-width>, <box-height>, <font-size>, <text-color>, "
            "<text-background-color>, <translated text>, <image-width>, and <image-height> with actual values. "
            "Ensure colors are in the (R, G, B) format."
        )

    def encode_image(self, image_path: str) -> str:
        """
        Encode the image to base64 string.

        :param image_path: Path to the image file.
        :return: Base64-encoded string of the image.
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def parse_translated_text_data(self, text: str) -> tuple[list[dict], dict]:
        """
        Parse a JSON-formatted string into a list of dictionaries and image size.

        :param text: String representation of a JSON object containing translations and image size.
        :return: Tuple containing a list of dictionaries with parsed data and a dictionary for image size.
        """
        # Clean up the string to make sure it's valid JSON
        clean_text = text.strip().strip('```json').strip('```')

        try:
            # Use json.loads to parse the string
            parsed_data = json.loads(clean_text)
            logger.debug(f"Parsed data using json.loads: {parsed_data}")

            # Extract translations and image size
            translations = parsed_data.get('translations', [])
            image_size = parsed_data.get('image_size', {'width': None, 'height': None})

            return translations, [image_size['width'], image_size['height']]
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return [], {'width': None, 'height': None}

    def translate_image_with_openai(self, caption: str, file_path: str, temperature: int = 0, max_tokens: int = 4096) -> tuple[list[dict], dict]:
        """
        Use OpenAI API to recognize and translate text from the image using base64 encoding.

        :param caption: Caption or context for the image.
        :param file_path: Path to the image file.
        :return: Tuple containing a list of dictionaries with translated text data and a dictionary for image size.
        """
        try:
            base64_image = self.encode_image(file_path)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": caption},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "high"}}
                        ]
                    }
                ],
                max_tokens=max_tokens,  # Adjusted for potentially larger output
                temperature=temperature,
            )

            translated_data = response.choices[0].message.content
            logger.info(f"Text translated using OpenAI: {translated_data}")

            return self.parse_translated_text_data(translated_data)
        except Exception as e:
            error_message = f"Failed to translate text with OpenAI: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

    def overlay_text(self, image: Image, text_data: dict, original_size: tuple, final_size: tuple) -> None:
        """
        Overlay translated text onto the image if required keys are present, scaling coordinates based on the original and final image sizes.

        :param image: Image to draw text on.
        :param text_data: Dictionary containing text position and style information.
        :param original_size: Tuple of (width, height) for the original image size.
        :param final_size: Tuple of (width, height) for the final image size.
        """
        required_keys = {'x', 'y', 'width', 'height', 'translated_text'}
        
        # Log the content of text_data before checking required keys
        logger.debug(f"Text data received for overlay: {text_data}")
        
        # Check if all required keys are present
        if not required_keys.issubset(text_data):
            logger.warning("Skipping overlay: Missing one or more required keys in text_data.")
            return

        # Scale coordinates based on the original and final image sizes
        scale = (original_size[0] / final_size[0])
        logger.debug(f"Scale: scale: {scale}")

        # Scaling the coordinates
        x = text_data['x'] * scale
        y = text_data['y'] * scale
        font_size = text_data.get('font_size', 12) * (scale / 1.3)  # Scale font size proportionally
        
        # Retrieve colors, defaulting to black for text and light gray for background
        text_color = text_data.get('text_color', [0, 0, 0])  # Default to black
        text_background_color = text_data.get('text_background_color', [192, 192, 192])  # Default to light gray

        # Convert color lists to tuples and add alpha for transparency to the background color
        if isinstance(text_color, list):
            text_color = tuple(text_color)
        if isinstance(text_background_color, list):
            text_background_color = tuple(text_background_color)

        rectangle_color = text_background_color + (230,)  # Transparency

        translated_text = text_data['translated_text']

        # Load the font with scaled size
        font = ImageFont.truetype(self.font_path, int(font_size))

        # Measure the size of the text to adjust the rectangle size dynamically
        draw = ImageDraw.Draw(image, 'RGBA')
        text_bbox = draw.textbbox((0, 0), translated_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Adjust the rectangle size based on the text dimensions
        padding_horizontal = 40  # Increased padding for left and right
        padding_vertical = 40    # Increased padding for top and bottom
        rectangle_coords = [
            x, 
            y, 
            x + text_width + padding_horizontal, 
            y + text_height + padding_vertical
        ]

        # Draw the rectangle background for the text
        draw.rectangle(rectangle_coords, fill=rectangle_color)

        # Calculate the position to center the text within the specified rectangle
        text_x = x + (padding_horizontal / 2)  # Center padding for left
        text_y = y + (padding_vertical / 2)    # Center padding for top

        draw.text((text_x, text_y), translated_text, font=font, fill=text_color)
        logger.debug(f"Applied translated text: '{translated_text}' at position ({text_x}, {text_y}) with font size {font_size}")

    def translate_image(self, debug=False, max_retries=3) -> str:
        """
        Translate the image by recognizing text and overlaying translated text. Retries on failure up to max_retries times.

        :param debug: Debug flag to log additional information.
        :param max_retries: Maximum number of retries if the translation process fails.
        :return: Path to the translated image file.
        """
        self.document.update_progress(0, 1)

        # Get original image dimensions
        image = Image.open(self.original_image_path)
        original_size = image.size

        # Define the final image size (if different from original)
        final_size = original_size  # For now, we assume no scaling occurs

        # Update prompt with image size

        # Log the generated prompt
        logger.debug(f"Generated prompt: {self.get_prompt()}")

        attempt = 0
        while attempt < max_retries:
            try:
                # Use OpenAI to translate text and get image size
                translated_text_data, returned_image_size = self.translate_image_with_openai(self.get_prompt(), self.original_image_path)
                
                # Log the returned image size
                logger.debug(f"Returned image size from GPT: {returned_image_size}")

                # Check if any translations were successfully received
                if not translated_text_data:
                    logger.error("Translation failed, no text data received.")
                    raise ValueError("No translated text data received.")

                # Load the original image in RGB for final overlay
                final_original_image = Image.open(self.original_image_path).convert('RGB')

                # Overlay each translated text data on the image, passing original and final image sizes
                for text_data in translated_text_data:
                    self.overlay_text(final_original_image, text_data, original_size, returned_image_size)

                try:
                    final_original_image.save(self.translated_image_path)
                    self.document.translated_file.name = f'{self.document.pk}/translations/{self.translated_image_name}'
                    self.document.save()
                    logger.info(f"Final translated image saved at: {self.translated_image_path}")
                except Exception as e:
                    error_message = f"Failed to save final translated image: {e}"
                    logger.error(error_message)
                    raise Exception(error_message)

                self.document.update_progress(1, 1)
                return self.translated_image_path

            except Exception as e:
                attempt += 1
                logger.error(f"Attempt {attempt} failed: {e}")
                if attempt >= max_retries:
                    logger.error(f"All {max_retries} attempts failed. Aborting operation.")
                    raise e  # Re-raise the exception after exhausting all attempts

# Example usage
# python3 -m backend.services.image_translator_with_openai
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
    image_translator = ImageTranslatorWithOpenAI(document)
    translated_image_path = image_translator.translate_image()
