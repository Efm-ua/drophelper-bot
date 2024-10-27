import json
import logging
import os
from datetime import datetime
from pathlib import Path

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отримуємо абсолютний шлях до директорії проекту
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / 'data' / 'users.json'

def load_data():
    """Завантаження даних з JSON файлу"""
    if not DATA_FILE.parent.exists():
        DATA_FILE.parent.mkdir(parents=True)
    if not DATA_FILE.exists():
        initial_data = {
            "users": {},
            "total_spots": 10000,  # Змінено з 1000 на 10000
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
        return initial_data

def save_data(data):
    """Збереження даних в JSON файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def clear_statistics():
    """Очищення статистики без видалення користувачів"""
    try:
        data = load_data()
        
        # Очищуємо статистику
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
        return False, f"Помилка: {str(e)}"

def delete_user(user_id):
    """Видалення користувача з системи"""
    try:
        data = load_data()
        user_id_str = str(user_id)
        
        # Перевіряємо чи існує користувач
        if user_id_str not in data["users"]:
            return False, "Користувача не знайдено"
        
        # Зберігаємо дані для логу
        user_data = data["users"][user_id_str]
        ref_code = user_data["referral_code"]
        
        # Видаляємо реферальний код користувача
        if ref_code in data["referral_codes"]:
            del data["referral_codes"][ref_code]
        
        # Видаляємо користувача зі списку рефералів інших користувачів
        if user_data["referred_by"]:
            referrer = data["users"][user_data["referred_by"]]
            if user_id_str in referrer["referrals"]:
                referrer["referrals"].remove(user_id_str)
                # Віднімаємо бонусні токени у реферера
                referrer["tokens"] -= 1000
        
        # Обробляємо рефералів видаленого користувача
        for referral_id in user_data.get("referrals", []):
            if referral_id in data["users"]:
                data["users"][referral_id]["referred_by"] = None
        
        # Видаляємо користувача з усіх списків
        if user_id_str in data["counted_users"]:
            data["counted_users"].remove(user_id_str)
        if user_id_str in data["webapp_users"]:
            data["webapp_users"].remove(user_id_str)
        
        # Оновлюємо статистику мов
        language = user_data["language"]
        if language in data["statistics"]["languages"]:
            data["statistics"]["languages"][language] -= 1
            if data["statistics"]["languages"][language] <= 0:
                del data["statistics"]["languages"][language]
        
        # Зменшуємо лічильник використаних місць
        data["used_spots"] -= 1
        
        # Видаляємо самого користувача
        del data["users"][user_id_str]
        
        save_data(data)
        logger.info(f"User {user_id} successfully deleted")
        return True, f"Користувача {user_id} успішно видалено"
        
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        return False, f"Помилка: {str(e)}"

def update_statistics(user_id, action, data=None):
    """
    Оновлення статистики
    action: 'bot_start', 'webapp_open'
    data: додаткові дані (мова, країна)
    """
    try:
        json_data = load_data()
        user_id_str = str(user_id)
        
        # Ініціалізація структури статистики
        if "statistics" not in json_data:
            json_data["statistics"] = {
                "total_bot_users": 0,
                "webapp_opens": 0,
                "languages": {},
                "countries": {}
            }
        if "counted_users" not in json_data:
            json_data["counted_users"] = []
        if "webapp_users" not in json_data:
            json_data["webapp_users"] = []
        
        if action == 'bot_start':
            # Рахуємо тільки нових користувачів бота
            if user_id_str not in json_data["counted_users"]:
                json_data["statistics"]["total_bot_users"] += 1
                json_data["counted_users"].append(user_id_str)
                
                # Оновлення статистики мов та країн
                language = (data.get('language') or 'unknown').lower()
                json_data["statistics"]["languages"][language] = json_data["statistics"]["languages"].get(language, 0) + 1
                
                country = (data.get('country') or 'unknown').upper()
                json_data["statistics"]["countries"][country] = json_data["statistics"]["countries"].get(country, 0) + 1
                
                logger.info(f"Updated statistics for new user {user_id}: lang={language}, country={country}")
                
        elif action == 'webapp_open':
            # Рахуємо відкриття MiniApp тільки для користувачів, які ще його не відкривали
            if user_id_str in json_data["counted_users"] and user_id_str not in json_data["webapp_users"]:
                json_data["statistics"]["webapp_opens"] += 1
                json_data["webapp_users"].append(user_id_str)
                logger.info(f"Updated statistics for first webapp open by user {user_id}")
        
        save_data(json_data)
        return True
    except Exception as e:
        logger.error(f"Error updating statistics: {e}")
        return False

def get_statistics():
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

def generate_referral_code(user_id):
    """Генерація реферального коду"""
    return f"REF{user_id}"

def register_user(user_id, username, language_code, referral_code=None):
    """
    Реєстрація нового користувача
    Повертає (success: bool, message: str)
    """
    try:
        data = load_data()
        user_id_str = str(user_id)
        
        # Перевіряємо чи користувач вже зареєстрований
        if user_id_str in data["users"]:
            return False, "Already registered"
        
        # Перевіряємо чи є вільні місця
        if data["used_spots"] >= data["total_spots"]:
            return False, "No spots left"
        
        # Створюємо нового користувача
        ref_code = generate_referral_code(user_id)
        data["users"][user_id_str] = {
            "username": username,
            "language": language_code,
            "tokens": 5000,
            "referral_code": ref_code,
            "referred_by": None,
            "referrals": [],
            "join_date": datetime.now().isoformat()
        }
        data["referral_codes"][ref_code] = user_id_str
        data["used_spots"] += 1
        
        # Зберігаємо дані користувача
        save_data(data)
        
        # Якщо є реферальний код, обробляємо його
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
        return False, f"Error: {str(e)}"

def add_referral(user_id, referral_code):
    """
    Додавання реферала
    Повертає (success: bool, message: str)
    """
    try:
        data = load_data()
        user_id_str = str(user_id)
        
        # Перевіряємо чи існує реферальний код
        if referral_code not in data["referral_codes"]:
            logger.warning(f"Invalid referral code: {referral_code}")
            return False, "Invalid referral code"
        
        referrer_id = data["referral_codes"][referral_code]
        
        # Перевіряємо чи користувач не намагається використати свій власний код
        if user_id_str == referrer_id:
            logger.warning(f"User {user_id} tried to use their own referral code")
            return False, "Cannot use own referral code"
        
        # Перевіряємо чи користувач вже не був запрошений
        if data["users"][user_id_str]["referred_by"]:
            logger.warning(f"User {user_id} already used a referral code")
            return False, "Already used a referral code"
        
        # Додаємо реферала та нараховуємо токени
        if user_id_str not in data["users"][referrer_id]["referrals"]:
            data["users"][referrer_id]["referrals"].append(user_id_str)
            data["users"][referrer_id]["tokens"] += 1000  # Бонус за реферала
            data["users"][user_id_str]["referred_by"] = referrer_id
            save_data(data)
            logger.info(f"Successfully added referral: {user_id} -> {referrer_id}")
            return True, "Success"
        
        logger.warning(f"User {user_id} was already referred by {referrer_id}")
        return False, "Already referred"
        
    except Exception as e:
        logger.error(f"Error in add_referral: {e}")
        return False, f"Error: {str(e)}"

def get_spots_left():
    """Отримання кількості вільних місць"""
    data = load_data()
    return data["total_spots"] - data["used_spots"]

def get_user_data(user_id):
    """Отримання даних користувача"""
    data = load_data()
    return data["users"].get(str(user_id))

def get_user_stats(user_id):
    """Отримання статистики користувача"""
    user_data = get_user_data(user_id)
    if not user_data:
        return None
    
    referrals_count = len(user_data.get('referrals', []))
    return {
        'tokens': user_data['tokens'],
        'referrals_count': referrals_count,
        'referral_earnings': referrals_count * 1000,
        'referral_code': user_data['referral_code'],
        'username': user_data['username'],
        'language': user_data['language']
    }

def generate_referral_link(user_id):
    """Генерація реферального посилання"""
    user_data = get_user_data(user_id)
    if not user_data:
        return None
    return f"https://t.me/AI_DropHelper_bot?start={user_data['referral_code']}"