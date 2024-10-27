from flask import Flask, render_template, send_file, request, redirect, url_for, session, flash
import json
import os
import pandas as pd
import csv
import io
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Замініть на ваш секретний ключ

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Оновлений шлях до файлу users.json
DATA_FILE_PATH = r"C:\1\drophelper-bot\data\users.json"

def load_data():
    # Перевірка існування файлу
    if not os.path.exists(DATA_FILE_PATH):
        raise FileNotFoundError(f"Файл не знайдено за шляхом: {DATA_FILE_PATH}")
    
    with open(DATA_FILE_PATH, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Помилка при завантаженні JSON: {e}")
    
    # Переконайтеся, що ключ "users" існує і є словником
    if "users" not in data or not isinstance(data["users"], dict):
        raise ValueError("JSON-файл має неправильну структуру: відсутній ключ 'users' або він не є словником.")
    
    users_data = data["users"]
    
    # Валідація даних: всі значення повинні бути словниками і мати необхідні поля
    required_fields = {"username", "language", "tokens", "referral_code", "referred_by", "referrals", "join_date"}
    valid_data = {}
    invalid_data = {}
    
    for user_id, user_info in users_data.items():
        if isinstance(user_info, dict):
            # Перевірка наявності необхідних полів
            if required_fields.issubset(user_info.keys()):
                # Перевірка, що 'referrals' є списком
                if isinstance(user_info['referrals'], list):
                    valid_data[user_id] = user_info
                else:
                    # Спробуйте конвертувати у список, якщо це можливо
                    try:
                        user_info['referrals'] = list(user_info['referrals'])
                        valid_data[user_id] = user_info
                        logging.warning(f"Користувач {user_id} має поле 'referrals', яке не було списком. Конвертовано у список.")
                    except TypeError:
                        # Якщо не вдалося, відзначте як некоректний
                        invalid_data[user_id] = {
                            "missing_fields": ["referrals (не є списком)"],
                            "data": user_info
                        }
            else:
                # Відсутні необхідні поля
                missing = required_fields - set(user_info.keys())
                invalid_data[user_id] = {
                    "missing_fields": list(missing),
                    "data": user_info
                }
        else:
            # Некоректний запис користувача
            invalid_data[user_id] = user_info
    
    if invalid_data:
        logging.warning(f"Знайдено некоректні записи у users.json: {invalid_data}")
    
    return valid_data

def process_referral_stats_with_pandas(data):
    df = pd.DataFrame.from_dict(data, orient='index')
    df['referrals_count'] = df['referrals'].apply(len)
    
    total_users = len(df)
    total_referrals = df['referrals_count'].sum()
    total_referrers = df[df['referrals_count'] > 0].shape[0]
    average_referrals = df['referrals_count'].mean()
    top_referrers = df.sort_values(by='referrals_count', ascending=False).head(10)
    referral_sources = df['referred_by'].value_counts()
    
    return {
        'total_users': total_users,
        'total_referrals': total_referrals,
        'total_referrers': total_referrers,
        'average_referrals': round(average_referrals, 2),
        'top_referrers': list(zip(top_referrers.index, top_referrers['referrals_count'])),
        'referral_sources': referral_sources.to_dict()
    }

@app.route('/')
def index():
    try:
        data = load_data()
        stats = process_referral_stats_with_pandas(data)
        return render_template('index.html', stats=stats)
    except Exception as e:
        logging.error(f"Сталася помилка при обробці даних: {e}")
        return f"Сталася помилка при обробці даних: {e}", 500

# Додавання маршруту для експорту CSV
@app.route('/export/csv')
def export_csv():
    try:
        data = load_data()
        stats = process_referral_stats_with_pandas(data)
        
        # Створення CSV
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(["User ID", "Number of Referrals"])
        for user_id, count in stats['top_referrers']:
            cw.writerow([user_id, count])
        
        output = io.BytesIO()
        output.write(si.getvalue().encode('utf-8'))
        output.seek(0)
        
        return send_file(output, mimetype='text/csv', as_attachment=True, attachment_filename='top_referrers.csv')
    except Exception as e:
        logging.error(f"Сталася помилка при експорті CSV: {e}")
        return f"Сталася помилка при експорті CSV: {e}", 500

# Глобальні обробники помилок
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)
