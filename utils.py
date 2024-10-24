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
            "total_spots": 1000,
            "used_spots": 0,
            "referral_codes": {}
        }
        save_data(initial_data)
        return initial_data
    with open(DATA_FILE, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_data(data):
    """Збереження даних в JSON файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def generate_referral_code(user_id):
    """Генерація реферального коду"""
    return f"REF{user_id}"

def register_user(user_id, username, language_code, referral_code=None):
    """
    Реєстрація нового користувача
    Повертає (success: bool, message: str)
    """
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
        "tokens": 5000,  # Початкові токени
        "referral_code": ref_code,
        "referred_by": None,
        "referrals": [],
        "join_date": datetime.now().isoformat()
    }
    data["referral_codes"][ref_code] = user_id_str
    data["used_spots"] += 1
    
    # Якщо є реферальний код, обробляємо його
    if referral_code:
        success, message = add_referral(user_id, referral_code)
        if not success:
            logger.warning(f"Failed to process referral for user {user_id}: {message}")
    
    save_data(data)
    return True, "Success"

def add_referral(user_id, referral_code):
    """
    Додавання реферала
    Повертає (success: bool, message: str)
    """
    data = load_data()
    user_id_str = str(user_id)
    
    # Перевіряємо чи існує реферальний код
    if referral_code not in data["referral_codes"]:
        return False, "Invalid referral code"
    
    referrer_id = data["referral_codes"][referral_code]
    
    # Перевіряємо чи користувач не намагається використати свій власний код
    if user_id_str == referrer_id:
        return False, "Cannot use own referral code"
    
    # Перевіряємо чи користувач вже не був запрошений
    if data["users"][user_id_str].get("referred_by"):
        return False, "Already used a referral code"
    
    # Додаємо реферала та нараховуємо токени
    if user_id_str not in data["users"][referrer_id]["referrals"]:
        data["users"][referrer_id]["referrals"].append(user_id_str)
        data["users"][referrer_id]["tokens"] += 1000  # Бонус за реферала
        data["users"][user_id_str]["referred_by"] = referrer_id
        save_data(data)
        return True, "Success"
    
    return False, "Already referred"

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