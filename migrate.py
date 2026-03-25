import os
import mysql.connector

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'vacation_db'),
    'user': os.getenv('DB_USER', 'vacation_user'),
    'password': os.getenv('DB_PASSWORD', 'vacation_pass')
}

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), 'migrations')


def run_migrations():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Create tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) NOT NULL PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Get already-applied versions
    cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
    applied = {row[0] for row in cursor.fetchall()}

    # Discover and sort migration files
    migration_files = sorted(
        f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql')
    )

    for filename in migration_files:
        if filename in applied:
            continue

        filepath = os.path.join(MIGRATIONS_DIR, filename)
        with open(filepath, 'r') as f:
            sql = f.read()

        print(f"Applying migration: {filename}")

        for statement in sql.split(';'):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)

        try:
            cursor.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (filename,)
            )
            conn.commit()
            print(f"  Applied successfully.")
        except mysql.connector.IntegrityError:
            # Another process already applied this migration
            conn.rollback()
            print(f"  Already applied (concurrent run).")

    cursor.close()
    conn.close()
    print("Migrations complete.")


if __name__ == '__main__':
    run_migrations()
