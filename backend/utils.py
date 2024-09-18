import logging

# Set up logger
logger = logging.getLogger(__name__)

def shorten_long_word(original: str, translated: str, max_ratio: float = 1.5) -> str:
    """
    Shorten the translated word if its length significantly exceeds the length of the original word.
    Handles two-word translations by shortening both words with proper grammatical rules.

    :param original: Original word before translation.
    :param translated: Translated word.
    :param max_ratio: Maximum allowed ratio between the lengths of the translated and original words.
    :return: Shortened version of the translated word if necessary.
    """
    if len(translated) > len(original) * max_ratio:
        words = translated.split()

        if len(words) == 1:
            # If it's a single word, shorten by cutting and adding a hyphen
            midpoint = len(original) // 2
            shortened = f"{translated[:midpoint]}-{translated[-3:]}"
            logger.info(f"Shortened single translated word '{translated}' to '{shortened}'")
            return shortened
        
        elif len(words) == 2:
            # First word shortened with a dot
            first_word = words[0]
            first_shortened = f"{first_word[:min(5, len(first_word))]}."
            
            # Second word shortened with a hyphenation in the middle
            second_word = words[1]
            second_shortened = f"{second_word[0]}-{second_word[-3:]}"  # Example: "полость" -> "п-сть"
            
            shortened = f"{first_shortened} {second_shortened}"
            logger.info(f"Shortened two-word translation '{translated}' to '{shortened}'")
            return shortened

    return translated
