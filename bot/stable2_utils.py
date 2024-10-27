import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List, Set

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отримуємо абсолютний шлях до директорії проекту
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / 'data' / 'users.json'

# Константи
SUPPORTED_LANGUAGES = {'ua', 'ru', 'en'}
DEFAULT_LANGUAGE = 'en'
INITIAL_TOKENS = 5000
REFERRAL_BONUS = 1000

class DataValidationError(Exception):
    """Помилка валідації даних"""
    pass

def normalize_language_code(language_code: Optional[str]) -> str:
    """Нормалізація коду мови"""
    if not language_code:
        return DEFAULT_LANGUAGE
        
    lang_map = {
        'uk': 'ua',  # Ukrainian
        'ua': 'ua',
        'ru': 'ru',
        'en': 'en',
        'en-us': 'en',
        'en-gb': 'en'
    }
    
    normalized = lang_map.get(language_code.lower(), DEFAULT_LANGUAGE)
    if normalized not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language code: {language_code}, using {DEFAULT_LANGUAGE}")
        return DEFAULT_LANGUAGE
    
    return normalized

def load_data() -> Dict:
    """Завантаження даних з JSON файлу"""
    try:
        # Перевіряємо наявність директорії та файлу
        if not DATA_FILE.parent.exists():
            DATA_FILE.parent.mkdir(parents=True)
            logger.info(f"Created directory: {DATA_FILE.parent}")

        if not DATA_FILE.exists():
            initial_data = {
                "users": {},
                "total_spots": 10000,
                "used_spots": 0,
                "referral_codes": {},
                "statistics": {
                    "total_bot_users": 0,
                    "webapp_opens": 0,
                    "languages": {},
                    "countries": {}
                },
                "counted_users": [],
                "webapp_users": []
            }
            save_data(initial_data)
            logger.info(f"Created initial data file: {DATA_FILE}")
            return initial_data

        with open(DATA_FILE, 'r', encoding='utf-8') as file:
            data = json.load(file)
            validate_data_structure(data)
            return data

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {DATA_FILE}: {e}")
        raise DataValidationError("Invalid JSON format in data file")
    except Exception as e:
        logger.error(f"Unexpected error loading data: {e}")
        raise

def validate_data_structure(data: Dict) -> None:
    """Валідація структури даних"""
    required_keys = {
        "users", "total_spots", "used_spots", "referral_codes",
        "statistics", "counted_users", "webapp_users"
    }
    
    if not all(key in data for key in required_keys):
        missing_keys = required_keys - set(data.keys())
        raise DataValidationError(f"Missing required keys in data structure: {missing_keys}")
    
    if not isinstance(data["statistics"], dict):
        raise DataValidationError("Invalid statistics structure")
    
    required_stats = {"total_bot_users", "webapp_opens", "languages", "countries"}
    if not all(key in data["statistics"] for key in required_stats):
        raise DataValidationError("Invalid statistics structure")

def save_data(data: Dict) -> None:
    """Збереження даних в JSON файл"""
    try:
        validate_data_structure(data)
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        logger.debug("Data successfully saved")
    except Exception as e:
        logger.error(f"Error saving data: {e}")
        raise

def update_statistics(user_id: int, action: str, data: Optional[Dict] = None) -> bool:
    """Оновлення статистики"""
    try:
        json_data = load_data()
        user_id_str = str(user_id)
        
        if "statistics" not in json_data:
            json_data["statistics"] = {
                "total_bot_users": 0,
                "webapp_opens": 0,
                "languages": {},
                "countries": {}
            }
        
        if action == 'bot_start':
            if user_id_str not in json_data.get("counted_users", []):
                json_data["statistics"]["total_bot_users"] += 1
                json_data.setdefault("counted_users", []).append(user_id_str)
                
                if data and 'language' in data:
                    language = normalize_language_code(data['language'])
                    json_data["statistics"]["languages"][language] = \
                        json_data["statistics"]["languages"].get(language, 0) + 1
                
                if data and 'country' in data:
                    country = (data['country'] or 'unknown').upper()
                    json_data["statistics"]["countries"][country] = \
                        json_data["statistics"]["countries"].get(country, 0) + 1
                
                logger.info(f"Updated statistics for new user {user_id}")
                
        elif action == 'webapp_open':
            if user_id_str in json_data.get("counted_users", []) and \
               user_id_str not in json_data.get("webapp_users", []):
                json_data["statistics"]["webapp_opens"] += 1
                json_data.setdefault("webapp_users", []).append(user_id_str)
                logger.info(f"Updated statistics for first webapp open by user {user_id}")
        
        save_data(json_data)
        return True
    except Exception as e:
        logger.error(f"Error updating statistics: {e}")
        return False

def clear_statistics() -> Tuple[bool, str]:
    """Очищення статистики"""
    try:
        data = load_data()
        data["statistics"] = {
            "total_bot_users": 0,
            "webapp_opens": 0,
            "languages": {},
            "countries": {}
        }
        data["counted_users"] = []
        data["webapp_users"] = []
        
        save_data(data)
        logger.info("Statistics cleared successfully")
        return True, "Статистику успішно очищено"
    except Exception as e:
        logger.error(f"Error clearing statistics: {e}")
        return False, str(e)

def get_statistics() -> Optional[Dict[str, Any]]:
    """Отримання загальної статистики"""
    try:
        data = load_data()
        stats = data.get("statistics", {})
        
        total_users = stats.get("total_bot_users", 0)
        webapp_opens = stats.get("webapp_opens", 0)
        conversion = (webapp_opens / total_users * 100) if total_users > 0 else 0
        
        return {
            "total_users": total_users,
            "webapp_opens": webapp_opens,
            "conversion": round(conversion, 2),
            "languages": stats.get("languages", {}),
            "countries": stats.get("countries", {}),
            "spots_left": data["total_spots"] - data["used_spots"]
        }
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return None

def register_user(user_id: int, username: str, language_code: str, 
                 referral_code: Optional[str] = None) -> Tuple[bool, str]:
    """Реєстрація нового користувача"""
    try:
        data = load_data()
        user_id_str = str(user_id)
        
        if user_id_str in data["users"]:
            return False, "Already registered"
        
        if data["used_spots"] >= data["total_spots"]:
            return False, "No spots left"
        
        normalized_lang = normalize_language_code(language_code)
        ref_code = generate_referral_code(user_id)
        
        data["users"][user_id_str] = {
            "username": username,
            "language": normalized_lang,
            "tokens": INITIAL_TOKENS,
            "referral_code": ref_code,
            "referred_by": None,
            "referrals": [],
            "join_date": datetime.now().isoformat()
        }
        data["referral_codes"][ref_code] = user_id_str
        data["used_spots"] += 1
        
        save_data(data)
        
        if referral_code:
            logger.info(f"Processing referral code {referral_code} for user {user_id}")
            success, message = add_referral(user_id, referral_code)
            if success:
                logger.info(f"Successfully processed referral for user {user_id}")
                data = load_data()
                save_data(data)
            else:
                logger.warning(f"Failed to process referral for user {user_id}: {message}")
        
        return True, "Success"
        
    except Exception as e:
        logger.error(f"Error in register_user: {e}")
        return False, str(e)

def add_referral(user_id: int, referral_code: str) -> Tuple[bool, str]:
    """Додавання реферала"""
    try:
        data = load_data()
        user_id_str = str(user_id)
        
        if referral_code not in data["referral_codes"]:
            return False, "Invalid referral code"
        
        referrer_id = data["referral_codes"][referral_code]
        
        if user_id_str == referrer_id:
            return False, "Cannot use own referral code"
        
        if data["users"][user_id_str]["referred_by"]:
            return False, "Already used a referral code"
        
        if user_id_str not in data["users"][referrer_id]["referrals"]:
            data["users"][referrer_id]["referrals"].append(user_id_str)
            data["users"][referrer_id]["tokens"] += REFERRAL_BONUS
            data["users"][user_id_str]["referred_by"] = referrer_id
            save_data(data)
            logger.info(f"Successfully added referral: {user_id} -> {referrer_id}")
            return True, "Success"
        
        return False, "Already referred"
        
    except Exception as e:
        logger.error(f"Error in add_referral: {e}")
        return False, str(e)

def delete_user(user_id: int) -> Tuple[bool, str]:
    """Видалення користувача"""
    try:
        data = load_data()
        user_id_str = str(user_id)
        
        if user_id_str not in data["users"]:
            return False, "Користувача не знайдено"
        
        user_data = data["users"][user_id_str]
        ref_code = user_data["referral_code"]
        
        # Видаляємо реферальний код
        if ref_code in data["referral_codes"]:
            del data["referral_codes"][ref_code]
        
        # Обробляємо реферальні зв'язки
        if user_data["referred_by"]:
            referrer = data["users"][user_data["referred_by"]]
            if user_id_str in referrer["referrals"]:
                referrer["referrals"].remove(user_id_str)
                referrer["tokens"] -= REFERRAL_BONUS
        
        # Обробляємо рефералів користувача
        for referral_id in user_data.get("referrals", []):
            if referral_id in data["users"]:
                data["users"][referral_id]["referred_by"] = None
        
        # Оновлюємо статистику
        if user_id_str in data["counted_users"]:
            data["counted_users"].remove(user_id_str)
            
        if user_id_str in data["webapp_users"]:
            data["webapp_users"].remove(user_id_str)
        
        language = user_data["language"]
        if language in data["statistics"]["languages"]:
            data["statistics"]["languages"][language] -= 1
            if data["statistics"]["languages"][language] <= 0:
                del data["statistics"]["languages"][language]
        
        data["used_spots"] -= 1
        del data["users"][user_id_str]
        
        save_data(data)
        logger.info(f"Successfully deleted user {user_id}")
        return True, f"Користувача {user_id} успішно видалено"
        
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        return False, str(e)

def get_spots_left() -> int:
    """Отримання кількості вільних місць"""
    data = load_data()
    return data["total_spots"] - data["used_spots"]

def get_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Отримання даних користувача"""
    try:
        data = load_data()
        return data["users"].get(str(user_id))
    except Exception as e:
        logger.error(f"Error getting user data: {e}")
        return None

def get_user_stats(user_id: int) -> Optional[Dict[str, Any]]:
    """Отримання статистики користувача"""
    user_data = get_user_data(user_id)
    if not user_data:
        return None
    
    referrals_count = len(user_data.get('referrals', []))
    return {
        'tokens': user_data['tokens'],
        'referrals_count': referrals_count,
        'referral_earnings': referrals_count * REFERRAL_BONUS,
        'referral_code': user_data['referral_code'],
        'username': user_data['username'],
        'language': user_data['language']
    }

def generate_referral_code(user_id: int) -> str:
    """Генерація реферального коду"""
    return f"REF{user_id}"

def generate_referral_link(user_id: int) -> Optional[str]:
    """Генерація реферального посилання"""
    user_data = get_user_data(user_id)
    if not user_data:
        return None
    return f"https://t.me/AI_DropHelper_bot?start={user_data['referral_code']}"