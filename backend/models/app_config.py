# backend/models/app_config.py

from django.db import models

class AppConfig(models.Model):
    """
    Model to store configuration settings for the application, including prompts for translators.
    """
    key = models.CharField(max_length=100, unique=True)  # Key for setting (e.g., "image_translator_prompt")
    value = models.TextField()  # Value for setting, supporting longer text for prompts

    class Meta:
        verbose_name = "Настройка"
        verbose_name_plural = "Настройки"

    def __str__(self):
        return f"{self.key}: {self.value[:50]}..."  # Display the first 50 characters for brevity
