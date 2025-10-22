import os
import psycopg2
import sys

def read_sql_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def execute_sql_commands(connection, sql_commands, ignore_errors=False):
    cursor = connection.cursor()
    for command in sql_commands.split(';'):
        if command.strip():
            try:
                cursor.execute(command)
                print(f"Executed: {command.strip()[:50]}...")
            except psycopg2.Error as e:
                if ignore_errors and 'already exists' in str(e):
                    print(f"Notice: {e}")
                else:
                    print(f"Error executing: {command.strip()[:50]}...")
                    print(f"Error message: {e}")
                    if not ignore_errors:
                        cursor.close()
                        raise
    cursor.close()

def main():
    # PostgreSQL connection parameters for initial connection - using port 50333 for the Docker container
    initial_params = {
        'host': 'localhost',
        'port': '5432',  # Updated to use Docker-exposed port
        'user': 'postgres',  # Superuser role
        'password': 'postgres'  # Superuser password
    }
    
    # Step 1: Connect to PostgreSQL and create the database
    print("Connecting to PostgreSQL...")
    try:
        # First connection to create database
        conn = psycopg2.connect(**initial_params)
        conn.autocommit = True  # Required for database creation
        
        # Run database creation script
        print("Creating database...")
        db_creation_sql = read_sql_file('migrations/create_db.sql')
        execute_sql_commands(conn, db_creation_sql, ignore_errors=True)
        conn.close()
        
        # Step 2: Connect to the newly created database
        db_params = {
            'host': 'localhost',
            'port': '5432',  # Updated to use Docker-exposed port
            'user': 'postgres',  # Still using superuser
            'password': 'postgres',
            'database': 'DBopenAPI'
        }
        
        print("Connecting to DBopenAPI database...")
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        
        # Step 3: Create schema
        print("Creating schema...")
        schema_sql = read_sql_file('migrations/create_schema.sql')
        execute_sql_commands(conn, schema_sql, ignore_errors=True)
        
        # Step 4: Create user and grant privileges
        print("Creating user and granting privileges...")
        user_sql = read_sql_file('migrations/create_user.sql')
        execute_sql_commands(conn, user_sql, ignore_errors=True)
        
        # Step 5: Create tables
        print("Creating tables...")
        tables_sql = read_sql_file('migrations/create_tables.sql')
        execute_sql_commands(conn, tables_sql, ignore_errors=True)
        
        # Step 6: Create company full data table if not already included
        print("Ensuring company_full_data table is created...")
        company_full_sql = read_sql_file('migrations/create_company_full_data.sql')
        execute_sql_commands(conn, company_full_sql, ignore_errors=True)
        
        conn.close()
        
        print("All database objects created successfully!")
        print("\nYour .env file is already configured with:")
        print("DB_HOST=localhost")
        print("DB_PORT=50333")
        print("DB_NAME=DBopenAPI")
        print("DB_SCHEMA=openapi_schema")
        print("DB_USER=openapi_user")
        print("DB_PASSWORD=openapi_password")
        
        print("\nNow you can start your application with:")
        print("uvicorn app.main:app --reload")
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
