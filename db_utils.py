import mysql.connector
from config import DB_CONFIG, ADMIN_PASSWORD_HASH, ADMIN_PHONE

def connect():
    return mysql.connector.connect(**DB_CONFIG)

def setup_database_and_create_admin():
    try:
        # Establish a database connection
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        # Open the SQL file and execute each command for database setup
        with open("db_setup.sql", "r") as sql_file:
            sql_script = sql_file.read()

        # Split commands on semicolons and execute each one
        for command in sql_script.split(';'):
            if command.strip():  # Execute non-empty commands
                try:
                    cursor.execute(command)
                except mysql.connector.Error as err:
                    print(f"Error executing command: {err}")
                    continue  # Continue to the next command if one fails

        # Insert the initial admin after setting up the database
        cursor.execute("""
            INSERT INTO Admin (phone_number, password, chat_id)
            VALUES (%s, %s, NULL)
            ON DUPLICATE KEY UPDATE phone_number = phone_number;
        """, (ADMIN_PHONE, ADMIN_PASSWORD_HASH))

        connection.commit()
        print("Database setup and initial admin created successfully.")
    
    except mysql.connector.Error as err:
        print(f"Database setup failed: {err}")
    
    finally:
        # Ensure the cursor and connection are always closed
        cursor.close()
        connection.close()