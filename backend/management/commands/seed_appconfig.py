# backend/management/commands/seed_appconfig.py

from django.core.management.base import BaseCommand
from backend.models.app_config import AppConfig
from django.conf import settings

class Command(BaseCommand):
    help = 'Seed database with initial configuration settings for AppConfig'

    def handle(self, *args, **kwargs):
        prompts = {
            "text_translator_prompt": "You are a helpful assistant for translating documents into {translation_language}.",
            "image_translator_with_openai_prompt": (
                f"You are a helpful assistant for translating medical images into {{translation_language}}. "
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
            ),
        }

        for key, value in prompts.items():
            config, created = AppConfig.objects.update_or_create(key=key, defaults={"value": value})
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created setting '{key}'"))
            else:
                self.stdout.write(self.style.WARNING(f"Updated setting '{key}'"))

        # Получить ключ API из настроек и добавить его в AppConfig
        openai_api_key = settings.OPENAI_API_KEY
        if openai_api_key:
            config, created = AppConfig.objects.update_or_create(key="openai_api_key", defaults={"value": openai_api_key})
            if created:
                self.stdout.write(self.style.SUCCESS("Created setting 'openai_api_key'"))
            else:
                self.stdout.write(self.style.WARNING("Updated setting 'openai_api_key'"))
        else:
            self.stdout.write(self.style.ERROR('OpenAI API Key not found in .env'))

        self.stdout.write(self.style.SUCCESS('Database seeding completed.'))

        # Добавление или обновление модели GPT
        model_name = "gpt-4o"  # Здесь можно изменить на нужное имя модели
        config, created = AppConfig.objects.update_or_create(key="openai_model", defaults={"value": model_name})
        if created:
            self.stdout.write(self.style.SUCCESS("Created setting 'openai_model'"))
        else:
            self.stdout.write(self.style.WARNING("Updated setting 'openai_model'"))

        self.stdout.write(self.style.SUCCESS('Database seeding completed.'))
