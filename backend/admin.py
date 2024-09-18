# backend/admin.py

from django.contrib import admin
from .models.document import Document
from .models.app_config import AppConfig
from .models.translation_phrase import TranslationPhrase  

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'translation_language', 'source_language', 'uploaded_at', 'original_file', 'translated_file')
    search_fields = ('title', 'translation_language', 'source_language')
    list_filter = ('translation_language', 'uploaded_at')

@admin.register(AppConfig)
class AppConfigAdmin(admin.ModelAdmin):
    list_display = ('key', 'value')  # Показывать ключ и значение в списке
    search_fields = ('key', 'value')  # Возможность поиска по ключу и значению
    list_editable = ('value',)        # Позволяет редактировать значения прямо из списка
    list_filter = ('key',)            # Фильтр по ключу для быстрого поиска

@admin.register(TranslationPhrase)
class TranslationPhraseAdmin(admin.ModelAdmin):
    list_display = ('source_language', 'target_language', 'source_phrase', 'translated_phrase')
    search_fields = ('source_phrase', 'translated_phrase')
    list_filter = ('source_language', 'target_language')
