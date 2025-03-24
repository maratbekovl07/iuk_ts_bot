import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import openai
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

openai.api_key = "OPENAI_API_KEY"
bot = telebot.TeleBot('7759072375:AAFOzaKYQShuSrteyMxmHfQzoT5BX3E956U')  # Укажите ваш токен

ADMIN_GROUP_ID = -4777086960  # Замените на ID вашей группы

# Хранилище заблокированных пользователей
banned_users = set()  # Хранилище заблокированных пользователей

FORBIDDEN_WORDS = []  # Замените на реальные запрещенные слова

def contains_profanity(text):
    """
    Проверяет текст на наличие запрещенных слов.
    """
    for word in FORBIDDEN_WORDS:
        if word in text.lower():  # Приводим текст к нижнему регистру для сравнения
            return True
    return False

# Возможные состояния
STATE_DEFAULT = "default"
STATE_IT_HUB_CONTACT = "it_hub_contact"
STATE_AVN_RESTORE = "avn_restore"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_type TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def set_user_state(user_id, state):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_states (
            user_id INTEGER PRIMARY KEY,
            state TEXT
        )
    ''')
    c.execute('INSERT OR REPLACE INTO user_states (user_id, state) VALUES (?, ?)', (user_id, state))
    conn.commit()
    conn.close()

def get_user_state(user_id):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('SELECT state FROM user_states WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    conn.close()
    return state[0] if state else STATE_DEFAULT

def save_message_to_db(user_id, message_type, content):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('INSERT INTO messages (user_id, message_type, content) VALUES (?, ?, ?)', (user_id, message_type, content))
    conn.commit()
    conn.close()

@bot.message_handler(commands=['start'])
def main(message):
    if message.chat.id == ADMIN_GROUP_ID:
        admin_menu(message)
        return

    # Главное меню для пользователя
    main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
    main_menu.add(KeyboardButton("📘 AVN"), KeyboardButton("🌐 Сайт колледжа"))
    main_menu.add(KeyboardButton("🔒 Восстановление AVN"), KeyboardButton("✉️ Обращение к IT Hab"))

    bot.send_message(
        message.chat.id,
        "Привет, студент Политехнического колледжа МУКР! 🎓\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=main_menu
    )

def admin_menu(message):
    # Меню для администратора
    admin_menu = ReplyKeyboardMarkup(resize_keyboard=True)
    admin_menu.add(KeyboardButton("📋 Очередь сообщений"), KeyboardButton("✉️ Ответить пользователю"))
    admin_menu.add(KeyboardButton("🔧 Инструкция по использованию"))

    bot.send_message(
        message.chat.id,
        "Добро пожаловать в админ-панель! 👨‍💻\nВыберите действие:",
        reply_markup=admin_menu
    )

@bot.message_handler(func=lambda message: message.text == "📋 Очередь сообщений" and message.chat.id == ADMIN_GROUP_ID)
def show_queue(message):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('SELECT user_id, message_type, content FROM messages')
    rows = c.fetchall()
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, "📭 Очередь пуста. Сообщений от пользователей нет.")
        return

    queue_summary = "📋 Очередь сообщений:\n\n"
    for user_id, message_type, content in rows:
        queue_summary += f"👤 Пользователь {user_id}:\n"
        if message_type == 'text':
            queue_summary += f"  ✉️ Текст: {content[:50]}...\n"
        elif message_type == 'photo':
            queue_summary += f"  📸 Фото (ID: {content})\n"
        queue_summary += "\n"

    bot.send_message(message.chat.id, queue_summary)

@bot.message_handler(func=lambda message: message.text == "✉️ Ответить пользователю" and message.chat.id == ADMIN_GROUP_ID)
def reply_instruction(message):
    bot.send_message(
        message.chat.id,
        "Для ответа пользователю используйте команду:\n\n"
        "`/reply <user_id> <текст ответа>`\n\n"
        "Например: `/reply 123456789 Добрый день, ваш запрос обработан.`",
        parse_mode="Markdown"
    )

def user_exists(user_id):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('SELECT 1 FROM messages WHERE user_id = ?', (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

@bot.message_handler(commands=['reply'])
def reply_to_user(message):
    if message.chat.id != ADMIN_GROUP_ID:
        bot.send_message(message.chat.id, "Вы не администратор!")
        return

    try:
        parts = message.text.split(' ', 2)
        if len(parts) < 3:
            bot.send_message(message.chat.id, "⚠️ Используйте формат команды: `/reply <user_id> <ответ>`", parse_mode="Markdown")
            return

        user_id = int(parts[1])
        reply_text = parts[2]

        if user_exists(user_id):
            bot.send_message(user_id, f"📩 Ответ от администратора:\n\n{reply_text}")
            bot.send_message(message.chat.id, f"✅ Ответ пользователю {user_id} отправлен.")
            conn = sqlite3.connect('messages.db')
            c = conn.cursor()
            c.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
        else:
            bot.send_message(message.chat.id, f"⚠️ Пользователь с ID {user_id} не найден в базе.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda message: message.text == "📘 AVN")
def avn_portal(message):
    set_user_state(message.chat.id, STATE_AVN_RESTORE)  # Пример установки состояния
    bot.send_message(
        message.chat.id,
        "📘 Портал AVN:\n\n"
        "Перейдите на портал AVN для авторизации и доступа к обучающим материалам:\n"
        "[AVN Portal](https://avn.pc.edu.kg/lms/login)",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == "🌐 Сайт колледжа")
def site(message):
    set_user_state(message.chat.id, STATE_AVN_RESTORE)  # Пример установки состояния
    bot.send_message(
        message.chat.id,
        "🌐 Политехнический колледж МУКР:\n\n"
        "Нажмите на ссылку ниже, чтобы перейти на официальный сайт колледжа:\n"
        "[WEB Site](https://pc.edu.kg)",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == "✉️ Обращение к IT Hab")
def it_hab_contact(message):
    set_user_state(message.chat.id, STATE_IT_HUB_CONTACT)
    bot.send_message(
        message.chat.id,
        "✉️ Напишите ваше сообщение для IT Hab. Мы постараемся ответить вам как можно быстрее.\n\n"
        "Просто отправьте текст или прикрепите фото прямо в этот чат."
    )

@bot.message_handler(func=lambda message: message.text == "🔒 Восстановление AVN")
def restore_avn(message):
    set_user_state(message.chat.id, STATE_AVN_RESTORE)
    bot.send_message(
        message.chat.id,
        "Для восстановления доступа в AVN выполните следующие шаги:\n\n"
        "1. Заполните рапорт по приведенному ниже шаблону.\n"
        "2. Прикрепите фотографию рапорта и отправьте свои данные (ФИО, группа, номер телефона).\n\n"
        "⚠️ Логин и пароль будут восстановлены только после проверки вашего запроса."
    )
    try:
        with open('шаблон.png', 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption="📎 Пример заполнения рапорта:")
    except FileNotFoundError:
        bot.send_message(message.chat.id, "❌ Шаблон рапорта не найден. Пожалуйста, свяжитесь с администратором.")
    bot.send_message(
        message.chat.id,
        "После того как заполните рапорт, прикрепите фото рапорта и отправьте свои данные через этот чат."
    )

@bot.message_handler(content_types=['photo', 'text'])
def handle_user_message(message):
    user_id = message.chat.id
    state = get_user_state(user_id)

    # Игнорируем сообщения от администратора
    if user_id == ADMIN_GROUP_ID:
        return

    # Проверка на блокировку пользователя
    if user_id in banned_users:
        bot.send_message(user_id, "🚫 Вы были заблокированы за нарушение правил.")
        return

    # Проверяем текстовые сообщения на наличие запрещенных слов
    if message.text and contains_profanity(message.text):
        bot.send_message(user_id, "🚫 Ваше сообщение содержит недопустимые слова. Вы заблокированы.")
        banned_users.add(user_id)  # Добавляем пользователя в список заблокированных
        bot.send_message(ADMIN_GROUP_ID, f"⚠️ Пользователь {user_id} был заблокирован за использование ненормативной лексики.")
        return

    # Проверяем, выбрал ли пользователь команду
    if state == STATE_DEFAULT:
        bot.send_message(user_id, "⚠️ Выберите команду из меню, чтобы продолжить.")
        return

    if state == STATE_IT_HUB_CONTACT:
        handle_message_for_admin(message, user_id)
    elif state == STATE_AVN_RESTORE:
        handle_message_for_admin(message, user_id)
    else:
        bot.send_message(user_id, "⚠️ Выберите команду из меню, чтобы продолжить.")

def handle_message_for_admin(message, user_id):
    """
    Функция для обработки сообщений и отправки их администратору.
    """
    if message.photo:
        photo_id = message.photo[-1].file_id
        save_message_to_db(user_id, 'photo', photo_id)
        bot.send_photo(
            ADMIN_GROUP_ID,
            photo_id,
            caption=f"📸 Фото от пользователя {user_id}:\n\nИмя: {message.from_user.first_name}\n"
                    f"Фамилия: {message.from_user.last_name or 'не указана'}\n"
                    f"Имя пользователя: @{message.from_user.username or 'не указано'}"
        )
        bot.send_message(user_id, "Ваше фото было отправлено администратору. Ожидайте ответа.")
    elif message.text:
        save_message_to_db(user_id, 'text', message.text)
        bot.send_message(
            ADMIN_GROUP_ID,
            f"📩 Сообщение от пользователя {user_id}:\n\n"
            f"Имя: {message.from_user.first_name}\n"
            f"Фамилия: {message.from_user.last_name or 'не указана'}\n"
            f"Имя пользователя: @{message.from_user.username or 'не указано'}\n\n"
            f"Сообщение: {message.text}"
        )
        bot.send_message(user_id, "Ваше сообщение отправлено администратору. Ожидайте ответа.")
    # Возврат в состояние по умолчанию
    set_user_state(user_id, STATE_DEFAULT)

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
