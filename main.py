from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
import mysql.connector
from config import DB_CONFIG, BOT_TOKEN
import re
from fuzzywuzzy import fuzz


# Database connection
db = mysql.connector.connect(**DB_CONFIG)
cursor = db.cursor()

# Define User Roles and Permissions
def create_user_or_staff(user_type, phone_number, password):
    if user_type not in ['staff', 'user', 'admin']:
        raise ValueError("Неверный тип пользователя")

    table = "Admin" if user_type == 'admin' else ("Staff" if user_type == 'staff' else "User")
    cursor.execute(f"INSERT INTO {table} (phone_number, password) VALUES (%s, %s)", 
                   (phone_number, password))
    db.commit()

def list_users_or_staff(user_type):
    table = "Admin" if user_type == 'admin' else ("Staff" if user_type == 'staff' else "User")
    cursor.execute(f"SELECT id, phone_number FROM {table}")
    return cursor.fetchall()

def delete_user_or_staff(user_type, user_id):
    table = "Admin" if user_type == 'admin' else ("Staff" if user_type == 'staff' else "User")
    cursor.execute(f"DELETE FROM {table} WHERE id = %s", (user_id,))
    db.commit()

# Define functions for CRUD operations
def add_question(user_id, question_text):
    cursor.execute("INSERT INTO Question (user_id, question_text, status, created_at) VALUES (%s, %s, %s, NOW())", 
                   (user_id, question_text, 'pending'))
    db.commit()
    return cursor.lastrowid

def get_question_status(question_id):
    cursor.execute("SELECT status FROM Question WHERE id = %s", (question_id,))
    return cursor.fetchone()

def update_question_status(question_id, status):
    cursor.execute("UPDATE Question SET status = %s WHERE id = %s", (status, question_id))
    db.commit()

def add_video(question_id, video_link, title, description, staff_id):
    cursor.execute(
        "INSERT INTO Video (question_id, video_link, title, description, staff_id) VALUES (%s, %s, %s, %s, %s)", 
        (question_id, video_link, title, description, staff_id)
    )
    db.commit()

def get_video_for_question(question_id):
    cursor.execute("SELECT video_link, title, description FROM Video WHERE question_id = %s", (question_id,))
    return cursor.fetchone()

def get_staff_chat_ids():
    cursor.execute("SELECT chat_id FROM Staff WHERE chat_id IS NOT NULL ORDER BY id ASC")
    return [row[0] for row in cursor.fetchall()]

def get_pending_questions():
    cursor.execute("SELECT id, question_text, created_at FROM Question WHERE status = 'pending' ORDER BY created_at")
    return cursor.fetchall()

def get_next_staff_id(current_staff_id=None):
    if current_staff_id:
        cursor.execute("SELECT id FROM Staff WHERE id > %s ORDER BY id ASC LIMIT 1", (current_staff_id,))
    else:
        cursor.execute("SELECT id FROM Staff ORDER BY id ASC LIMIT 1")
    result = cursor.fetchone()
    
    if not result:
        # If no next staff found, start from the beginning
        cursor.execute("SELECT id FROM Staff ORDER BY id ASC LIMIT 1")
        result = cursor.fetchone()
        
    return result[0] if result else None

def calculate_similarity(text1, text2):
    return fuzz.ratio(text1.lower(), text2.lower())

# Define command handlers
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Добро пожаловать! Используйте /login для аутентификации. Используйте /help, чтобы просмотреть доступные команды.')

async def help_command(update: Update, context: CallbackContext) -> None:
    role = context.user_data.get('role')
    if role == 'admin':
        commands = (
            "/create_user <номер телефона> <пароль>\n"
            "/create_staff <номер телефона> <пароль>\n"
            "/create_admin <номер телефона> <пароль>\n"
            "/list_users\n"
            "/list_staff\n"
            "/list_admins\n"
            "/remove_user ID пользователя\n"
            "/remove_staff ID куратора\n"
            "/remove_admin ID администратора"
        )
    elif role == 'staff':
        commands = (
            "/provide_videolink <ID вопроса> <Ссылка на видео> \"<Название>\" \"<Описание>\"\n"
            "/view_pending_questions\n"
        )
    elif role == 'user':
        commands = (
            "/ask <Текст вопроса>\n"
        )
    else:
        commands = "Сначала вам необходимо войти в систему, используя пароль /login <номер телефона> <пароль>."

    await update.message.reply_text(f"Доступные команды:\n{commands}")

async def login(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Использование: /login <номер телефона> <пароль>')
        return

    phone_number, password = args
    cursor.execute("SELECT id, 'admin' AS role FROM Admin WHERE phone_number = %s AND password = %s "
                   "UNION "
                   "SELECT id, 'staff' AS role FROM Staff WHERE phone_number = %s AND password = %s "
                   "UNION "
                   "SELECT id, 'user' AS role FROM User WHERE phone_number = %s AND password = %s",
                   (phone_number, password, phone_number, password, phone_number, password))
    user = cursor.fetchone()

    if user:
        user_id, role = user
        context.user_data['user_id'] = user_id
        context.user_data['role'] = role
        await update.message.reply_text(f'Успешный вход в систему как {role}. Используйте /help, чтобы просмотреть доступные команды.')
        if role != 'admin':
            cursor.execute(f"UPDATE {role.capitalize()} SET chat_id = %s WHERE id = %s", (update.message.chat_id, user_id))
            db.commit()
            print(f"{role.capitalize()} chat_id {update.message.chat_id} saved for user_id {user_id}")
    else:
        await update.message.reply_text('Неверный номер телефона или пароль.')

async def ask_question(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'user':
        await update.message.reply_text('Вы должны войти в систему как пользователь, чтобы задать вопрос.')
        return

    question_text = ' '.join(context.args)
    user_id = context.user_data['user_id']
    question_id = add_question(user_id, question_text)

    cursor.execute("SELECT id, video_link, title, description FROM Video")
    videos = cursor.fetchall()

    similar_videos = [
        (video_id, video_link, title, description) for video_id, video_link, title, description in videos
        if calculate_similarity(question_text, title) > 60 or calculate_similarity(question_text, description) > 60
    ]

    response_message = f"Ваш вопрос был отправлен с ID {question_id}."
    if similar_videos:
        response_message += "\n\nПохожие видео:\n"
        for video_id, video_link, title, description in similar_videos:
            response_message += f"\nНазвание: {title}\nОписание: {description}\nСсылка: {video_link}\n"

    await update.message.reply_text(response_message)

    for video_id, video_link, title, description in similar_videos:
        keyboard = [
            [InlineKeyboardButton("👍", callback_data=f"like_similar:{video_id}:{question_id}"),
             InlineKeyboardButton("👎", callback_data=f"dislike_similar:{video_id}:{question_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Do you like this video?\nНазвание: {title}\nОписание: {description}\nСсылка: {video_link}",
            reply_markup=reply_markup
        )

    # Notify the first staff in ascending order of id
    next_staff_id = get_next_staff_id()
    if next_staff_id:
        cursor.execute("SELECT chat_id FROM Staff WHERE id = %s", (next_staff_id,))
        next_staff_chat_id = cursor.fetchone()[0]
        await context.bot.send_message(next_staff_chat_id, f'New question (ID: {question_id}): {question_text}')
    else:
        cursor.execute("SELECT chat_id FROM Admin LIMIT 1")
        admin_chat_id = cursor.fetchone()[0]
        await context.bot.send_message(admin_chat_id, f'No staff available to review question ID: {question_id}\nВопрос: {question_text}')


async def view_pending_questions(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'staff':
        await update.message.reply_text('You must be logged in as staff to view pending questions.')
        return

    pending_questions = get_pending_questions()
    if not pending_questions:
        await update.message.reply_text('There are no pending questions.')
        return

    response_message = "Pending questions:\n"
    for question_id, question_text, created_at in pending_questions:
        response_message += f"\nID: {question_id}\nВопрос: {question_text}\nAsked on: {created_at}\n"
    await update.message.reply_text(response_message)

import re

async def provide_videolink(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'staff':
        await update.message.reply_text('You must be logged in as staff to provide an answer.')
        return

    # Extract arguments with regex for title and description in double quotes
    text = update.message.text
    match = re.match(r'^/provide_videolink (\d+) (\S+) "([^"]+)" "([^"]+)"$', text)
    
    if not match:
        await update.message.reply_text('Usage: /provide_videolink <question_id> <video_link> "title" "description"')
        return

    question_id = int(match.group(1))
    video_link = match.group(2)
    title = match.group(3)
    description = match.group(4)
    staff_id = context.user_data['user_id']

    add_video(question_id, video_link, title, description, staff_id)
    update_question_status(question_id, 'answered')
    await update.message.reply_text(f'Answer provided for question ID {question_id}.')
    
    cursor.execute("SELECT user_id FROM Question WHERE id = %s", (question_id,))
    user_id = cursor.fetchone()[0]
    cursor.execute("SELECT chat_id FROM User WHERE id = %s", (user_id,))
    user_chat_id = cursor.fetchone()[0]

    if user_chat_id:
        keyboard = [
            [InlineKeyboardButton("👍", callback_data=f"like:{question_id}"),
             InlineKeyboardButton("👎", callback_data=f"dislike:{question_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            user_chat_id,
            f"Your question has been answered.\nНазвание: {title}\nОписание: {description}\nСсылка: {video_link}",
            reply_markup=reply_markup
        )


async def handle_feedback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(':')
    action = data[0]
    video_id_or_question_id = int(data[1])
    
    if action == 'like':
        await context.bot.send_message(chat_id=query.message.chat_id, text="Спасибо за ваш отзыв!")
    elif action == 'dislike':
        await query.edit_message_text(text="Извините, что ответ не помог. Мы еще раз рассмотрим ваш вопрос.")
        update_question_status(video_id_or_question_id, 'pending')
        
        # Notify the next staff member
        cursor.execute("SELECT staff_id FROM Video WHERE question_id = %s", (video_id_or_question_id,))
        current_staff_id = cursor.fetchone()[0]
        next_staff_id = get_next_staff_id(current_staff_id)
        
        cursor.execute("SELECT question_text FROM Question WHERE id = %s", (video_id_or_question_id,))
        question_text = cursor.fetchone()[0]
        
        if next_staff_id:
            cursor.execute("SELECT chat_id FROM Staff WHERE id = %s", (next_staff_id,))
            next_staff_chat_id = cursor.fetchone()[0]
            await context.bot.send_message(next_staff_chat_id, f'Требуется отзыв для вопроса (ID: {video_id_or_question_id}): {question_text}')
        else:
            cursor.execute("SELECT chat_id FROM Admin LIMIT 1")
            admin_chat_id = cursor.fetchone()[0]
            await context.bot.send_message(admin_chat_id, f'Нет кураторов для рассмотрения вопроса ID: {video_id_or_question_id}\nВопрос: {question_text}')
    elif action == 'like_similar':
        question_id = int(data[2])
        await context.bot.send_message(chat_id=query.message.chat_id, text="Спасибо за ваш отзыв! Мы будем использовать это видео для вашего вопроса.")
        update_question_status(question_id, 'answered')
    elif action == 'dislike_similar':
        question_id = int(data[2])
        await query.edit_message_text(text="Извините, что подобное видео не помогло. Мы еще раз рассмотрим ваш вопрос.")
        cursor.execute("DELETE FROM Video WHERE id = %s", (video_id_or_question_id,))
        db.commit()
        update_question_status(question_id, 'pending')
        
        next_staff_id = get_next_staff_id()
        if next_staff_id:
            cursor.execute("SELECT chat_id FROM Staff WHERE id = %s", (next_staff_id,))
            next_staff_chat_id = cursor.fetchone()[0]
            cursor.execute("SELECT question_text FROM Question WHERE id = %s", (question_id,))
            question_text = cursor.fetchone()[0]
            await context.bot.send_message(next_staff_chat_id, f'New question (ID: {question_id}): {question_text}')
        else:
            cursor.execute("SELECT chat_id FROM Admin LIMIT 1")
            admin_chat_id = cursor.fetchone()[0]
            await context.bot.send_message(admin_chat_id, f'Нет кураторов для рассмотрения вопроса ID: {question_id}\nВопрос: {question_text}')

async def create_user(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Для создания пользователей вы должны войти в систему как администратор.')
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Использование: /create_user <номер телефона> <пароль>')
        return

    phone_number, password = args
    create_user_or_staff('user', phone_number, password)
    await update.message.reply_text('Пользователь успешно создан.')

async def create_staff(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Для создания куратора вы должны войти в систему как администратор.')
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Использование: /create_staff <номер телефона> <пароль>')
        return

    phone_number, password = args
    create_user_or_staff('staff', phone_number, password)
    await update.message.reply_text('Куратор успешно создан.')

async def create_admin(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Вы должны войти в систему как администратор, чтобы создать администраторов..')
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Использование: /create_admin <номер телефона> <пароль>')
        return

    phone_number, password = args
    create_user_or_staff('admin', phone_number, password)
    await update.message.reply_text('Администратор успешно создан.')

async def list_users(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Чтобы получить список пользователей, вы должны войти в систему как администратор.')
        return

    users = list_users_or_staff('user')
    response = "Пользователи:\n" + "\n".join([f"ID: {user_id}, Тел: {phone}" for user_id, phone in users])
    await update.message.reply_text(response)

async def list_staff(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Вы должны войти в систему как администратор, чтобы составить список кураторов.')
        return

    staff = list_users_or_staff('staff')
    response = "Кураторы:\n" + "\n".join([f"ID: {staff_id}, Тел: {phone}" for staff_id, phone in staff])
    await update.message.reply_text(response)

async def list_admins(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Вы должны войти в систему как администратор, чтобы получить список администраторов.')
        return

    admins = list_users_or_staff('admin')
    response = "Администраторы:\n" + "\n".join([f"ID: {admin_id}, Тел: {phone}" for admin_id, phone in admins])
    await update.message.reply_text(response)

async def remove_user(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Вы должны войти в систему как администратор, чтобы удалить пользователей.')
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Использование: /remove_user <ID пользователя>')
        return

    user_id = args[0]
    delete_user_or_staff('user', user_id)
    await update.message.reply_text(f'Пользователь {user_id} успешно удален.')

async def remove_staff(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Вы должны войти в систему как администратор, чтобы удалить куратор.')
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Использование: /remove_staff <ID куратора>')
        return

    staff_id = args[0]
    delete_user_or_staff('staff', staff_id)
    await update.message.reply_text(f'Куратор {staff_id} успешно удален.')

async def remove_admin(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Вы должны войти в систему как администратор, чтобы удалить администраторов.')
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Использование: /remove_admin <ID Администратора>')
        return

    admin_id = args[0]
    delete_user_or_staff('admin', admin_id)
    await update.message.reply_text(f'Администратор {admin_id} успешно удален.')

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    
    #General commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("login", login))

    #User's command
    application.add_handler(CommandHandler("ask", ask_question))

    #Staff's commands
    application.add_handler(CommandHandler("view_pending_questions", view_pending_questions))
    application.add_handler(CommandHandler("provide_videolink", provide_videolink))

    #Admin's commands
    application.add_handler(CommandHandler("create_user", create_user))
    application.add_handler(CommandHandler("create_staff", create_staff))
    application.add_handler(CommandHandler("create_admin", create_admin))
    application.add_handler(CommandHandler("list_users", list_users))
    application.add_handler(CommandHandler("list_staff", list_staff))
    application.add_handler(CommandHandler("list_admins", list_admins))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("remove_staff", remove_staff))
    application.add_handler(CommandHandler("remove_admin", remove_admin))
    
    application.add_handler(CallbackQueryHandler(handle_feedback))

    application.run_polling()

if __name__ == "__main__":
    main()