# src/services/font_manager.py

import os
import re
import logging
from fontTools.ttLib import TTFont
from typing import Dict
from django.conf import settings
from backend.models.document import LANGUAGES, TEXT_ENCODING_CYRILLIC

logger = logging.getLogger(__name__)

class FontManager:
    cyrillic_support_cache: Dict[str, bool] = {}

    def __init__(self, translation_language: str = 'RU'):
        """
        Initialize the FontManager with the directory of fonts.
        """
        self.fonts_dir = os.path.join(settings.BASE_DIR, 'fonts')
        self.translation_language = translation_language

    def clean_font_name(self, fontname: str) -> str:
        """
        Clean up font name to ensure it is valid for use in PyMuPDF's insert_font method.

        :param fontname: Original font name from the PDF.
        :return: Cleaned font name suitable for PyMuPDF.
        """
        # Replace spaces and special characters with underscores
        cleaned_fontname = re.sub(r'[^A-Za-z0-9]', '_', fontname)
        return cleaned_fontname

    def find_font_path(self, fontname: str) -> str:
        """
        Find the appropriate font file based on the provided font name by searching through available font files.
        
        :param fontname: The name of the font to find.
        :return: Path to the font file if found, else default to Arial.
        """
        logger.debug(f"Searching for font: {fontname}")

        # Normalize the font name by removing common suffixes, spaces, and converting to lowercase
        normalized_fontname = re.sub(r'(MT|PSMT|[-\s]+)', '', fontname).lower()

        best_match = None
        best_match_score = 0
        style_penalty = {
            "bold": 2,
            "italic": 2,
            "bolditalic": 3
        }
        match_threshold = 1  # Minimum score to consider a font a good match

        # Получаем список всех языков, поддерживающих кириллицу
        cyrillic_languages = [lang[0] for lang in LANGUAGES if lang[2] == TEXT_ENCODING_CYRILLIC]

        for root, _, files in os.walk(self.fonts_dir):
            for file in files:
                # Normalize the filename similarly to match against fontname
                normalized_filename = re.sub(r'[-\s]+', '', file).lower().replace('.ttf', '').replace('.ttc', '').replace('.otf', '')

                # Calculate match score based on name similarity
                match_score = sum(part in normalized_filename for part in normalized_fontname.split('_'))

                # Add penalties if the styles (bold/italic) do not match
                if "bold" in normalized_fontname and "bold" not in normalized_filename:
                    match_score -= style_penalty["bold"]
                if "italic" in normalized_fontname and "italic" not in normalized_filename:
                    match_score -= style_penalty["italic"]
                if "bold" not in normalized_fontname and "bold" in normalized_filename:
                    match_score -= style_penalty["bold"]
                if "italic" not in normalized_fontname and "italic" in normalized_filename:
                    match_score -= style_penalty["italic"]

                # Update best match if this file has a better score
                if match_score > best_match_score:
                    best_match = os.path.join(root, file)
                    best_match_score = match_score

            if best_match and best_match_score >= match_threshold:
                # Check for the cyrillic support
                if self.translation_language in cyrillic_languages and not self.supports_cyrillic(best_match):
                    logger.debug(f"Font '{fontname}' does not support Cyrillic. Using Arial as default.")
                    return os.path.join(self.fonts_dir, 'Arial.ttf')
                else:
                    logger.debug(f"Best match found: {os.path.basename(best_match)} with score: {best_match_score}")
                    break

        # Use Arial if no match is found or if the best match score is below the threshold
        if not best_match or best_match_score < match_threshold:
            logger.error(f"Font '{fontname}' not found or match is too weak. Using Arial as default.")
            return os.path.join(self.fonts_dir, 'Arial.ttf')

        return best_match

    def supports_cyrillic(self, font_path: str) -> bool:
        """
        Check if a font supports Cyrillic characters.
        
        :param font_path: Path to the font file.
        :return: True if Cyrillic is supported, else False.
        """
        if font_path in self.cyrillic_support_cache:
            return self.cyrillic_support_cache[font_path]
        try:
            font = TTFont(font_path)
            cyrillic_range = range(0x0400, 0x0500)
            for table in font['cmap'].tables:
                if any(ord_char in cyrillic_range for ord_char in table.cmap.keys()):
                    self.cyrillic_support_cache[font_path] = True
                    return True
        except Exception as e:
            logger.error(f"Error checking Cyrillic support for {font_path}: {e}")
        self.cyrillic_support_cache[font_path] = False
        return False

# Example usage
# python3 -m src.services.font_manager
if __name__ == '__main__':
    font_manager = FontManager('/path/to/fonts')
    print(font_manager.clean_font_name('Arial Bold'))
    print(font_manager.find_font_path('Arial'))
    print(font_manager.supports_cyrillic('/path/to/arial.ttf'))
