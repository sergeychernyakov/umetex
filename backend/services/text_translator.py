# src/services/text_translator.py

import re
import random
import logging
from typing import List, Optional, Dict
from openai import OpenAI
from backend.models.app_config import AppConfig
from backend.models.translation_phrase import TranslationPhrase
from backend.models.document import LANGUAGES
import ahocorasick

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TextTranslator:
    def __init__(self, translation_language: str = 'RU', temperature: int = 0, max_tokens: int = 4096, shorten_words: bool = False):
        """
        Initialize the TextTranslator with API key, temperature, and max tokens.

        :param translation_language: The target language for translation.
        :param temperature: Temperature for the OpenAI model.
        :param max_tokens: Max tokens for the OpenAI model.
        :param shorten_words: Whether to shorten the translated words if they are too long.
        """
        self.translation_language = translation_language
        self.source_language = None
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.prompt = self.get_prompt()
        self.api_key = self.get_api_key()
        self.model = self.get_model()
        self.shorten_words = shorten_words
        self.client = OpenAI(api_key=self.api_key)

    def get_model(self) -> str:
        try:
            return AppConfig.objects.get(key="openai_model").value
        except AppConfig.DoesNotExist:
            return "gpt-4o"  # Default value o1-preview and o1-mini

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
        If shorten_words is enabled, modify the prompt to request shorter translations.
        """
        try:
            raw_prompt = AppConfig.objects.get(key="text_translator_prompt").value
            # Replace placeholders with actual values
            return raw_prompt.format(translation_language=self.translation_language)
        except AppConfig.DoesNotExist:
            return f"You are a helpful assistant for translating documents into {self.translation_language}."

    def find_phrases_in_combined_text(self, texts: List[str]) -> Dict[str, Optional[str]]:
        """
        Find all phrases from TranslationPhrase in the combined text of shuffled_texts using Aho-Corasick algorithm.

        :param texts: List of shuffled text segments.
        :return: Dictionary of found phrases with their translations (if available).
        """
        # Приводим весь объединенный текст к нижнему регистру
        combined_text = " ".join(texts).lower()

        # Создаем автомат Aho-Corasick и заполняем его фразами
        automaton = ahocorasick.Automaton()
        phrases = TranslationPhrase.objects.filter(target_language=self.translation_language)

        # Добавляем фразы в автомат
        for phrase in phrases:
            lower_phrase = phrase.source_phrase.lower()
            automaton.add_word(lower_phrase, (lower_phrase, phrase.translated_phrase))
        
        # Создаем структуру автомата
        automaton.make_automaton()

        # Словарь для хранения найденных фраз и их переводов
        found_phrases = {}

        # Ищем все фразы в объединенном тексте
        for end_index, (found_phrase, translation) in automaton.iter(combined_text):
            # Проверяем, была ли фраза уже найдена, чтобы избежать дубликатов
            if found_phrase not in found_phrases:
                found_phrases[found_phrase] = translation
                # logger.debug(f"Found phrase in combined text: {found_phrase} -> {translation}")

        return found_phrases

    def translate_texts(self, texts: List[str]) -> List[Optional[str]]:
        """
        Translate an array of messages using the OpenAI API and extract translations
        based on predefined patterns.

        :param texts: List of text messages to translate.
        :return: List of extracted translation data.
        """
        # Regular expression to detect non-translatable segments (document numbers, section numbers)
        non_translatable_pattern = re.compile(r"^\s*[\d\-\/.:]+[\d\w\-\/.:]*\s*$")

        # Filter out non-translatable segments but keep their positions
        translatable_texts = []
        indices_mapping = []  # To map filtered texts back to their original position
        all_texts = [None] * len(texts)  # To store both translated and non-translated texts

        for i, text in enumerate(texts):
            predefined_translation = None
            if not self.shorten_words:
                predefined_translation = self.get_predefined_translation(text)
            # Check if text is translatable (not just numbers or document codes)
            if non_translatable_pattern.match(text):
                # If it's not translatable, add it directly to the results
                all_texts[i] = text
                logger.debug(f"Keeping non-translatable text segment as is: text_{i}: [{text}]")
            elif predefined_translation:
                # Apply original text format to predefined translation
                formatted_translation = self.apply_format(predefined_translation, text)
                all_texts[i] = formatted_translation
                logger.debug(f"Using predefined translation for text_{i}: [{text}] -> [{formatted_translation}]")
            else:
                translatable_texts.append(text)
                indices_mapping.append(i)

        # If there are no translatable texts left after checking predefined translations, return early
        if not translatable_texts:
            return all_texts

        # Shuffle the text segments to avoid order bias
        shuffled_indices = list(range(len(translatable_texts)))
        random.shuffle(shuffled_indices)
        shuffled_texts = [translatable_texts[i] for i in shuffled_indices]

        # Ищем все фразы из базы данных в объединенном тексте shuffled_texts
        found_phrases = self.find_phrases_in_combined_text(shuffled_texts)
        logger.debug(f"<<<<< Found phrases in combined text: {found_phrases}")

        # Create patterns for extracted data
        patterns = {
            f"text_{indices_mapping[i]}": rf"text_{indices_mapping[i]}: \[([^\]]*?)\]" 
            for i in shuffled_indices
        }

        # Enhanced prompt to guide the translation process
        message = (
            "The terminology used should correspond to the established practice of application in the relevant field of professional activity. "
            "The following is a list of text segments extracted from a medical document. "
            "Please determine the source language of the text first and include it in the format source_language: [{LANGUAGE_CODE}]. "
            "Translate each text segment into the target language, ensuring that each translation directly replaces the placeholder "
            "Please ensure that the translated text is concise and close to the length of the original text, "
            "maintaining the same capitalization (uppercase/lowercase) as in the original. "
            "and retains the same numbering format for consistency. Please only provide the translated text within the brackets.\n\n"
        )

        if self.shorten_words:
            message += "Important! If the translated word is significantly longer than the original word (2 times), shorten it using a hyphen. "
            message += "Example: Pyloric (original), Пилорический (translated), shortened: Пил-кий.\n"
            message += "If the translated word contains two or more words, shorten the first words with a period and the last one with a hyphen. "
            message += "Example: Cardia (original), Кардиальная полость (translated), shortened: Кард. п-ть.\n"
            message += "Example: INTERNAL STRUCTURE (original), ВНУТРЕННЯЯ СТРУКТУРА (translated), no need to shorten: ВНУТРЕННЯЯ СТРУКТУРА\n"

        # Добавляем найденные фразы в message
        if found_phrases:
            message += "Use those phrases for the translation:\n"
            for phrase, translation in found_phrases.items():
                message += f"{phrase}: [{translation}]\n"
            message += "\n"  # Разделитель между найденными фразами и основным текстом

        for i, text in zip(shuffled_indices, shuffled_texts):
            original_index = indices_mapping[i]
            message += f"text_{original_index}: [{text}]\n"
            logger.debug(f"Prepared shuffled text segment for translation: text_{original_index}: [{text}]")

        # Initialize the dictionary to hold the extracted data
        translated_text = self.translate_text(self.get_prompt(), message)
        logger.debug(f"Translated text received: {translated_text}")

        source_language_match = re.search(r'source_language:\s*\[\{?([A-Z-]+)\}?\]', translated_text)
        if source_language_match:
            detected_source_language = source_language_match.group(1)
            logger.debug(f"Detected source language: {detected_source_language}")

            # Matching the source language with LANGUAGES_CHOICES
            self.source_language = self.match_source_language(detected_source_language)
        else:
            logger.warning(f"Source language didn't match: {source_language_match}' not found")

        # Extract and filter matches for each pattern, and strip spaces from the strings
        for key, pattern in patterns.items():
            matches = re.findall(pattern, translated_text)
            logger.debug(f"Pattern for {key}: {pattern}, Matches found: {matches}")

            # Get the original index from the pattern key
            index = int(key.split('_')[1])
            non_empty_matches = [match.strip() for match in matches if match.strip()]
            if non_empty_matches:
                # Сохраняем переведённую фразу в базу
                translation = non_empty_matches[0]
                if not self.shorten_words:
                    # Save phrase if it has 2, 3, or 4 words
                    if 1 <= len(translation.split()) <= 7:
                        self.save_translated_phrase(texts[index], translation)
                        logger.debug(f"Translated text saved: [{texts[index]}] -> [{translation}]")
                all_texts[index] = translation
            else:
                logger.debug(f"No match found for text_{index}, keeping original text: {texts[index]}")
                all_texts[index] = texts[index]  # Fallback to original if translation is missing

        return all_texts

    def match_source_language(self, detected_language: str) -> Optional[str]:
        """
        Match the detected language from ChatGPT with LANGUAGES_CHOICES and return the code if found.

        :param detected_language: The language code detected by ChatGPT.
        :return: The matched language code or None if not found.
        """
        for code, name, encoding in LANGUAGES:
            if code == detected_language:
                return code
        logger.warning(f"Source language '{detected_language}' not found in LANGUAGES_CHOICES.")
        return None

    def save_translated_phrase(self, original: str, translated: str) -> None:
        """
        Save the original and translated phrase to the database if the translation is new,
        or update the translation if the phrase already exists without a translation.

        :param original: The original text phrase.
        :param translated: The translated text phrase.
        """
        # Try to find the phrase based on source_phrase and target_language
        phrase, created = TranslationPhrase.objects.get_or_create(
            source_phrase=original,
            target_language=self.translation_language,
        )

        # Check if the phrase was newly created or if it lacks a translation
        if created or phrase.translated_phrase is None:
            phrase.translated_phrase = translated
            phrase.source_language = self.source_language  # Assign the source language, if available
            phrase.save()
            logger.debug(f"Saved translated phrase to database: {original} -> {translated}")
        # If phrase exists but source_language is missing, update source_language
        elif phrase.source_language is None and self.source_language:
            phrase.source_language = self.source_language
            phrase.save()
            logger.debug(f"Updated source_language for phrase: {original}")
        else:
            logger.debug(f"Phrase '{original}' already translated as '{phrase.translated_phrase}', skipping save.")

    def get_predefined_translation(self, text: str) -> Optional[str]:
        """
        Retrieve predefined translation for a given text if available.

        :param text: The text to check for a predefined translation.
        :return: Predefined translation or None if not found.
        """
        try:
            phrase = TranslationPhrase.objects.get(
                target_language=self.translation_language,
                source_phrase=text
            )
            logger.debug(f"Predefined translation found: [{text}] -> [{phrase.translated_phrase}]")
            return phrase.translated_phrase
        except TranslationPhrase.DoesNotExist:
            logger.debug(f"No predefined translation found for: [{text}]")
            return None

    def is_title_case(self, text: str) -> bool:
        """
        Custom function to check if the text is in title case.
        It will ignore symbols and numbers at the beginning of the text.

        :param text: The text to check.
        :return: True if the text is in title case, ignoring the initial symbols and numbers.
        """
        # Регулярное выражение для нахождения первой текстовой части после символов и чисел
        pattern = re.compile(r'[A-Za-zА-Яа-я]+')

        # Находим первое текстовое слово после символов
        match = pattern.search(text)
        if match:
            # Проверяем, написано ли слово в формате заголовка
            word = match.group()
            return word[0].isupper() and word[1:].islower()
        return False

    def apply_format(self, translated_text: str, original_text: str) -> str:
        """
        Apply the format of the original text to the translated text.

        :param translated_text: The translated text to format.
        :param original_text: The original text to determine the format from.
        :return: Formatted translated text.
        """
        # Используем собственную функцию для проверки формата заголовка
        if self.is_title_case(original_text) and self.translation_language == 'RU':
            pattern = re.compile(r'^(\W*\d+[\w-]*\s*)+', re.UNICODE)
            match = pattern.match(translated_text)
            if match:
                matched_part = match.group()
                remaining_text = translated_text[len(matched_part):].strip()
                formatted_text = f"{matched_part}{remaining_text.capitalize()}"
                return formatted_text
            else:
                return translated_text.capitalize()
        elif original_text.istitle() and self.translation_language == 'RU':
            return translated_text.capitalize()

        return translated_text

    def translate_text(self, prompt: str, message: str) -> str:
        """
        Translate text using the OpenAI API.

        :param prompt: The ChatGPT prompt.
        :param message: The text to translate.
        :return: Translated text.
        """
        if len(prompt) == 0 or len(message) == 0:
            return ''

        print(f"Sending prompt to OpenAI API: {prompt}")
        print(f"Sending message to OpenAI API: {message}")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        translated_text = response.choices[0].message.content
        logger.debug(f"Received response from OpenAI API: {translated_text}")

        return translated_text

# Example usage
# python3 -m backend.services.text_translator
if __name__ == '__main__':
    # Example setup
    api_key = "your_openai_api_key"
    translator = TextTranslator(api_key)
    example_texts = ["Hello world!", "12345"]
    translated_texts = translator.translate_texts(example_texts, "Spanish")
    logger.debug(translated_texts)
