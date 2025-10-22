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
    # PostgreSQL connection parameters for initial connection
    initial_params = {
        'host': 'localhost',
        'port': '5432',
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
            'port': '5432',
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
        
        conn.close()
        
        print("Updating .env file with new connection string...")
        # Update .env file
        env_file_path = '.env'
        new_db_url = "postgresql://openapi_user:openapi_password@localhost:5432/DBopenAPI?options=-csearch_path%3Dopenapi_schema"
        
        with open(env_file_path, 'r') as env_file:
            env_content = env_file.read()
        
        # Replace the DATABASE_URL line
        env_content = env_content.replace(
            'DATABASE_URL=postgresql://postgres:postgres@localhost:5432/openAPI_db', 
            f'DATABASE_URL={new_db_url}'
        )
        
        with open(env_file_path, 'w') as env_file:
            env_file.write(env_content)
            
        print("Migration completed successfully!")
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
