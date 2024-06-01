from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext
import mysql.connector
import re
from fuzzywuzzy import fuzz

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="6067iphone",
    database="telegram_bot"
)
cursor = db.cursor()

# Define User Roles and Permissions
def create_user_or_staff(user_type, phone_number, password):
    if user_type not in ['staff', 'user', 'admin']:
        raise ValueError("Invalid user type")

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
    cursor.execute("SELECT chat_id FROM Staff WHERE chat_id IS NOT NULL")
    return [row[0] for row in cursor.fetchall()]

def get_pending_questions():
    cursor.execute("SELECT id, question_text, created_at FROM Question WHERE status = 'pending' ORDER BY created_at")
    return cursor.fetchall()

# Define command handlers
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Welcome to the bot! Use /login to authenticate. Use /help to see available commands.')

async def help_command(update: Update, context: CallbackContext) -> None:
    role = context.user_data.get('role')
    if role == 'admin':
        commands = (
            "/create_user phone_number password\n"
            "/create_staff phone_number password\n"
            "/create_admin phone_number password\n"
            "/list_users\n"
            "/list_staff\n"
            "/list_admins\n"
            "/remove_user user_id\n"
            "/remove_staff staff_id\n"
            "/remove_admin admin_id"
        )
    elif role == 'staff':
        commands = (
            "/login phone_number password\n"
            "/answer\n"
            "/provide_answer question_id video_link \"title\" \"description\"\n"
            "/view_pending_questions"
        )
    elif role == 'user':
        commands = (
            "/login phone_number password\n"
            "/ask question_text"
        )
    else:
        commands = "You need to log in first using /login phone_number password."

    await update.message.reply_text(f"Available commands:\n{commands}")

async def login(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Usage: /login <phone_number> <password>')
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
        await update.message.reply_text(f'Successfully logged in as {role}. Use /help to see available commands.')
        if role != 'admin':
            cursor.execute(f"UPDATE {role.capitalize()} SET chat_id = %s WHERE id = %s", (update.message.chat_id, user_id))
            db.commit()
            print(f"{role.capitalize()} chat_id {update.message.chat_id} saved for user_id {user_id}")
    else:
        await update.message.reply_text('Invalid phone number or password.')

def calculate_similarity(text1, text2):
    return fuzz.ratio(text1.lower(), text2.lower())

async def ask_question(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'user':
        await update.message.reply_text('You must be logged in as a user to ask a question.')
        return

    question_text = ' '.join(context.args)
    user_id = context.user_data['user_id']
    question_id = add_question(user_id, question_text)

    cursor.execute("SELECT video_link, title, description FROM Video")
    videos = cursor.fetchall()

    similar_videos = [
        (video_link, title, description) for video_link, title, description in videos
        if calculate_similarity(question_text, title) > 60 or calculate_similarity(question_text, description) > 60
    ]

    response_message = f"Your question has been submitted with ID {question_id}."
    if similar_videos:
        response_message += "\n\nSimilar videos:\n"
        for video_link, title, description in similar_videos:
            response_message += f"\nTitle: {title}\nDescription: {description}\nLink: {video_link}\n"

    staff_chat_ids = get_staff_chat_ids()
    for chat_id in staff_chat_ids:
        await context.bot.send_message(chat_id, f'New question (ID: {question_id}): {question_text}')

    await update.message.reply_text(response_message)

async def view_pending_questions(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'staff':
        await update.message.reply_text('You must be logged in as staff to view pending questions.')
        return

    pending_questions = get_pending_questions()
    if pending_questions:
        response_message = "Pending questions:\n"
        for question_id, question_text, created_at in pending_questions:
            response_message += f"\nID: {question_id}\nQuestion: {question_text}\nCreated at: {created_at}\n"
    else:
        response_message = "There are no pending questions."

    await update.message.reply_text(response_message)

async def provide_answer(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'staff':
        await update.message.reply_text('You must be logged in as a staff to provide answers.')
        return

    if len(context.args) < 4:
        await update.message.reply_text('Usage: /provide_answer <question_id> <video_link> "title" "description"')
        return

    try:
        question_id = int(context.args[0])
        video_link = context.args[1]

        match = re.match(r'"([^"]+)"\s+"([^"]+)"', ' '.join(context.args[2:]))
        if not match:
            await update.message.reply_text('Usage: /provide_answer <question_id> <video_link> "title" "description"')
            return

        title = match.group(1)
        description = match.group(2)

        staff_id = context.user_data['user_id']  # Retrieve the current staff ID from the context data

        add_video(question_id, video_link, title, description, staff_id)
        update_question_status(question_id, 'answered')

        cursor.execute("SELECT user_id FROM Question WHERE id = %s", (question_id,))
        user_id = cursor.fetchone()[0]
        cursor.execute("SELECT chat_id FROM User WHERE id = %s", (user_id,))
        user_chat_id = cursor.fetchone()[0]

        keyboard = [
            [InlineKeyboardButton("👍 Like", callback_data=f'like:{question_id}'), InlineKeyboardButton("👎 Dislike", callback_data=f'dislike:{question_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(user_chat_id, f'Your question has been answered: {title}\n{description}\n{video_link}\n\nPlease provide your feedback:', reply_markup=reply_markup)

        await update.message.reply_text('Answer has been submitted.')

    except Exception as e:
        await update.message.reply_text(f'Error providing answer: {str(e)}')


async def feedback_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    feedback, question_id = query.data.split(':')
    question_id = int(question_id)

    update_feedback(question_id, feedback)

    original_message = query.message.text
    feedback_response = ""

    if feedback == 'dislike':
        dislike_count = get_dislike_count(question_id)
        if dislike_count >= 2:
            notify_next_staff_or_admin(question_id, context)
            feedback_response = '\n\nYour feedback has been recorded and the question will be reviewed by another staff member or admin.'
        else:
            feedback_response = '\n\nYour feedback has been recorded. We will review the answer.'
    else:
        feedback_response = '\n\nThank you for your feedback!'

    await query.edit_message_text(original_message + feedback_response)
    await query.answer()

def update_feedback(question_id, feedback):
    if feedback == 'like':
        cursor.execute("UPDATE Video SET like_count = like_count + 1 WHERE question_id = %s", (question_id,))
    elif feedback == 'dislike':
        cursor.execute("UPDATE Video SET dislike_count = dislike_count + 1 WHERE question_id = %s", (question_id,))
    db.commit()

def get_dislike_count(question_id):
    cursor.execute("SELECT dislike_count FROM Video WHERE question_id = %s", (question_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def notify_next_staff_or_admin(question_id, context):
    cursor.execute("SELECT id FROM Staff WHERE dislike_count < 2 LIMIT 1")
    next_staff = cursor.fetchone()

    if next_staff:
        next_staff_id = next_staff[0]
        cursor.execute("SELECT chat_id FROM Staff WHERE id = %s", (next_staff_id,))
        chat_id = cursor.fetchone()[0]
        cursor.execute("SELECT question_text FROM Question WHERE id = %s", (question_id,))
        question_text = cursor.fetchone()[0]
        context.bot.send_message(chat_id, f'Pending review question ID: {question_id}\nQuestion: {question_text}')
    else:
        cursor.execute("SELECT chat_id FROM Admin LIMIT 1")
        admin_chat_id = cursor.fetchone()[0]
        cursor.execute("SELECT question_text FROM Question WHERE id = %s", (question_id,))
        question_text = cursor.fetchone()[0]
        context.bot.send_message(admin_chat_id, f'No staff available to review question ID: {question_id}\nQuestion: {question_text}')
    db.commit()

# Define admin command handlers
async def create_user(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Usage: /create_user <phone_number> <password>')
        return

    phone_number, password = args
    try:
        create_user_or_staff('user', phone_number, password)
        await update.message.reply_text('User created successfully.')
    except Exception as e:
        await update.message.reply_text(f'Error creating user: {str(e)}')

async def create_staff(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Usage: /create_staff <phone_number> <password>')
        return

    phone_number, password = args
    try:
        create_user_or_staff('staff', phone_number, password)
        await update.message.reply_text('Staff created successfully.')
    except Exception as e:
        await update.message.reply_text(f'Error creating staff: {str(e)}')

async def create_admin(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Usage: /create_admin <phone_number> <password>')
        return

    phone_number, password = args
    try:
        create_user_or_staff('admin', phone_number, password)
        await update.message.reply_text('Admin created successfully.')
    except Exception as e:
        await update.message.reply_text(f'Error creating admin: {str(e)}')

async def list_users(update: Update, context: CallbackContext) -> None:
    users = list_users_or_staff('user')
    response_message = "Users:\n"
    for user_id, phone_number in users:
        response_message += f"ID: {user_id}, Phone: {phone_number}\n"
    await update.message.reply_text(response_message)

async def list_staff(update: Update, context: CallbackContext) -> None:
    staff_members = list_users_or_staff('staff')
    response_message = "Staff members:\n"
    for staff_id, phone_number in staff_members:
        response_message += f"ID: {staff_id}, Phone: {phone_number}\n"
    await update.message.reply_text(response_message)

async def list_admins(update: Update, context: CallbackContext) -> None:
    admins = list_users_or_staff('admin')
    response_message = "Admins:\n"
    for admin_id, phone_number in admins:
        response_message += f"ID: {admin_id}, Phone: {phone_number}\n"
    await update.message.reply_text(response_message)

async def remove_user(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /remove_user <user_id>')
        return

    user_id = int(args[0])
    try:
        delete_user_or_staff('user', user_id)
        await update.message.reply_text('User removed successfully.')
    except Exception as e:
        await update.message.reply_text(f'Error removing user: {str(e)}')

async def remove_staff(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /remove_staff <staff_id>')
        return

    staff_id = int(args[0])
    try:
        delete_user_or_staff('staff', staff_id)
        await update.message.reply_text('Staff removed successfully.')
    except Exception as e:
        await update.message.reply_text(f'Error removing staff: {str(e)}')

async def remove_admin(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /remove_admin <admin_id>')
        return

    admin_id = int(args[0])
    try:
        delete_user_or_staff('admin', admin_id)
        await update.message.reply_text('Admin removed successfully.')
    except Exception as e:
        await update.message.reply_text(f'Error removing admin: {str(e)}')

def main() -> None:
    application = Application.builder().token("7134060419:AAHCcn5_DZ5C8P7a2gu0PhZE--Ij4AN2dbg").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("ask", ask_question))
    application.add_handler(CommandHandler("view_pending_questions", view_pending_questions))
    application.add_handler(CommandHandler("provide_answer", provide_answer))
    application.add_handler(CallbackQueryHandler(feedback_callback))

    application.add_handler(CommandHandler("create_user", create_user))
    application.add_handler(CommandHandler("create_staff", create_staff))
    application.add_handler(CommandHandler("create_admin", create_admin))
    application.add_handler(CommandHandler("list_users", list_users))
    application.add_handler(CommandHandler("list_staff", list_staff))
    application.add_handler(CommandHandler("list_admins", list_admins))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("remove_staff", remove_staff))
    application.add_handler(CommandHandler("remove_admin", remove_admin))

    application.run_polling()

if __name__ == '__main__':
    main()
