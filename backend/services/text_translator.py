# src/services/text_translator.py

import re
import random
import logging
from typing import List, Optional
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

class TextTranslator:
    def __init__(self, translation_language: str = 'RU', temperature: int = 0, max_tokens: int = 4096):
        """
        Initialize the TextTranslator with API key, temperature, and max tokens.
        
        :param api_key: API key for OpenAI.
        :param temperature: Temperature for the OpenAI model.
        :param max_tokens: Max tokens for the OpenAI model.
        """
        self.translation_language = translation_language
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.temperature = temperature
        self.max_tokens = max_tokens

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
            # Check if text is translatable (not just numbers or document codes)
            if non_translatable_pattern.match(text):
                # If it's not translatable, add it directly to the results
                all_texts[i] = text
                logger.debug(f"Keeping non-translatable text segment as is: text_{i}: [{text}]")
            else:
                translatable_texts.append(text)
                indices_mapping.append(i)

        # Shuffle the text segments to avoid order bias
        shuffled_indices = list(range(len(translatable_texts)))
        random.shuffle(shuffled_indices)
        shuffled_texts = [translatable_texts[i] for i in shuffled_indices]

        # Create patterns for extracted data
        patterns = {
            f"text_{indices_mapping[i]}": rf"text_{indices_mapping[i]}: \[([^\]]*?)\]" 
            for i in shuffled_indices
        }

        # Enhanced prompt to guide the translation process
        prompt = f"You are a helpful assistant for translating documents into {self.translation_language}."
        message = (
            "The following is a list of text segments extracted from a medical document. "
            "Translate each text segment into the target language, ensuring that each translation directly replaces the placeholder "
            "and retains the same numbering format for consistency. Please only provide the translated text within the brackets.\n\n"
        )

        for i, text in zip(shuffled_indices, shuffled_texts):
            original_index = indices_mapping[i]
            message += f"text_{original_index}: [{text}]\n"
            logger.debug(f"Prepared shuffled text segment for translation: text_{original_index}: [{text}]")

        # Initialize the dictionary to hold the extracted data
        translated_text = self.translate_text(prompt, message)
        logger.debug(f"Translated text received: {translated_text}")

        # Extract and filter matches for each pattern, and strip spaces from the strings
        for key, pattern in patterns.items():
            matches = re.findall(pattern, translated_text)
            logger.debug(f"Pattern for {key}: {pattern}, Matches found: {matches}")

            # Get the original index from the pattern key
            index = int(key.split('_')[1])
            non_empty_matches = [match.strip() for match in matches if match.strip()]
            if non_empty_matches:
                all_texts[index] = non_empty_matches[0]
            else:
                print(f"No match found for text_{index}, keeping original text: {texts[index]}")
                all_texts[index] = texts[index]  # Fallback to original if translation is missing

        return all_texts

    def translate_text(self, prompt: str, message: str) -> str:
        """
        Translate text using the OpenAI API.

        :param prompt: The ChatGPT prompt.
        :param message: The text to translate.
        :return: Translated text.
        """
        if len(prompt) == 0 or len(message) == 0:
            return ''

        logger.debug(f"Sending prompt to OpenAI API: {prompt}")
        logger.debug(f"Sending message to OpenAI API: {message}")

        response = self.client.chat.completions.create(
            model="gpt-4o",
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
    print(translated_texts)
