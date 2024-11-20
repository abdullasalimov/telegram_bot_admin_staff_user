from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
import mysql.connector
from config import DB_CONFIG, BOT_TOKEN, SIMILARITY
import re
from fuzzywuzzy import fuzz
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash


# Database connection
db = mysql.connector.connect(**DB_CONFIG)
cursor = db.cursor()

# Language dictionary
LANG_DICT = {
    'en': {
        'commands': {
            'admin': "/set_language\n/create_user <phone> <password>\n/create_staff <phone> <password>\n/create_admin <phone> <password>\n/list_users\n/list_staff\n/list_admins\n/remove_user <user ID>\n/remove_staff <staff ID>\n/remove_admin <admin ID>",
            'staff': "/set_language\n/view_pending_questions\n/provide_videolink <question ID> <video link> \"<Title>\" \"<Description>\"",
            'user': "/set_language\n/ask <your question>",
        },
        'welcome': "Welcome! Use /login to authenticate. Use /help to view available commands.",
        'invalid_user_type': "Invalid user type.",
        'use_login': "You must log in first using /login <phone_number> <password>.",
        'invalid_command_usage': "Usage: /login <phone number> <password>.",
        'user_created': "User successfully created.",
        'staff_created': "Staff successfully created.",
        'admin_created': "Admin successfully created.",
        'login_success': "Successfully logged in as {role}. Use /help view commands.",
        'login_failed': "Invalid phone number or password.",
        'question_asked': "Your question has been submitted with ID {id}.",
        # 'thanks_feedback': "Thank you for your feedback!",
        'help_commands': "Available commands:\n{commands}",
        'user_role':"You must log in as a User to ask a question.",
        'similar_videos':"Similar videos",
        'title':"Title",
        'description':"Description",
        'link':"Link",
        'do_you_like':"Do you like this video?\nTitle: {title}\nDescription: {description}\nLink: {video_link}",
        'new_question':"New question (ID: {question_id}): {question_text}",
        'no_staff_review':"No staff available to review question ID: {question_id}\nQuestion: {question_text}",
        'staff_login':"You must be logged in as staff to view pending questions.",
        'no_questions':"There are no pending questions.",
        'pending':"Pending questions:\n",
        'question':"\nID: {question_id}\nQuestion: {question_text}\nAsked on: {created_at}\n",
        'staff_login_2':"You must be logged in as staff to provide an answer.",
        'usage_provide_videolink':"Usage: /provide_videolink <question_id> <video_link> \"title\" \"description\"",
        'answer_question':"Answer provided for question ID {question_id}.",
        'answered_question':"Your question has been answered.\nTitle: {title}\nDescription: {description}\nLink: {video_link}",
        'review_thanks':"Thank you for your feedback!",
        'answer_no_help':"Sorry, the answer didn't help. We'll look at your question again.",
        'review_required':"Required feedback for question (ID: {video_id_or_question_id}): {question_text}",
        'no_staff':"No staff to handle question ID: {video_id_or_question_id}\nQuestion: {question_text}",
        'thanks_review':"Thank you for your feedback! We'll use this video for your question.",
        'no_help_video':"Sorry this video didn't work. We will consider your question again.",
        'no_staff_available':"No staff to handle question ID: {question_id}\nQuestion: {question_text}.",
        'admin_login':"To create users, you must log in as an admin.",
        'create_user':"Use: /create_user <phone number> <password>",
        'admin_login_staff':"To create staff, you must log in as an admin.",
        'create_staff':"Use: /create_staff <phone number> <password>",
        'admin_login_admin':"You need to sign in as an admin to create admins.",
        'create_admin':"Use: /create_admin <phone number> <password>",
        'user_list':"To get a user list, you must log in as an admin.",
        'users':"Users:\n",
        'staff_list':"To get a staff list, you must log in as an admin.",
        'staff':"Staffs:\n",
        'admin_list':"You need to sign in as an admin to get an admin list.",
        'admin':"Administrators:\n",
        'remove_user':"You need to sign in as an admin to remove users.",
        'remove_user_use':"Use: /remove_user <user ID>.",
        'remove_user_success':"{user_id} has been successfully removed.",        'remove_staff':"You need to sign in as an admin to remove staffs.",
        'remove_staff_use':"Use: /remove_staff <staff ID>.",
        'remove_staff_success':"{staff_id} has been successfully removed.",'remove_admin':"You need to sign in as an admin to remove admins.",
        'remove_admin_use':"Use: /remove_admin <admin ID>.",
        'remove_admin_success':"{admin_id} has been successfully removed.",

    },
    'ru': {
        'commands': {
            'admin': "/set_language\n/create_user <телефон> <пароль>\n/create_staff <телефон> <пароль>\n/create_admin <телефон> <пароль>\n/list_users\n/list_staff\n/list_admins\n/remove_user <ID пользователя>\n/remove_staff <ID куратора>\n/remove_admin <ID администратора>",
            'staff': "/set_language\n/view_pending_questions\n/provide_videolink <ID вопроса> <ссылка на видео> \"<Название>\" \"<Описание>\"",
            'user': "/set_language\n/ask <ваш вопрос>",
        },
        'welcome': "Добро пожаловать! Используйте /login для аутентификации. Используйте /help, чтобы просмотреть доступные команды.",
        'invalid_user_type': "Неверный тип пользователя.",
        'use_login': "Сначала вам необходимо войти в систему, используя /login <номер телефона> <пароль>.",
        'invalid_command_usage': "Использование: /login <номер телефона> <пароль>",
        'user_created': "Пользователь успешно создан.",
        'staff_created': "Куратор успешно создан.",
        'admin_created': "Администратор успешно создан.",
        'login_success': "Успешный вход в систему как {role}. Используйте /help, чтобы просмотреть доступные команды.",
        'login_failed': "Неверный номер телефона или пароль.",
        'question_asked': "Ваш вопрос был отправлен с ID {id}.",
        # 'thanks_feedback': "Спасибо за ваш отзыв!",
        'help_commands': "Доступные команды:\n{commands}",
        'user_role':"Вы должны войти в систему как пользователь, чтобы задать вопрос.",
        'similar_videos':"Похожие видео",
        'title':"Название",
        'description':"Описание",
        'link':"Ссылка",
        'do_you_like':"Вам нравится это видео?\nНазвание: {title}\nОписание: {description}\nСсылка: {video_link}",
        'new_question':"Новый вопрос (ID: {question_id}): {question_text}",
        'no_staff_review':"Нет сотрудников, которые могли бы проверить ID вопроса: {question_id}\nВопрос: {question_text}",
        'staff_login':"Для просмотра ожидаемых вопросов необходимо авторизоваться в качестве Куратора.",
        'no_questions':"Нет ожидаемых вопросов.",
        'pending':"Вопросы ожидания:\n",
        'question':"\nID: {question_id}\nВопрос: {question_text}\nЗапрошен: {created_at}\n",
        'staff_login_2':"Чтобы дать ответ вопросов необходимо авторизоваться в качестве Куратора.",
        'usage_provide_videolink':"Использование: /provide_videolink <ID вопроса> <Ссылка на видео> \"Названия\" \"Описания\"",
        'answer_question':"Ответ предоставлен для ID вопроса {question_id}.",
        'answered_question':"Ваш вопрос получил ответ.\nНазвание: {title}\nОписание: {description}\nСсылка: {video_link}",
        'review_thanks':"Спасибо за ваш отзыв!",
        'answer_no_help':"Извините, что ответ не помог. Мы еще раз рассмотрим ваш вопрос.",
        'review_required':"Требуется отзыв для вопроса (ID: {video_id_or_question_id}): {question_text}",
        'no_staff':"Нет кураторов для рассмотрения вопроса ID: {video_id_or_question_id}\nВопрос: {question_text}",
        'thanks_review':"Спасибо за ваш отзыв! Мы будем использовать это видео для вашего вопроса.",
        'no_help_video':"Извините, что подобное видео не помогло. Мы еще раз рассмотрим ваш вопрос.",
        'no_staff_available':"Нет кураторов для рассмотрения вопроса ID: {question_id}\nВопрос: {question_text}",
        'admin_login':"Для создания пользователей вы должны войти в систему как администратор.",
        'create_user':"Использование: /create_user <номер телефона> <пароль>",
        'admin_login_staff':"Чтобы создать куратор, нужно войти в систему в качестве администратора.",
        'create_staff':"Использование: /create_staff <номер телефона> <пароль>",
        'admin_login_admin':"Вы должны войти в систему как администратор, чтобы создать администраторов.",
        'create_admin':"Использование: /create_admin <номер телефона> <пароль>",
        'user_list':"Чтобы получить список пользователей, вы должны войти в систему как администратор.",
        'users':"Пользователи:\n",
        'staff_list':"Вы должны войти в систему как администратор, чтобы составить список кураторов",
        'staff':"Кураторы:\n",
        'admin_list':"Вы должны войти в систему как администратор, чтобы получить список администраторов.",
        'admin':"Администраторы:\n",
        'remove_user':"Вы должны войти в систему как администратор, чтобы удалить пользователей.",
        'remove_user_use':"Использование: /remove_user <ID пользователя>",
        'remove_user_success':"Пользователь {user_id} успешно удален.",
        'remove_staff':"Вы должны войти в систему как администратор, чтобы удалить кураторов.",
        'remove_staff_use':"Использование: /remove_staff <ID куратора>",
        'remove_staff_success':"Куратор {staff_id} успешно удален.",        'remove_admin':"Вы должны войти в систему как администратор, чтобы удалить админов.",
        'remove_admin_use':"Использование: /remove_admin <ID админа>",
        'remove_admin_success':"Админ {admin_id} успешно удален.",
    },
    'kz': {
        'commands': {
            'admin': "/set_language\n/create_user <телефон> <пароль>\n/create_staff <телефон> <пароль>\n/create_admin <телефон> <пароль>\n/list_users\n/list_staff\n/list_admins\n/remove_user <қолданушы ID>\n/remove_staff <қызметкер ID>\n/remove_admin <әкімші ID>",
            'staff': "/set_language\n/view_pending_questions\n/provide_videolink <сұрақ ID> <бейне сілтеме> \"<Тақырыбы>\" \"<Сипаттама>\"",
            'user': "/set_language\n/ask <сұрағыңыз>",
        },
        'welcome': "Қош келдіңіз! Аутентификация үшін /login пайдаланыңыз. Қол жетімді командаларды көру үшін /help пайдаланыңыз.",
        'invalid_user_type': "Жарамсыз пайдаланушы түрі.",
        'use_login': "Алдымен /login <телефон нөмірі> <құпия сөз> арқылы жүйеге кіруіңіз керек.",
        'invalid_command_usage': "Қолдану: /login <телефон нөмірі> <құпия сөз>.",
        'user_created': "Пайдаланушы сәтті құрылды.",
        'staff_created': "Қызметкер сәтті құрылды.",
        'admin_created': "Администратор сәтті құрылды.",
        'login_success': "{role} ретінде сәтті кіру. Командаларды көру үшін /help пайдаланыңыз.",
        'login_failed': "Телефон нөмірі немесе құпия сөз дұрыс емес.",
        'question_asked': "Сіздің сұрағыңыз ID {id} нөмірімен жіберілді.",
        # 'thanks_feedback': "Пікіріңіз үшін рахмет!",
        'help_commands': "Қол жетімді командалар:\n{commands}",
        'user_role': "Сұрақ қою үшін пайдаланушы ретінде кіруіңіз керек.",
        'similar_videos': "Ұқсас видеолар",
        'title': "Атауы",
        'description': "Сипаттама",
        'link': "Сілтеме",
        'do_you_like': "Бұл видео ұнай ма?\nАтауы: {title}\nСипаттама: {description}\nСілтеме: {video_link}",
        'new_question': "Жаңа сұрақ (ID: {question_id}): {question_text}",
        'no_staff_review': "ID {question_id} сұрағын қарау үшін қызметкерлер жоқ.\nСұрақ: {question_text}",
        'staff_login': "Күтілген сұрақтарды көру үшін қызметкер ретінде кіруіңіз керек.",
        'no_questions': "Күтілген сұрақтар жоқ.",
        'pending': "Күтілген сұрақтар:\n",
        'question': "\nID: {question_id}\nСұрақ: {question_text}\nҚойылған күні: {created_at}\n",
        'staff_login_2': "Сұрақтарға жауап беру үшін қызметкер ретінде кіруіңіз керек.",
        'usage_provide_videolink': "Қолдану: /provide_videolink <сұрақ ID> <видео сілтеме> \"атауы\" \"сипаттама\"",
        'answer_question': "ID {question_id} сұрағына жауап берілді.",
        'answered_question': "Сіздің сұрағыңызға жауап берілді.\nАтауы: {title}\nСипаттама: {description}\nСілтеме: {video_link}",
        'review_thanks': "Пікіріңіз үшін рахмет!",
        'answer_no_help': "Кешіріңіз, жауап көмектеспеді. Біз сіздің сұрағыңызды қайта қараймыз.",
        'review_required': "Сұрақ үшін пікір қажет (ID: {video_id_or_question_id}): {question_text}",
        'no_staff': "ID {video_id_or_question_id} сұрағын қарау үшін қызметкерлер жоқ.\nСұрақ: {question_text}",
        'thanks_review': "Пікіріңіз үшін рахмет! Біз осы видеоны сіздің сұрағыңыз үшін пайдаланамыз.",
        'no_help_video': "Кешіріңіз, бұл видео көмектеспеді. Біз сіздің сұрағыңызды қайта қараймыз.",
        'no_staff_available': "ID {question_id} сұрағын қарау үшін қызметкерлер жоқ.\nСұрақ: {question_text}.",
        'admin_login': "Пайдаланушыларды құру үшін әкімші ретінде кіруіңіз керек.",
        'create_user': "Қолдану: /create_user <телефон нөмірі> <құпия сөз>",
        'admin_login_staff': "Қызметкерлерді құру үшін әкімші ретінде кіруіңіз керек.",
        'create_staff': "Қолдану: /create_staff <телефон нөмірі> <құпия сөз>",
        'admin_login_admin': "Администраторларды құру үшін әкімші ретінде кіруіңіз керек.",
        'create_admin': "Қолдану: /create_admin <телефон нөмірі> <құпия сөз>",
        'user_list': "Пайдаланушылар тізімін алу үшін әкімші ретінде кіруіңіз керек.",
        'users': "Пайдаланушылар:\n",
        'staff_list': "Қызметкерлер тізімін алу үшін әкімші ретінде кіруіңіз керек.",
        'staff': "Қызметкерлер:\n",
        'admin_list': "Администраторлар тізімін алу үшін әкімші ретінде кіруіңіз керек.",
        'admin': "Администраторлар:\n",
        'remove_user': "Пайдаланушыларды жою үшін әкімші ретінде кіруіңіз керек.",
        'remove_user_use': "Қолдану: /remove_user <пайдаланушы ID>.",
        'remove_user_success': "{user_id} пайдаланушысы сәтті жойылды.",
        'remove_staff': "Қызметкерлерді жою үшін әкімші ретінде кіруіңіз керек.",
        'remove_staff_use': "Қолдану: /remove_staff <қызметкер ID>.",
        'remove_staff_success': "{staff_id} қызметкері сәтті жойылды.",
        'remove_admin': "Администраторларды жою үшін әкімші ретінде кіруіңіз керек.",
        'remove_admin_use': "Қолдану: /remove_admin <администратор ID>.",
        'remove_admin_success': "{admin_id} администраторы сәтті жойылды.",
    }
}

# Function to get language preference from context
def get_user_language(context):
    return context.user_data.get('language', 'en')

# Wrapper function for multi-language messages
def tr(context: CallbackContext, key: str, **kwargs) -> str:
    language = context.user_data.get('language', 'en')  # Default to English
    text = LANG_DICT.get(language, {}).get(key, LANG_DICT['en'].get(key, key))
    if isinstance(text, dict):  # For nested keys like 'commands'
        return text  # Directly return the dictionary if needed
    return text.format(**kwargs) if kwargs else text

# Define User Roles and Permissions
def create_user_or_staff(user_type, phone_number, password):
    if user_type not in ['staff', 'user', 'admin']:
        raise ValueError('invalid_user_type')

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
    await update.message.reply_text(tr(context, 'welcome'))

async def help_command(update: Update, context: CallbackContext) -> None:
    role = context.user_data.get('role')
    language = context.user_data.get('language', 'en')  # Default to 'en'
    localized_commands = LANG_DICT[language]['commands'].get(role, tr(context, 'use_login'))
    await update.message.reply_text(tr(context, 'help_commands', commands=localized_commands))


async def login(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(tr(context, 'invalid_command_usage'))
        return

    phone_number, password = args
    
    # Query to fetch user information and password hash
    cursor.execute("""
        SELECT id, 'admin' AS role, password FROM Admin WHERE phone_number = %s
        UNION
        SELECT id, 'staff' AS role, password FROM Staff WHERE phone_number = %s
        UNION
        SELECT id, 'user' AS role, password FROM User WHERE phone_number = %s
    """, (phone_number, phone_number, phone_number))
    
    user = cursor.fetchone()

    if user:
        user_id, role, stored_password_hash = user
        
        # Verify the password using the hashed password stored in the database
        if check_password_hash(stored_password_hash, password):
            context.user_data['user_id'] = user_id
            context.user_data['role'] = role

            # Fetch user language
            cursor.execute(f"SELECT language FROM {role.capitalize()} WHERE id = %s", (user_id,))
            user_language = cursor.fetchone()[0] or 'en'  # Default to English if no language is set
            context.user_data['language'] = user_language

            await update.message.reply_text(tr(context, 'login_success', role=role))
            
            # Update chat_id for any role
            cursor.execute(f"UPDATE {role.capitalize()} SET chat_id = %s WHERE id = %s", (update.message.chat_id, user_id))
            db.commit()
            print(f"{role.capitalize()} chat_id {update.message.chat_id} saved for user_id {user_id}")
        
        else:
            await update.message.reply_text(tr(context,'login_failed'))
    else:
        await update.message.reply_text(tr(context,'login_failed'))

async def ask_question(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'user':
        await update.message.reply_text(tr(context, 'user_role'))
        return

    question_text = ' '.join(context.args)
    user_id = context.user_data['user_id']
    question_id = add_question(user_id, question_text)

    cursor.execute("SELECT id, video_link, title, description FROM Video")
    videos = cursor.fetchall()

    similar_videos = [
        (video_id, video_link, title, description) for video_id, video_link, title, description in videos
        if calculate_similarity(question_text, title) > SIMILARITY or calculate_similarity(question_text, description) > SIMILARITY
    ]

    response_message = tr(context, 'question_asked', id=question_id)
    if similar_videos:
        response_message += f"\n\n{tr(context,'similar_videos')}:\n"
        for video_id, video_link, title, description in similar_videos:
            response_message += f"\n{tr(context, 'title')}: {title}\n{tr(context, 'description')}: {description}\n{tr(context, 'link')}: {video_link}\n"

    await update.message.reply_text(response_message)

    for video_id, video_link, title, description in similar_videos:
        keyboard = [
            [InlineKeyboardButton("👍", callback_data=f"like_similar:{video_id}:{question_id}"),
             InlineKeyboardButton("👎", callback_data=f"dislike_similar:{video_id}:{question_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(tr(context,'do_you_like',title=title,description=description,link=video_link), reply_markup=reply_markup)

    # Notify the first staff in ascending order of id
    next_staff_id = get_next_staff_id()

    print(next_staff_id)
    
    if next_staff_id:
        cursor.execute("SELECT chat_id FROM Staff WHERE id = %s", (next_staff_id,))
        next_staff_chat_id = cursor.fetchone()[0]
        await context.bot.send_message(next_staff_chat_id, tr(context,'new_question', question_id=question_id, question_text=question_text))
    else:
        cursor.execute("SELECT chat_id FROM Admin LIMIT 1")
        admin_chat_id = cursor.fetchone()[0]
        await context.bot.send_message(admin_chat_id, tr(context,'no_staff_review_', question_id=question_id,question_text=question_text))


async def view_pending_questions(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'staff':
        await update.message.reply_text(tr(context, 'staff_login'))
        return

    pending_questions = get_pending_questions()
    if not pending_questions:
        await update.message.reply_text(tr(context, 'no_questions'))
        return

    response_message = tr(context, 'pending')
    for question_id, question_text, created_at in pending_questions:
        response_message += tr(
            context,
            'question',
            question_id=question_id,
            question_text=question_text,
            created_at=created_at
        )
    await update.message.reply_text(response_message)

import re

async def provide_videolink(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'staff':
        await update.message.reply_text(tr(context,'staff_login_2'))
        return

    # Extract arguments with regex for title and description in double quotes
    text = update.message.text
    match = re.match(r'^/provide_videolink (\d+) (\S+) "([^"]+)" "([^"]+)"$', text)
    
    if not match:
        await update.message.reply_text(tr(context,'usage_provide_videolink'))
        return

    question_id = int(match.group(1))
    video_link = match.group(2)
    title = match.group(3)
    description = match.group(4)
    staff_id = context.user_data['user_id']

    add_video(question_id, video_link, title, description, staff_id)
    update_question_status(question_id, 'answered')
    await update.message.reply_text(tr(context,'answer_question', question_id=question_id))
    
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
            tr(context,'answered_question', title=title,description=description,video_link=video_link),
            reply_markup=reply_markup
        )


async def handle_feedback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(':')
    action = data[0]
    video_id_or_question_id = int(data[1])
    
    if action == 'like':
        await context.bot.send_message(chat_id=query.message.chat_id, text=tr(context,'review_thanks'))
    elif action == 'dislike':
        await query.edit_message_text(text=tr(context,'answer_no_help'))
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
            await context.bot.send_message(next_staff_chat_id, tr(context,'review_required', video_id_or_question_id=video_id_or_question_id,question_text=question_text))
        else:
            cursor.execute("SELECT chat_id FROM Admin LIMIT 1")
            admin_chat_id = cursor.fetchone()[0]
            await context.bot.send_message(admin_chat_id, tr(context, 'no_staff',video_id_or_question_id=video_id_or_question_id,question_text=question_text))
    elif action == 'like_similar':
        question_id = int(data[2])
        await context.bot.send_message(chat_id=query.message.chat_id, text=tr(context,'thanks_review'))
        update_question_status(question_id, 'answered')
    elif action == 'dislike_similar':
        question_id = int(data[2])
        await query.edit_message_text(text=tr(context,'no_help_video'))
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
            await context.bot.send_message(admin_chat_id, tr(context,'no_staff_available',question_id=question_id,question_text=question_text))

async def create_user(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text(tr(context,'admin_login'))
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text(tr(context,'create_user'))
        return

    phone_number, password = args
    create_user_or_staff('user', phone_number, generate_password_hash(password))
    await update.message.reply_text(tr(context,'user_created'))

async def create_staff(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text(tr(context,'admin_login_staff'))
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text(tr(context,'create_staff'))
        return

    phone_number, password = args
    create_user_or_staff('staff', phone_number, generate_password_hash(password))
    await update.message.reply_text(tr(context,'staff_created'))

async def create_admin(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text(tr(context,'admin_login_admin'))
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text(tr(context,'create_admin'))
        return

    phone_number, password = args
    create_user_or_staff('admin', phone_number, password)
    await update.message.reply_text(tr(context,'admin_created'))

async def list_users(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text(tr(context,'user_list'))
        return

    users = list_users_or_staff('user')
    response = tr(context,'users') + "\n".join([f"ID: {user_id}, Tel: {phone}" for user_id, phone in users])
    await update.message.reply_text(response)

async def list_staff(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text(tr(context,'staff_list'))
        return

    staff = list_users_or_staff('staff')
    response = tr(context,'staff') + "\n".join([f"ID: {staff_id}, Tel: {phone}" for staff_id, phone in staff])
    await update.message.reply_text(response)

async def list_admins(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text(tr(context,'admin_list'))
        return

    admins = list_users_or_staff('admin')
    response = tr(context, 'admin') + "\n".join([f"ID: {admin_id}, Tel: {phone}" for admin_id, phone in admins])
    await update.message.reply_text(response)

async def remove_user(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text(tr(context,'remove_user'))
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text(tr(context,'remove_user_use'))
        return

    user_id = args[0]
    delete_user_or_staff('user', user_id)
    await update.message.reply_text(tr(context,'remove_user_success', user_id=user_id))

async def remove_staff(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text(tr(context,'remove_staff'))
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text(tr(context,'remove_staff_use'))
        return

    staff_id = args[0]
    delete_user_or_staff('staff', staff_id)
    await update.message.reply_text(tr(context,'remove_staff_success',staff_id= staff_id))

async def remove_admin(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text(tr(context,'remove_admin'))
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text(tr(context,'remove_admin_use'))
        return

    admin_id = args[0]
    delete_user_or_staff('admin', admin_id)
    await update.message.reply_text(tr(context,'remove_admin_success',admin_id=admin_id))


async def set_language(update: Update, context: CallbackContext) -> None:
    # Inline keyboard for language selection
    keyboard = [
        [InlineKeyboardButton("Русский", callback_data="set_lang:ru")],
        [InlineKeyboardButton("English", callback_data="set_lang:en")],
        [InlineKeyboardButton("Қазақша", callback_data="set_lang:kz")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите язык / Select a language / Тілді таңдаңыз:", reply_markup=reply_markup)


async def handle_language_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    # Extract language code from callback data
    lang_code = query.data.split(":")[1]
    chat_id = query.message.chat_id

    # Determine user type and update language
    cursor.execute("SELECT id FROM Admin WHERE chat_id = %s", (chat_id,))
    if cursor.fetchone():
        cursor.execute("UPDATE Admin SET language = %s WHERE chat_id = %s", (lang_code, chat_id))
    else:
        cursor.execute("SELECT id FROM Staff WHERE chat_id = %s", (chat_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE Staff SET language = %s WHERE chat_id = %s", (lang_code, chat_id))
        else:
            cursor.execute("SELECT id FROM User WHERE chat_id = %s", (chat_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE User SET language = %s WHERE chat_id = %s", (lang_code, chat_id))

    # Commit changes
    db.commit()
    await query.edit_message_text(f"Язык был установлен на: {lang_code.upper()} / Language set to: {lang_code.upper()} / Тіл орнатылды: {lang_code.upper()}")


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

    application.add_handler(CommandHandler("set_language", set_language))
    application.add_handler(CallbackQueryHandler(handle_language_selection, pattern="^set_lang:"))

    application.add_handler(CallbackQueryHandler(handle_feedback))

    application.run_polling()

if __name__ == "__main__":
    main()