from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
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
    cursor.execute("INSERT INTO Question (user_id, question_text, status, created_at, like_count, dislike_count) VALUES (%s, %s, %s, NOW(), 0, 0)", 
                   (user_id, question_text, 'pending'))
    db.commit()
    return cursor.lastrowid

def get_question_status(question_id):
    cursor.execute("SELECT status FROM Question WHERE id = %s", (question_id,))
    return cursor.fetchone()

def update_question_status(question_id, status):
    cursor.execute("UPDATE Question SET status = %s WHERE id = %s", (status, question_id))
    db.commit()

def add_video(question_id, video_link, title, description):
    cursor.execute("INSERT INTO Video (question_id, video_link, title, description) VALUES (%s, %s, %s, %s)",
                   (question_id, video_link, title, description))
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

def update_feedback(question_id, feedback):
    if feedback == 'like':
        cursor.execute("UPDATE Question SET like_count = like_count + 1 WHERE id = %s", (question_id,))
    elif feedback == 'dislike':
        cursor.execute("UPDATE Question SET dislike_count = dislike_count + 1 WHERE id = %s", (question_id,))
    db.commit()


def get_dislike_count(question_id):
    cursor.execute("SELECT dislike_count FROM Question WHERE id = %s", (question_id,))
    return cursor.fetchone()[0]

def notify_next_staff_or_admin(question_id):
    staff_chat_ids = get_staff_chat_ids()
    if staff_chat_ids:
        for chat_id in staff_chat_ids:
            if chat_id:
                try:
                    context.bot.send_message(chat_id, f'New question from user:\nQuestion ID: {question_id}\nThis question has been disliked multiple times and needs your attention.')
                except telegram.error.BadRequest as e:
                    print(f"Failed to send message to chat_id {chat_id}: {e}")
    else:
        # Notify admin if no staff available
        admin_chat_ids = [admin[1] for admin in list_users_or_staff('admin')]
        for chat_id in admin_chat_ids:
            if chat_id:
                try:
                    context.bot.send_message(chat_id, f'Unresolved question from user:\nQuestion ID: {question_id}\nThis question has been disliked multiple times and needs your attention.')
                except telegram.error.BadRequest as e:
                    print(f"Failed to send message to admin chat_id {chat_id}: {e}")

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

    # Fetch all videos from the database
    cursor.execute("SELECT video_link, title, description FROM Video")
    videos = cursor.fetchall()

    best_match = None
    best_similarity = 0

    for video in videos:
        video_link, title, description = video
        title_similarity = calculate_similarity(question_text, title)
        description_similarity = calculate_similarity(question_text, description)

        # Check similarity with title and description
        if title_similarity > best_similarity:
            best_similarity = title_similarity
            best_match = video
        
        if description_similarity > best_similarity:
            best_similarity = description_similarity
            best_match = video

    if best_match and best_similarity >= 35:
        video_link, title, description = best_match
        update_question_status(question_id, 'answered')
        await update.message.reply_text(f'Answer found: {title}\n{description}\n{video_link}')
    else:
        staff_chat_ids = get_staff_chat_ids()
        print(f"Staff chat_ids: {staff_chat_ids}")  # Debugging line
        for chat_id in staff_chat_ids:
            if chat_id:  # Ensure chat_id is valid
                try:
                    await context.bot.send_message(chat_id, f'New question from user:\nQuestion ID: {question_id}\nQuestion: {question_text}')
                except telegram.error.BadRequest as e:
                    print(f"Failed to send message to chat_id {chat_id}: {e}")  # Debugging line
        await update.message.reply_text('Your question has been submitted to the staff and is pending review.')

async def answer_question(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'staff':
        await update.message.reply_text('You must be logged in as a staff to answer questions.')
        return

    question_id = get_next_pending_question()
    if question_id:
        question_text = get_question_text(question_id)
        await update.message.reply_text(f'Next pending question (ID: {question_id}):\n{question_text}')
    else:
        await update.message.reply_text('There are no pending questions.')

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

        add_video(question_id, video_link, title, description)
        update_question_status(question_id, 'answered')

        cursor.execute("SELECT user_id FROM Question WHERE id = %s", (question_id,))
        user_id = cursor.fetchone()[0]
        cursor.execute("SELECT chat_id FROM User WHERE id = %s", (user_id,))
        user_chat_id = cursor.fetchone()[0]
        await context.bot.send_message(user_chat_id, f'Your question has been answered: {title}\n{description}\n{video_link}\n\nPlease provide your feedback using /feedback {question_id} like or /feedback {question_id} dislike.')

        await update.message.reply_text('Answer has been submitted.')

    except Exception as e:
        await update.message.reply_text(f'Error providing answer: {str(e)}')

async def view_pending_questions(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'staff':
        await update.message.reply_text('You must be logged in as a staff to view pending questions.')
        return

    pending_questions = get_pending_questions()
    if pending_questions:
        response = "\n\n".join([f"ID: {qid}, Question: {text}, Timestamp: {timestamp}" for qid, text, timestamp in pending_questions])
    else:
        response = 'No pending questions.'
    
    await update.message.reply_text(response)

# Admin-related commands
async def create_user(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Only admins can create users.')
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Usage: /create_user <phone_number> <password>')
        return

    phone_number, password = args
    create_user_or_staff('user', phone_number, password)
    await update.message.reply_text('User created successfully.')

async def create_staff(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Only admins can create staff.')
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Usage: /create_staff <phone_number> <password>')
        return

    phone_number, password = args
    create_user_or_staff('staff', phone_number, password)
    await update.message.reply_text('Staff created successfully.')

async def create_admin(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Only admins can create admins.')
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Usage: /create_admin <phone_number> <password>')
        return

    phone_number, password = args
    create_user_or_staff('admin', phone_number, password)
    await update.message.reply_text('Admin created successfully.')

async def list_users(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Only admins can list users.')
        return

    users = list_users_or_staff('user')
    user_list = "\n".join([f"ID: {user_id}, Phone: {phone_number}" for user_id, phone_number in users])
    await update.message.reply_text(f"Users:\n{user_list}")

async def list_staff(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Only admins can list staff.')
        return

    staff = list_users_or_staff('staff')
    staff_list = "\n".join([f"ID: {staff_id}, Phone: {phone_number}" for staff_id, phone_number in staff])
    await update.message.reply_text(f"Staff:\n{staff_list}")

async def list_admins(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Only admins can list admins.')
        return

    admins = list_users_or_staff('admin')
    admin_list = "\n".join([f"ID: {admin_id}, Phone: {phone_number}" for admin_id, phone_number in admins])
    await update.message.reply_text(f"Admins:\n{admin_list}")

async def remove_user(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Only admins can remove users.')
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /remove_user <user_id>')
        return

    user_id = args[0]
    delete_user_or_staff('user', user_id)
    await update.message.reply_text('User removed successfully.')

async def remove_staff(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Only admins can remove staff.')
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /remove_staff <staff_id>')
        return

    staff_id = args[0]
    delete_user_or_staff('staff', staff_id)
    await update.message.reply_text('Staff removed successfully.')

async def remove_admin(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('role') != 'admin':
        await update.message.reply_text('Only admins can remove admins.')
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /remove_admin <admin_id>')
        return

    admin_id = args[0]
    delete_user_or_staff('admin', admin_id)
    await update.message.reply_text('Admin removed successfully.')

# Helper functions
def get_next_pending_question():
    cursor.execute("SELECT id FROM Question WHERE status = 'pending' ORDER BY created_at LIMIT 1")
    result = cursor.fetchone()
    return result[0] if result else None

async def give_feedback(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data or context.user_data.get('role') != 'user':
        await update.message.reply_text('You must be logged in as a user to give feedback.')
        return

    if len(context.args) != 2:
        await update.message.reply_text('Usage: /feedback <question_id> <like|dislike>')
        return

    try:
        question_id = int(context.args[0])
        feedback = context.args[1]

        if feedback not in ['like', 'dislike']:
            await update.message.reply_text('Feedback must be "like" or "dislike".')
            return

        update_feedback(question_id, feedback)

        if feedback == 'dislike':
            dislike_count = get_dislike_count(question_id)
            if dislike_count >= 2:
                notify_next_staff_or_admin(question_id)
                await update.message.reply_text('Your feedback has been recorded and the question will be reviewed by another staff member or admin.')
            else:
                await update.message.reply_text('Your feedback has been recorded. We will review the answer.')
        else:
            await update.message.reply_text('Thank you for your feedback!')

    except Exception as e:
        await update.message.reply_text(f'Error giving feedback: {str(e)}')

def get_question_text(question_id):
    cursor.execute("SELECT question_text FROM Question WHERE id = %s", (question_id,))
    result = cursor.fetchone()
    return result[0] if result else None

# Set up the application
def main():
    application = Application.builder().token("7134060419:AAHCcn5_DZ5C8P7a2gu0PhZE--Ij4AN2dbg").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("ask", ask_question))
    application.add_handler(CommandHandler("answer", answer_question))
    application.add_handler(CommandHandler("provide_answer", provide_answer))
    application.add_handler(CommandHandler("view_pending_questions", view_pending_questions))
    application.add_handler(CommandHandler("create_user", create_user))
    application.add_handler(CommandHandler("create_staff", create_staff))
    application.add_handler(CommandHandler("create_admin", create_admin))
    application.add_handler(CommandHandler("list_users", list_users))
    application.add_handler(CommandHandler("list_staff", list_staff))
    application.add_handler(CommandHandler("list_admins", list_admins))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("remove_staff", remove_staff))
    application.add_handler(CommandHandler("remove_admin", remove_admin))
    application.add_handler(CommandHandler("feedback", give_feedback))

    application.run_polling()

if __name__ == "__main__":
    main()