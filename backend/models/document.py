# backend/models/document.py

import os
import shutil
import logging
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


logger = logging.getLogger(__name__)

TEXT_ENCODING_LATIN = 0
TEXT_ENCODING_GREEK = 1
TEXT_ENCODING_CYRILLIC = 2

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
    # Копия списка LANGUAGES для использования в поле translation_language (только 2 элемента в каждом кортеже)
    LANGUAGES_CHOICES = [(lang[0], lang[1]) for lang in LANGUAGES]

    title = models.CharField(max_length=255)
    original_file = models.FileField(upload_to='tmp/originals/')
    translated_file = models.FileField(upload_to='tmp/translations/', blank=True, null=True)
    translation_language = models.CharField(max_length=5, choices=LANGUAGES_CHOICES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)  # Save to generate a primary key

        original_file_new_name = f'original_{self.pk}.pdf'
        original_file_new_path = f'{self.pk}/originals/{original_file_new_name}'
        translated_file_new_path = f'{self.pk}/translations/{os.path.basename(self.translated_file.name)}' if self.translated_file else None

        print(f"Original file new path: {original_file_new_path}")
        print(f"Translated file new path: {translated_file_new_path}")

        original_dir = os.path.join(settings.MEDIA_ROOT, f'{self.pk}/originals/')
        translated_dir = os.path.join(settings.MEDIA_ROOT, f'{self.pk}/translations/')

        os.makedirs(original_dir, exist_ok=True)
        os.makedirs(translated_dir, exist_ok=True)

        if self.original_file and self.original_file.name.startswith('tmp/originals/'):
            try:
                original_source_path = self.original_file.path
                original_destination_path = os.path.join(settings.MEDIA_ROOT, original_file_new_path)
                shutil.move(original_source_path, original_destination_path)
                self.original_file.name = original_file_new_path
                logger.debug(f"Moved original file to: {original_destination_path}")
            except Exception as e:
                logger.debug(f"Error moving original file: {e}")

        if self.translated_file and self.translated_file.name.startswith('tmp/translations/'):
            try:
                translated_source_path = self.translated_file.path
                translated_destination_path = os.path.join(settings.MEDIA_ROOT, translated_file_new_path)
                shutil.move(translated_source_path, translated_destination_path)
                self.translated_file.name = translated_file_new_path
                logger.debug(f"Moved translated file to: {translated_destination_path}")
            except Exception as e:
                logger.debug(f"Error moving translated file: {e}")

        super().save(*args, **kwargs)

    def translate(self):
        """
        Translate the document using the PDFTranslator class and update the translated_file field.
        """
        from backend.services import PDFTranslator

        translator = PDFTranslator(self)
        translator.translate_pdf()  # Perform the translation and get the file name

    # def translate(self):
    #     from fpdf import FPDF

    #     document_dir = os.path.join(settings.MEDIA_ROOT, str(self.pk))
    #     translations_dir = os.path.join(document_dir, 'translations')
    #     os.makedirs(translations_dir, exist_ok=True)

    #     translated_file_name = f"translated_{self.pk}.pdf"
    #     translated_file_path = os.path.join(translations_dir, translated_file_name)

    #     pdf = FPDF()
    #     pdf.add_page()
    #     pdf.set_font("Arial", size=12)
    #     pdf.cell(200, 10, txt=f"Translated: {self.title}", ln=True, align='C')
    #     pdf.output(translated_file_path)

    #     self.translated_file.name = f'{self.pk}/translations/{translated_file_name}'
    #     self.save()

@receiver(post_delete, sender=Document)
def delete_files_on_document_delete(sender, instance, **kwargs):
    if instance.original_file:
        instance.original_file.delete(save=False)
    if instance.translated_file:
        instance.translated_file.delete(save=False)
