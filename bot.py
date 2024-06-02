from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
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
    # Increment total questions received count for the staff member
    cursor.execute("UPDATE Staff SET total_questions_received = total_questions_received + 1 WHERE id = %s", (staff_id,))
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
            "/view_pending_questions\n"
            "/view_staff_stats"
        )
    elif role == 'user':
        commands = (
            "/login phone_number password\n"
            "/ask question_text\n"
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

    await update.message.reply_text(response_message)

    # Notify the first staff in ascending order of id
    next_staff_id = get_next_staff_id()
    if next_staff_id:
        cursor.execute("SELECT chat_id FROM Staff WHERE id = %s", (next_staff_id,))
        next_staff_chat_id = cursor.fetchone()[0]
        await context.bot.send_message(next_staff_chat_id, f'New question (ID: {question_id}): {question_text}')
    else:
        cursor.execute("SELECT chat_id FROM Admin LIMIT 1")
        admin_chat_id = cursor.fetchone()[0]
        await context.bot.send_message(admin_chat_id, f'No staff available to review question ID: {question_id}\nQuestion: {question_text}')


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
        await update.message.reply_text('You must be logged in as staff to provide an answer.')
        return

    if len(context.args) < 4:
        await update.message.reply_text('Usage: /provide_answer <question_id> <video_link> "<title>" "<description>"')
        return

    try:
        question_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text('Invalid question_id. It should be an integer.')
        return

    video_link = context.args[1]
    if not re.match(r'^(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+$', video_link):
        await update.message.reply_text('Invalid video link. It should be a valid YouTube URL.')
        return

    # Extract title and description by joining the remaining arguments and splitting them properly
    remaining_args = ' '.join(context.args[2:])
    try:
        title, description = re.findall(r'"(.*?)"', remaining_args)
    except ValueError:
        await update.message.reply_text('Title and description must be enclosed in double quotes.')
        return

    staff_id = context.user_data['user_id']

    add_video(question_id, video_link, title, description, staff_id)
    update_question_status(question_id, 'answered')
    await update.message.reply_text(f'The answer for question ID {question_id} has been provided.')

    cursor.execute("SELECT user_id FROM Question WHERE id = %s", (question_id,))
    user_id = cursor.fetchone()[0]
    cursor.execute("SELECT chat_id FROM User WHERE id = %s", (user_id,))
    user_chat_id = cursor.fetchone()[0]
    await context.bot.send_message(user_chat_id, f'Your question has been answered.\nTitle: {title}\nDescription: {description}\nLink: {video_link}')

    # Show buttons for like or dislike
    keyboard = [
        [InlineKeyboardButton("👍", callback_data=f"like:{question_id}"), InlineKeyboardButton("👎", callback_data=f"dislike:{question_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(user_chat_id, "Do you like this answer?", reply_markup=reply_markup)

async def feedback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    feedback_type, question_id = query.data.split(':')
    question_id = int(question_id)

    if feedback_type == 'like':
        await query.answer("Glad you liked it!")
    elif feedback_type == 'dislike':
        await query.answer("We're sorry you didn't like it. We will reassign your question to another staff member.")

        cursor.execute("SELECT staff_id FROM Video WHERE question_id = %s", (question_id,))
        current_staff_id = cursor.fetchone()[0]

        # Delete the video entry and update question status
        cursor.execute("DELETE FROM Video WHERE question_id = %s", (question_id,))
        update_question_status(question_id, 'pending')
        db.commit()

        # Reassign to the next staff member
        next_staff_id = get_next_staff_id(current_staff_id)
        if next_staff_id:
            cursor.execute("SELECT chat_id FROM Staff WHERE id = %s", (next_staff_id,))
            next_staff_chat_id = cursor.fetchone()[0]
            cursor.execute("SELECT question_text FROM Question WHERE id = %s", (question_id,))
            question_text = cursor.fetchone()[0]
            await context.bot.send_message(next_staff_chat_id, f'New reassigned question (ID: {question_id}): {question_text}')
        else:
            cursor.execute("SELECT chat_id FROM Admin LIMIT 1")
            admin_chat_id = cursor.fetchone()[0]
            await context.bot.send_message(admin_chat_id, f'No staff available to review reassigned question ID: {question_id}\nQuestion: {question_text}')

async def reassign_question_to_next_staff(question_id, current_staff_id, context):
    next_staff_id = get_next_staff_id(current_staff_id)
    if next_staff_id:
        cursor.execute("SELECT chat_id FROM Staff WHERE id = %s", (next_staff_id,))
        next_staff_chat_id = cursor.fetchone()[0]
        cursor.execute("SELECT question_text FROM Question WHERE id = %s", (question_id,))
        question_text = cursor.fetchone()[0]
        await context.bot.send_message(next_staff_chat_id, f'Reassigned question (ID: {question_id}): {question_text}\nUse the command: /provide_answer {question_id} <video_link> "<title>" "<description>"')
    else:
        # If no next staff member, notify the admin
        cursor.execute("SELECT chat_id FROM Admin LIMIT 1")
        admin_chat_id = cursor.fetchone()[0]
        cursor.execute("SELECT question_text FROM Question WHERE id = %s", (question_id,))
        question_text = cursor.fetchone()[0]
        await context.bot.send_message(admin_chat_id, f'No other staff available to review question ID: {question_id}\nQuestion: {question_text}')

async def view_staff_stats(update: Update, context: CallbackContext) -> None:
    if 'role' not in context.user_data or context.user_data.get('role') != 'admin':
        await update.message.reply_text('You must be logged in as an admin to view staff stats.')
        return

    staff_id = context.user_data['user_id']
    cursor.execute("SELECT total_questions_received, positive_feedback, negative_feedback FROM Staff WHERE id = %s", (staff_id,))
    stats = cursor.fetchone()
    total_questions_received, positive_feedback, negative_feedback = stats

    response_message = f"Staff Stats:\nTotal questions received: {total_questions_received}\nPositive feedback received: {positive_feedback}\nNegative feedback received: {negative_feedback}"
    await update.message.reply_text(response_message)


# Admin commands
async def create_user(update: Update, context: CallbackContext) -> None:
    await create_entity(update, context, 'user')

async def create_staff(update: Update, context: CallbackContext) -> None:
    await create_entity(update, context, 'staff')

async def create_admin(update: Update, context: CallbackContext) -> None:
    await create_entity(update, context, 'admin')

async def create_entity(update: Update, context: CallbackContext, entity_type: str) -> None:
    if 'role' not in context.user_data or context.user_data.get('role') != 'admin':
        await update.message.reply_text(f'You must be logged in as an admin to create a {entity_type}.')
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text(f'Usage: /create_{entity_type} <phone_number> <password>')
        return

    phone_number, password = args
    create_user_or_staff(entity_type, phone_number, password)
    await update.message.reply_text(f'{entity_type.capitalize()} created successfully.')

async def list_users(update: Update, context: CallbackContext) -> None:
    await list_entities(update, context, 'user')

async def list_staff(update: Update, context: CallbackContext) -> None:
    await list_entities(update, context, 'staff')

async def list_admins(update: Update, context: CallbackContext) -> None:
    await list_entities(update, context, 'admin')

async def list_entities(update: Update, context: CallbackContext, entity_type: str) -> None:
    if 'role' not in context.user_data or context.user_data.get('role') != 'admin':
        await update.message.reply_text(f'You must be logged in as an admin to list {entity_type}s.')
        return

    entities = list_users_or_staff(entity_type)
    response_message = f"{entity_type.capitalize()}s:\n"
    for entity_id, phone_number in entities:
        response_message += f"ID: {entity_id}, Phone number: {phone_number}\n"

    await update.message.reply_text(response_message)

async def remove_user(update: Update, context: CallbackContext) -> None:
    await remove_entity(update, context, 'user')

async def remove_staff(update: Update, context: CallbackContext) -> None:
    await remove_entity(update, context, 'staff')

async def remove_admin(update: Update, context: CallbackContext) -> None:
    await remove_entity(update, context, 'admin')

async def remove_entity(update: Update, context: CallbackContext, entity_type: str) -> None:
    if 'role' not in context.user_data or context.user_data.get('role') != 'admin':
        await update.message.reply_text(f'You must be logged in as an admin to remove a {entity_type}.')
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text(f'Usage: /remove_{entity_type} <{entity_type}_id>')
        return

    entity_id = int(args[0])
    delete_user_or_staff(entity_type, entity_id)
    await update.message.reply_text(f'{entity_type.capitalize()} removed successfully.')

def main():
    application = Application.builder().token('7134060419:AAHCcn5_DZ5C8P7a2gu0PhZE--Ij4AN2dbg').build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("login", login))

    application.add_handler(CommandHandler("ask", ask_question))
    application.add_handler(CommandHandler("view_pending_questions", view_pending_questions))
    application.add_handler(CommandHandler("provide_answer", provide_answer))
    application.add_handler(CommandHandler("view_staff_stats", view_staff_stats))

    application.add_handler(CommandHandler("create_user", create_user))
    application.add_handler(CommandHandler("create_staff", create_staff))
    application.add_handler(CommandHandler("create_admin", create_admin))
    application.add_handler(CommandHandler("list_users", list_users))
    application.add_handler(CommandHandler("list_staff", list_staff))
    application.add_handler(CommandHandler("list_admins", list_admins))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("remove_staff", remove_staff))
    application.add_handler(CommandHandler("remove_admin", remove_admin))

    # Handler for callback queries (e.g., like/dislike feedback)
    application.add_handler(CallbackQueryHandler(feedback))

    application.run_polling()

if __name__ == '__main__':
    main()