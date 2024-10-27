import os
import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from functools import wraps
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Імпортуємо функції з utils.py та locales.py
from .utils import (
    load_data, save_data, register_user, get_spots_left, 
    get_user_data, get_user_stats, generate_referral_link,
    update_statistics, get_statistics, clear_statistics, delete_user
)
from .locales import LocaleManager

# Отримуємо абсолютний шлях до директорії проекту
BASE_DIR = Path(__file__).resolve().parent.parent

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Список адмін-користувачів
ADMIN_USERS = ['1229624876']

# Ініціалізуємо менеджер локалізації
locale_manager = LocaleManager(BASE_DIR / 'bot' / 'texts')

def admin_required(func):
    """Декоратор для перевірки адмін-прав"""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id)
        if user_id not in ADMIN_USERS:
            await update.message.reply_text("⛔️ У вас немає доступу до цієї команди")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def signal_handler(sig, frame):
    print('\nЗавершення роботи бота...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Завантаження змінних середовища
load_dotenv(BASE_DIR / '.env')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /start"""
    user = update.effective_user
    message_text = update.message.text
    user_id_str = str(user.id)
    
    # Визначаємо мову користувача
    user_language = locale_manager.get_user_language(user_id_str, user.language_code)
    logger.info(f"Detected language for user {user_id_str}: {user_language}")
    
    # Оновлюємо статистику
    update_statistics(user.id, 'bot_start', {
        'language': user_language,
        'country': None
    })
    
    # Перевіряємо чи є реферальний код в повідомленні
    referral_code = None
    if len(message_text.split()) > 1:
        referral_code = message_text.split()[1]
    
    success, message = register_user(user.id, user.username, user_language, referral_code)
    
    if message == "No spots left":
        await update.message.reply_text(
            locale_manager.get_text("spots_taken", user_id_str, user_language)
        )
        return
        
    # Отримуємо дані для MiniApp
    spots_left = get_spots_left()
    user_data = get_user_data(user.id)
    
    # Створення URL для MiniApp
    base_url = "https://efm-ua.github.io/drophelper-miniapp"
    webapp_url = f"{base_url}/index-{user_language}.html"
    params = f"?spots={spots_left}&tokens={user_data['tokens']}&ref={user_data['referral_code']}&lang={user_language}"
    webapp_url += params
    
    # Створення кнопки для MiniApp
    keyboard = [[InlineKeyboardButton(
        locale_manager.get_text("button", user_id_str, user_language),
        web_app=WebAppInfo(url=webapp_url)
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Відправляємо вітальне повідомлення з фото
    with open(BASE_DIR / 'image.webp', 'rb') as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=locale_manager.get_text("welcome", user_id_str, user_language),
            reply_markup=reply_markup
        )
    
    # Оновлюємо статистику відкриття WebApp
    update_statistics(user.id, 'webapp_open')
    logger.info(f"User {user_id_str} started bot. Registration status: {message}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /stats"""
    user = update.effective_user
    user_id_str = str(user.id)
    user_language = locale_manager.get_user_language(user_id_str, user.language_code)
    
    user_stats = get_user_stats(user.id)
    if not user_stats:
        await update.message.reply_text(
            locale_manager.get_text("not_registered", user_id_str, user_language)
        )
        return
    
    spots_left = get_spots_left()
    ref_link = generate_referral_link(user.id)
    
    stats_message = (
        f"{locale_manager.get_text('stats_title', user_id_str, user_language)}:\n\n"
        f"{locale_manager.get_text('tokens_label', user_id_str, user_language)}: {user_stats['tokens']}\n"
        f"{locale_manager.get_text('referrals_label', user_id_str, user_language)}: {user_stats['referrals_count']}\n"
        f"{locale_manager.get_text('earnings_label', user_id_str, user_language)}: {user_stats['referral_earnings']}\n"
        f"{locale_manager.get_text('spots_left_label', user_id_str, user_language)}: {spots_left}\n\n"
        f"{locale_manager.get_text('referral_link_label', user_id_str, user_language)}:\n{ref_link}"
    )
    
    # Створення кнопки для копіювання
    keyboard = [[InlineKeyboardButton(
        locale_manager.get_text("copy_link_button", user_id_str, user_language),
        callback_data="copy_link"
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(stats_message, reply_markup=reply_markup)

@admin_required
async def stats_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /stats_admin"""
    stats = get_statistics()
    if not stats:
        await update.message.reply_text("❌ Помилка отримання статистики")
        return
    
    message = (
        "📊 Загальна статистика бота:\n\n"
        f"👥 Всього користувачів: {stats['total_users']}\n"
        f"🌐 Запусків MiniApp: {stats['webapp_opens']}\n"
        f"📈 Конверсія: {stats['conversion']}%\n"
        f"📝 Вільних місць: {stats['spots_left']}\n\n"
        "🗣 Мови користувачів:\n"
    )
    
    for lang, count in stats['languages'].items():
        flag = {
            'uk': '🇺🇦',
            'ua': '🇺🇦',
            'ru': '🇷🇺',
            'en': '🇬🇧',
            'unknown': '❓'
        }.get(lang.lower(), '🌐')
        message += f"{flag} {lang}: {count}\n"
    
    if stats['countries']:
        message += "\n🌍 Країни:\n"
        for country, count in stats['countries'].items():
            message += f"- {country}: {count}\n"
    
    await update.message.reply_text(message)

@admin_required
async def clear_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /clear_stats"""
    success, message = clear_statistics()
    user_id_str = str(update.effective_user.id)
    user_language = locale_manager.get_user_language(user_id_str, update.effective_user.language_code)
    
    if success:
        await update.message.reply_text(
            "✅ Статистику успішно очищено!\n"
            "Використайте /stats_admin для перевірки"
        )
    else:
        await update.message.reply_text(
            locale_manager.format_text("error_occurred", user_id_str, error=message)
        )

@admin_required
async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /delete_user"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Потрібно вказати ID користувача!\n"
            "Використання: /delete_user <user_id>"
        )
        return
    
    try:
        user_id = context.args[0]
        success, message = delete_user(user_id)
        
        if success:
            await update.message.reply_text(f"✅ {message}")
        else:
            await update.message.reply_text(f"❌ {message}")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /help"""
    user = update.effective_user
    user_id_str = str(user.id)
    user_language = locale_manager.get_user_language(user_id_str, user.language_code)
    
    help_text = (
        f"{locale_manager.get_text('help_title', user_id_str, user_language)}:\n\n"
        f"/start - {locale_manager.get_text('help_start', user_id_str, user_language)}\n"
        f"/stats - {locale_manager.get_text('help_stats', user_id_str, user_language)}\n"
        f"/help - {locale_manager.get_text('help_help', user_id_str, user_language)}\n\n"
        f"{locale_manager.get_text('help_additional', user_id_str, user_language)}:\n"
        f"{locale_manager.get_text('help_tokens_info', user_id_str, user_language)}"
    )
    
    # Додаткові команди для адмінів
    if user_id_str in ADMIN_USERS:
        admin_help = (
            "\n\n👑 Команди адміністратора:\n"
            "/stats_admin - Загальна статистика\n"
            "/clear_stats - Очистити статистику\n"
            "/delete_user - Видалити користувача (формат: /delete_user <user_id>)"
        )
        help_text += admin_help
    
    await update.message.reply_text(help_text)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка натискань кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "copy_link":
        user = query.from_user
        user_id_str = str(user.id)
        user_language = locale_manager.get_user_language(user_id_str, user.language_code)
        
        ref_link = generate_referral_link(user.id)
        await query.message.reply_text(
            f"{locale_manager.get_text('link_copied', user_id_str, user_language)}\n{ref_link}"
        )

def main():
    """Основна функція запуску бота"""
    try:
        # Створення застосунку
        application = Application.builder().token(os.getenv('BOT_TOKEN')).build()

        # Додавання обробників команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("stats_admin", stats_admin))
        application.add_handler(CommandHandler("clear_stats", clear_stats_command))
        application.add_handler(CommandHandler("delete_user", delete_user_command))
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