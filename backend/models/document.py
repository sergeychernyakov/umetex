# backend/models/document.py

import os
import shutil
import logging
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


logger = logging.getLogger(__name__)

class Document(models.Model):
    LANGUAGES = [
        ('RU', 'Русский'),
        ('EN', 'Английский'),
        ('ES', 'Испанский'),
        ('IT', 'Итальянский'),
        ('DE', 'Немецкий'),
        ('FR', 'Французский'),
        ('AR', 'Арабский'),
        ('AZ', 'Азербайджанский'),
        ('BE', 'Белорусский'),
        ('BN', 'Бенгальский'),
        ('BS', 'Боснийский'),
        ('PT-BR', 'Бразильский Португальский'),
        ('BG', 'Болгарский'),
        ('YUE', 'Кантонский диалект (юэ)'),
        ('CA', 'Каталонский'),
        ('ZH', 'Китайский'),
        ('HR', 'Хорватский'),
        ('CS', 'Чешский'),
        ('DA', 'Датский'),
        ('NL', 'Голландский'),
        ('ET', 'Эстонский'),
        ('FI', 'Финский'),
        ('EL', 'Греческий'),
        ('GU', 'Гуджарати'),
        ('HI', 'Хинди'),
        ('HU', 'Венгерский'),
        ('ID', 'Индонезийский'),
        ('GA', 'Ирландский'),
        ('JA', 'Японский'),
        ('KZ', 'Казахский'),
        ('KO', 'Корейский'),
        ('KY', 'Кыргызский'),
        ('LV', 'Латышский'),
        ('LT', 'Литовский'),
        ('MK', 'Македонский'),
        ('MS', 'Малайский'),
        ('MT', 'Мальтийский'),
        ('CMN', 'Мандарин'),
        ('MR', 'Маратхи'),
        ('MO', 'Молдавский'),
        ('MN', 'Монгольский'),
        ('NE', 'Непальский'),
        ('NO', 'Норвежский'),
        ('PL', 'Польский'),
        ('PT', 'Португальский'),
        ('PA', 'Панджаби'),
        ('RO', 'Румынский'),
        ('SR', 'Сербский'),
        ('SK', 'Словацкий'),
        ('SL', 'Словенский'),
        ('SW', 'Суахили'),
        ('SV', 'Шведский'),
        ('TG', 'Таджикский'),
        ('TA', 'Тамильский'),
        ('TT', 'Татарский'),
        ('TE', 'Телугу'),
        ('TH', 'Тайский'),
        ('TR', 'Турецкий'),
        ('TK', 'Туркменский'),
        ('UK', 'Украинcкий'),
        ('UR', 'Урду'),
        ('UZ', 'Узбекский'),
        ('VI', 'Вьетнамский'),
    ]

    title = models.CharField(max_length=255)
    original_file = models.FileField(upload_to='tmp/originals/')
    translated_file = models.FileField(upload_to='tmp/translations/', blank=True, null=True)
    translation_language = models.CharField(max_length=5, choices=LANGUAGES)
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
