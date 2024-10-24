import os
import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Імпортуємо функції з utils.py
from .utils import (
    load_data, save_data, register_user, get_spots_left, 
    get_user_data, get_user_stats, generate_referral_link
)

# Отримуємо абсолютний шлях до директорії проекту
BASE_DIR = Path(__file__).resolve().parent.parent

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Обробник сигналу завершення
def signal_handler(sig, frame):
    print('\nЗавершення роботи бота...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Завантаження змінних середовища
load_dotenv(BASE_DIR / '.env')

# Завантаження текстів
def load_texts():
    texts = {}
    texts_dir = BASE_DIR / 'bot' / 'texts'
    for lang in ['ua', 'ru', 'en']:
        with open(texts_dir / f'{lang}.json', 'r', encoding='utf-8') as file:
            texts[lang] = json.load(file)
    return texts

# Завантаження текстів при старті
try:
    texts = load_texts()
except Exception as e:
    logger.error(f"Error loading texts: {e}")
    sys.exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /start"""
    user = update.effective_user
    message_text = update.message.text
    
    # Перевіряємо чи є реферальний код в повідомленні
    referral_code = None
    if len(message_text.split()) > 1:
        referral_code = message_text.split()[1]
    
    success, message = register_user(user.id, user.username, user.language_code, referral_code)
    
    # Створення клавіатури вибору мови
    keyboard = [
        [
            InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_ua"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if message == "No spots left":
        await update.message.reply_text(
            "На жаль, всі місця вже зайняті. Ви можете приєднатися до списку очікування."
        )
        return
    
    # Відправка повідомлення вибору мови
    welcome_message = "🌐 Будь ласка, оберіть мову / Пожалуйста, выберите язык / Please select your language"
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    logger.info(f"User {user.id} started bot. Registration status: {message}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /stats"""
    user_stats = get_user_stats(update.effective_user.id)
    if not user_stats:
        await update.message.reply_text("Ви ще не зареєстровані. Використайте команду /start")
        return
    
    spots_left = get_spots_left()
    ref_link = generate_referral_link(update.effective_user.id)
    
    stats_message = (
        f"📊 Ваша статистика:\n\n"
        f"💎 Токенів Helper: {user_stats['tokens']}\n"
        f"👥 Запрошено друзів: {user_stats['referrals_count']}\n"
        f"💰 Зароблено на рефералах: {user_stats['referral_earnings']}\n"
        f"📝 Вільних місць: {spots_left}\n"
        f"🔗 Ваш реферальний код: {user_stats['referral_code']}\n"
        f"🌐 Ваше реферальне посилання:\n{ref_link}\n\n"
        f"Запрошуйте друзів та отримуйте по 1000 токенів за кожного!"
    )
    
    # Створення кнопок для копіювання
    keyboard = [
        [InlineKeyboardButton("📋 Копіювати код", callback_data=f"copy_code_{user_stats['referral_code']}")],
        [InlineKeyboardButton("🔗 Копіювати посилання", callback_data="copy_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(stats_message, reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка натискань кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("lang_"):
        # Обробка вибору мови
        selected_lang = query.data.split('_')[1]
        user_id = query.from_user.id
        
        user_data = get_user_data(user_id)
        spots_left = get_spots_left()
        
        logger.info(f"User {user_id} selected language: {selected_lang}")
        
        # Створення URL для MiniApp
        base_url = "https://efm-ua.github.io/drophelper-miniapp"
        webapp_url = f"{base_url}/index-{selected_lang}.html"
        params = f"?spots={spots_left}&tokens={user_data['tokens']}&ref={user_data['referral_code']}&lang={selected_lang}"
        webapp_url += params
        
        logger.info(f"Generated WebApp URL: {webapp_url}")
        
        # Створення кнопки для MiniApp
        keyboard = [[InlineKeyboardButton(
            texts[selected_lang]["button"],
            web_app=WebAppInfo(url=webapp_url)
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Відправка повідомлень
        await query.message.reply_text(texts[selected_lang]["language_selected"])
        
        image_path = BASE_DIR / 'image.webp'
        with open(image_path, 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=texts[selected_lang]["welcome"],
                reply_markup=reply_markup
            )
    
    elif query.data.startswith("copy_code_"):
        # Обробка копіювання реферального коду
        code = query.data.split('_')[2]
        await query.message.reply_text(f"Реферальний код {code} скопійовано!")
    
    elif query.data == "copy_link":
        # Обробка копіювання реферального посилання
        ref_link = generate_referral_link(query.from_user.id)
        await query.message.reply_text(f"Реферальне посилання скопійовано!\n{ref_link}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /help"""
    help_text = (
        "🤖 Доступні команди:\n\n"
        "/start - Почати роботу з ботом\n"
        "/stats - Переглянути вашу статистику\n"
        "/help - Показати це повідомлення\n\n"
        "ℹ️ Додаткова інформація:\n"
        "- Отримайте 5000 токенів за реєстрацію\n"
        "- Запрошуйте друзів та отримуйте 1000 токенів за кожного\n"
        "- Використовуйте команду /stats для отримання вашого реферального посилання"
    )
    await update.message.reply_text(help_text)

def main():
    """Основна функція запуску бота"""
    try:
        # Створення застосунку
        application = Application.builder().token(os.getenv('BOT_TOKEN')).build()

        # Додавання обробників команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_click))

        # Запуск бота
        print("Бот запускається...")
        print("Для завершення роботи натисніть Ctrl+C")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except KeyboardInterrupt:
        print("\nОтримано сигнал завершення роботи...")
        if 'application' in locals():
            application.stop()
        print("Бот успішно зупинений")
        sys.exit(0)

    except Exception as e:
        print(f"\nПомилка: {e}")
        if 'application' in locals():
            application.stop()
        sys.exit(1)

if __name__ == '__main__':
    main()