# backend/models/translation_phrase.py

from django.db import models
from backend.models import Document

class TranslationPhrase(models.Model):
    source_language = models.CharField(
        max_length=10,
        choices=Document.LANGUAGES_CHOICES,
        verbose_name="Исходный язык",
        blank=True,
        null=True
    )
    target_language = models.CharField(
        max_length=10,
        choices=Document.LANGUAGES_CHOICES,
        verbose_name="Целевой язык"
    )
    source_phrase = models.TextField(verbose_name="Фраза на исходном языке")
    translated_phrase = models.TextField(verbose_name="Фраза на целевом языке")

    class Meta:
        verbose_name = "Предопределённая фраза"
        verbose_name_plural = "Предопределённые фразы"
        unique_together = ('source_language', 'target_language', 'source_phrase')

    def __str__(self):
        return f"{self.source_phrase} -> {self.translated_phrase}"
