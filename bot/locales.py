import json
from pathlib import Path
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from functools import lru_cache
import os

logger = logging.getLogger(__name__)

class LocaleManager:
    def __init__(self, texts_dir: Path):
        self.texts: Dict[str, Dict[str, Any]] = {}
        self.texts_dir = Path(texts_dir)
        self.user_languages: Dict[str, str] = {}  # Cache для мов користувачів
        self.last_reload = datetime.now()
        self.reload_interval = timedelta(minutes=30)
        self.supported_languages = ['ua', 'ru', 'en']
        self.default_language = 'en'
        self.load_texts()

    def _ensure_texts_dir_exists(self) -> None:
        """Перевірка та створення директорії для текстів"""
        if not self.texts_dir.exists():
            os.makedirs(self.texts_dir, exist_ok=True)
            logger.info(f"Created texts directory: {self.texts_dir}")

    def load_texts(self) -> None:
        """Завантаження всіх текстів з файлів локалізації"""
        self._ensure_texts_dir_exists()
        
        for lang in self.supported_languages:
            file_path = self.texts_dir / f'{lang}.json'
            try:
                if not file_path.exists():
                    logger.warning(f"Localization file not found: {file_path}")
                    self.texts[lang] = self._get_fallback_texts()
                    continue

                with open(file_path, 'r', encoding='utf-8') as file:
                    loaded_texts = json.load(file)
                    # Перевіряємо наявність всіх необхідних ключів
                    self.texts[lang] = self._validate_and_fix_texts(loaded_texts, lang)
                logger.info(f"Successfully loaded {lang} localization")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding {lang} texts: {e}")
                self.texts[lang] = self._get_fallback_texts()
            except Exception as e:
                logger.error(f"Unexpected error loading {lang} texts: {e}")
                self.texts[lang] = self._get_fallback_texts()

    def _validate_and_fix_texts(self, loaded_texts: dict, lang: str) -> dict:
        """Перевірка та виправлення текстів"""
        required_keys = {
            "welcome", "spots_taken", "button", "stats_title",
            "tokens_label", "referrals_label", "earnings_label",
            "spots_left_label", "referral_link_label",
            "copy_link_button", "link_copied", "help_title",
            "help_start", "help_stats", "help_help",
            "help_additional", "help_tokens_info",
            "not_registered", "error_occurred"
        }
        
        fallback = self._get_fallback_texts()
        result = loaded_texts.copy()
        
        # Додаємо відсутні ключі з fallback
        for key in required_keys:
            if key not in result:
                logger.warning(f"Missing key '{key}' in {lang} localization, using fallback")
                result[key] = fallback[key]
        
        return result

    def _get_fallback_texts(self) -> dict:
        """Базові тексти для випадку помилки завантаження"""
        return {
            "welcome": "Welcome to DropHelper!",
            "spots_taken": "Unfortunately, all spots are taken.",
            "button": "Open DropHelper",
            "stats_title": "Your Statistics",
            "tokens_label": "Helper Tokens",
            "referrals_label": "Friends Invited",
            "earnings_label": "Earned from Referrals",
            "spots_left_label": "Spots Left",
            "referral_link_label": "Your Referral Link",
            "copy_link_button": "Copy Link",
            "link_copied": "Link copied!",
            "help_title": "Available Commands",
            "help_start": "Start using the bot",
            "help_stats": "View your statistics",
            "help_help": "Show this message",
            "help_additional": "Additional Information",
            "help_tokens_info": "Get tokens and invite friends",
            "not_registered": "You are not registered yet. Use /start command",
            "error_occurred": "An error occurred: {error}"
        }

    @lru_cache(maxsize=1000)
    def get_user_language(self, user_id: str, language_code: Optional[str]) -> str:
        """Визначення мови користувача з кешуванням"""
        # Перевіряємо кеш
        if user_id in self.user_languages:
            return self.user_languages[user_id]
        
        # Маппінг кодів мов Telegram до наших кодів
        lang_map = {
            'uk': 'ua',  # Ukrainian
            'ua': 'ua',  # Ukrainian
            'ru': 'ru',  # Russian
            'en': 'en',  # English
            'en-us': 'en',
            'en-gb': 'en',
            None: 'en'   # Default to English
        }
        
        # Нормалізуємо код мови
        if language_code:
            language_code = language_code.lower()
        
        # Визначаємо мову
        detected_lang = lang_map.get(language_code, self.default_language)
        
        # Зберігаємо в кеш
        self.user_languages[user_id] = detected_lang
        
        return detected_lang

    def get_text(self, key: str, user_id: str, language_code: Optional[str] = None, **kwargs) -> str:
        """Отримання тексту потрібною мовою з підтримкою форматування"""
        self._check_reload()
        
        # Отримуємо мову користувача
        lang = self.get_user_language(user_id, language_code)
        
        try:
            # Спочатку шукаємо в обраній мові
            if lang in self.texts and key in self.texts[lang]:
                text = self.texts[lang][key]
            # Якщо не знайдено, шукаємо в англійській
            elif key in self.texts[self.default_language]:
                logger.warning(f"Missing text for key '{key}' in language '{lang}', using English")
                text = self.texts[self.default_language][key]
            else:
                # Якщо і в англійській немає, повертаємо повідомлення про відсутній текст
                logger.error(f"Missing text for key '{key}' in all languages")
                return f"Missing text: {key}"
            
            # Застосовуємо форматування, якщо є параметри
            if kwargs:
                try:
                    return text.format(**kwargs)
                except KeyError as e:
                    logger.error(f"Format error for key '{key}': {e}")
                    return text
            return text
            
        except Exception as e:
            logger.error(f"Error getting text for key '{key}': {e}")
            return f"Error getting text: {key}"

    def _check_reload(self) -> None:
        """Перевірка необхідності перезавантаження текстів"""
        if datetime.now() - self.last_reload > self.reload_interval:
            self.load_texts()
            self.last_reload = datetime.now()

    def update_user_language(self, user_id: str, language: str) -> bool:
        """Оновлення мови користувача в кеші"""
        if language not in self.supported_languages:
            logger.warning(f"Attempted to set unsupported language: {language}")
            return False
            
        self.user_languages[user_id] = language
        self.get_user_language.cache_clear()
        return True

    def clear_cache(self) -> None:
        """Очищення всіх кешів"""
        self.user_languages.clear()
        self.get_user_language.cache_clear()
        logger.info("Locale cache cleared")

    def get_supported_languages(self) -> list:
        """Отримання списку підтримуваних мов"""
        return self.supported_languages.copy()

    def format_text(self, key: str, user_id: str, **kwargs) -> str:
        """Зручний метод для форматування тексту з параметрами"""
        return self.get_text(key, user_id, None, **kwargs)