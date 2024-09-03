# backend/models/document.py

import os
import shutil
import logging
import json
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Constants for text encoding types
TEXT_ENCODING_LATIN = 0
TEXT_ENCODING_GREEK = 1
TEXT_ENCODING_CYRILLIC = 2

# List of supported languages with their text encoding
LANGUAGES = [
    ('RU', 'Русский', TEXT_ENCODING_CYRILLIC),
    ('EN', 'Английский', TEXT_ENCODING_LATIN),
    ('ES', 'Испанский', TEXT_ENCODING_LATIN),
    ('IT', 'Итальянский', TEXT_ENCODING_LATIN),
    ('DE', 'Немецкий', TEXT_ENCODING_LATIN),
    ('FR', 'Французский', TEXT_ENCODING_LATIN),
    ('AR', 'Арабский', TEXT_ENCODING_LATIN),
    ('AZ', 'Азербайджанский', TEXT_ENCODING_LATIN),
    ('BE', 'Белорусский', TEXT_ENCODING_CYRILLIC),
    ('BN', 'Бенгальский', TEXT_ENCODING_LATIN),
    ('BS', 'Боснийский', TEXT_ENCODING_LATIN),
    ('PT-BR', 'Бразильский Португальский', TEXT_ENCODING_LATIN),
    ('BG', 'Болгарский', TEXT_ENCODING_CYRILLIC),
    ('YUE', 'Кантонский диалект (юэ)', TEXT_ENCODING_LATIN),
    ('CA', 'Каталонский', TEXT_ENCODING_LATIN),
    ('ZH', 'Китайский', TEXT_ENCODING_LATIN),
    ('HR', 'Хорватский', TEXT_ENCODING_LATIN),
    ('CS', 'Чешский', TEXT_ENCODING_LATIN),
    ('DA', 'Датский', TEXT_ENCODING_LATIN),
    ('NL', 'Голландский', TEXT_ENCODING_LATIN),
    ('ET', 'Эстонский', TEXT_ENCODING_LATIN),
    ('FI', 'Финский', TEXT_ENCODING_LATIN),
    ('EL', 'Греческий', TEXT_ENCODING_GREEK),
    ('GU', 'Гуджарати', TEXT_ENCODING_LATIN),
    ('HI', 'Хинди', TEXT_ENCODING_LATIN),
    ('HU', 'Венгерский', TEXT_ENCODING_LATIN),
    ('ID', 'Индонезийский', TEXT_ENCODING_LATIN),
    ('GA', 'Ирландский', TEXT_ENCODING_LATIN),
    ('JA', 'Японский', TEXT_ENCODING_LATIN),
    ('KZ', 'Казахский', TEXT_ENCODING_CYRILLIC),
    ('KO', 'Корейский', TEXT_ENCODING_LATIN),
    ('KY', 'Кыргызский', TEXT_ENCODING_CYRILLIC),
    ('LV', 'Латышский', TEXT_ENCODING_LATIN),
    ('LT', 'Литовский', TEXT_ENCODING_LATIN),
    ('MK', 'Македонский', TEXT_ENCODING_CYRILLIC),
    ('MS', 'Малайский', TEXT_ENCODING_LATIN),
    ('MT', 'Мальтийский', TEXT_ENCODING_LATIN),
    ('CMN', 'Мандарин', TEXT_ENCODING_LATIN),
    ('MR', 'Маратхи', TEXT_ENCODING_LATIN),
    ('MO', 'Молдавский', TEXT_ENCODING_CYRILLIC),
    ('MN', 'Монгольский', TEXT_ENCODING_LATIN),
    ('NE', 'Непальский', TEXT_ENCODING_LATIN),
    ('NO', 'Норвежский', TEXT_ENCODING_LATIN),
    ('PL', 'Польский', TEXT_ENCODING_LATIN),
    ('PT', 'Португальский', TEXT_ENCODING_LATIN),
    ('PA', 'Панджаби', TEXT_ENCODING_LATIN),
    ('RO', 'Румынский', TEXT_ENCODING_LATIN),
    ('SR', 'Сербский', TEXT_ENCODING_CYRILLIC),
    ('SK', 'Словацкий', TEXT_ENCODING_LATIN),
    ('SL', 'Словенский', TEXT_ENCODING_LATIN),
    ('SW', 'Суахили', TEXT_ENCODING_LATIN),
    ('SV', 'Шведский', TEXT_ENCODING_LATIN),
    ('TG', 'Таджикский', TEXT_ENCODING_CYRILLIC),
    ('TA', 'Тамильский', TEXT_ENCODING_LATIN),
    ('TT', 'Татарский', TEXT_ENCODING_CYRILLIC),
    ('TE', 'Телугу', TEXT_ENCODING_LATIN),
    ('TH', 'Тайский', TEXT_ENCODING_LATIN),
    ('TR', 'Турецкий', TEXT_ENCODING_LATIN),
    ('TK', 'Туркменский', TEXT_ENCODING_LATIN),
    ('UK', 'Украинcкий', TEXT_ENCODING_CYRILLIC),
    ('UR', 'Урду', TEXT_ENCODING_LATIN),
    ('UZ', 'Узбекский', TEXT_ENCODING_LATIN),
    ('VI', 'Вьетнамский', TEXT_ENCODING_LATIN),
]

class Document(models.Model):
    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"

    """
    Model to represent a document for translation. Stores original and translated files, along with language details.
    """
    # Choices for language selection, derived from LANGUAGES constant
    LANGUAGES_CHOICES = [(lang[0], lang[1]) for lang in LANGUAGES]

    title = models.CharField(max_length=255)  # Title of the document
    original_file = models.FileField(upload_to='tmp/originals/')  # Path to the original file
    translated_file = models.FileField(upload_to='tmp/translations/', blank=True, null=True)  # Path to the translated file
    translation_language = models.CharField(max_length=5, choices=LANGUAGES_CHOICES)  # Language to translate into
    uploaded_at = models.DateTimeField(auto_now_add=True)  # Timestamp of when the document was uploaded

    def save(self, *args, **kwargs):
        """
        Override the save method to handle file storage and renaming for both original and translated files.

        :param args: Positional arguments passed to the superclass save method.
        :param kwargs: Keyword arguments passed to the superclass save method.
        """
        # Ensure the instance has a primary key (ID) before processing
        if not self.pk:
            super().save(*args, **kwargs)  # Call the parent class's save to generate a primary key

        # Validate the file extension
        if self.file_extension not in settings.SUPPORTED_FILE_FORMATS:
            logger.error(f"Unsupported file type: {self.file_extension}")
            raise ValueError(f"Unsupported file type: {self.file_extension}")

        # Define new paths for original and translated files
        original_file_new_name = f'original_{self.pk}{self.file_extension}'
        original_file_new_path = f'{self.pk}/originals/{original_file_new_name}'
        translated_file_new_path = f'{self.pk}/translations/{os.path.basename(self.translated_file.name)}' if self.translated_file else None

        logger.debug(f"Original file new path: {original_file_new_path}")

        # Create directories for original and translated files if they don't exist
        original_dir = os.path.join(settings.MEDIA_ROOT, f'{self.pk}/originals/')
        translated_dir = os.path.join(settings.MEDIA_ROOT, f'{self.pk}/translations/')

        os.makedirs(original_dir, exist_ok=True)
        os.makedirs(translated_dir, exist_ok=True)

        # Move original file from temporary location to permanent location
        if self.original_file and self.original_file.name.startswith('tmp/originals/'):
            try:
                original_source_path = self.original_file.path
                original_destination_path = os.path.join(settings.MEDIA_ROOT, original_file_new_path)
                shutil.move(original_source_path, original_destination_path)
                self.original_file.name = original_file_new_path
                logger.debug(f"Moved original file to: {original_destination_path}")
            except Exception as e:
                logger.debug(f"Error moving original file: {e}")

        # Move translated file from temporary location to permanent location
        if self.translated_file and self.translated_file.name.startswith('tmp/translations/'):
            try:
                translated_source_path = self.translated_file.path
                translated_destination_path = os.path.join(settings.MEDIA_ROOT, translated_file_new_path)
                shutil.move(translated_source_path, translated_destination_path)
                self.translated_file.name = translated_file_new_path
                logger.debug(f"Moved translated file to: {translated_destination_path}")
            except Exception as e:
                logger.debug(f"Error moving translated file: {e}")

        # Call the parent class's save method to save the instance
        super().save(*args, **kwargs)

    def translate(self):
        """
        Perform translation on the document using either the PDFTranslator or ImageTranslator class,
        depending on the type of the original file.
        """
        if self.file_extension == '.pdf':
            from backend.services.pdf_translator import PDFTranslator

            # Use PDFTranslator for PDF files
            translator = PDFTranslator(self)
            translator.translate_pdf()
        elif self.file_extension in ['.jpg', '.jpeg', '.png']:
            # Use ImageTranslator for image files

            from backend.services.image_translator import ImageTranslator
            translator = ImageTranslator(self)

            # from backend.services.image_translator_with_openai import ImageTranslatorWithOpenAI
            # translator = ImageTranslatorWithOpenAI(self)
            translator.translate_image()
        else:
            logger.error(f"Unsupported file type for translation: {self.file_extension}")
            raise ValueError(f"Unsupported file type for translation: {self.file_extension}")

    def translate(self):
        """
        Perform translation on the document using either the PDFTranslator or ImageTranslator class,
        depending on the type of the original file.
        """
        try:
            if self.file_extension == '.pdf':
                from backend.services.pdf_translator import PDFTranslator

                translator = PDFTranslator(self)
                translator.translate_pdf()
            # elif self.file_extension in ['.jpg', '.jpeg', '.png']:
            #     from backend.services.yandex_image_translator import YandexImageTranslator
            #     translator = YandexImageTranslator(self)
            #     translator.translate_image()
            else:
                logger.error(f"Unsupported file type for translation: {self.file_extension}")
                raise ValueError(f"Unsupported file type for translation: {self.file_extension}")

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error during translation for document {self.pk}: {error_message}")
            # Update progress with error information
            self.update_progress(current_page=translator.current_page, total_pages=translator.total_pages, error=True, error_message=error_message)
            raise  # Re-raise the exception to stop the process

    def title_short(self) -> str:
        """
        Returns a truncated version of the title if it exceeds a certain length.
        
        :return: A short version of the title with an ellipsis if truncated.
        """
        max_length = 20
        ext_length = 7  # Length to keep from the end, including the extension
        if len(self.title) > max_length:
            start = self.title[:max_length - ext_length]
            end = self.title[-ext_length:]
            return f"{start}..{end}"
        return self.title

    @property
    def file_extension(self) -> str:
        """
        Get the file extension of the original file.
        
        :return: The file extension in lowercase (e.g., '.pdf', '.jpg').
        """
        return os.path.splitext(self.original_file.name)[1].lower()

    def update_progress(self, current_page: int, total_pages: int, error: bool = False, error_message: str = ""):
        """
        Update the progress of the translation, including handling errors.

        :param current_page: Current page number being translated.
        :param total_pages: Total number of pages in the document.
        :param error: Boolean indicating if an error occurred.
        :param error_message: Error message describing the issue.
        """
        progress_data = {
            "document_id": self.pk,
            "current_page": current_page,
            "total_pages": total_pages,
            "file_name": f'translated_{self.pk}{self.file_extension}'
        }

        # Include error information only if an error occurred
        if error:
            progress_data["error"] = True
            progress_data["error_message"] = error_message

        progress_file = os.path.join(settings.MEDIA_ROOT, f'{self.pk}', f'{self.pk}_progress.json')
        os.makedirs(os.path.dirname(progress_file), exist_ok=True)
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)

        logger.debug(f"Progress updated for document {self.pk}: {progress_data}")

# Signal handler to delete files from the filesystem when a Document instance is deleted
@receiver(post_delete, sender=Document)
def delete_files_on_document_delete(sender, instance, **kwargs):
    """
    Delete associated files from the filesystem when a Document instance is deleted.

    :param sender: The model class that sent the signal.
    :param instance: The instance of the model that was deleted.
    :param kwargs: Additional keyword arguments.
    """
    if instance.original_file:
        instance.original_file.delete(save=False)  # Delete the original file
    if instance.translated_file:
        instance.translated_file.delete(save=False)  # Delete the translated file
