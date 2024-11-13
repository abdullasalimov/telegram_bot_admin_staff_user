import mysql.connector
from config import DB_CONFIG

def connect():
    return mysql.connector.connect(**DB_CONFIG)

def setup_database():
    connection = connect()
    cursor = connection.cursor()

    # Open the SQL file and execute each command
    with open("db_setup.sql", "r") as sql_file:
        sql_script = sql_file.read()

    # Split commands on semicolons and execute each one
    for command in sql_script.split(';'):
        if command.strip():  # Execute non-empty commands
            try:
                cursor.execute(command)
            except mysql.connector.Error as err:
                print(f"Error: {err}")
    
    connection.commit()
    cursor.close()
    connection.close()
