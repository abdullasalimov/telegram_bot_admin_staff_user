import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Load environment variables from the .env file
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

# Load initial admin credentials
ADMIN_PHONE = os.getenv('ADMIN_PHONE')
# Hash the initial admin password
ADMIN_PASSWORD_HASH = generate_password_hash(os.getenv('ADMIN_PASSWORD'))

# Calculate similarity
SIMILARITY = 60