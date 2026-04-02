import os
import pytest
import mysql.connector

# Point at the Docker MySQL instance
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'vacation_db'),
    'user': os.getenv('DB_USER', 'vacation_user'),
    'password': os.getenv('DB_PASSWORD', 'vacation_pass'),
}

# Patch app.py's DB_CONFIG so all functions connect to the same DB
import app
app.DB_CONFIG = DB_CONFIG


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe test-created rows before and after every test."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    def _clean():
        cursor.execute("DELETE FROM event_responses")
        cursor.execute("DELETE FROM vacation_days")
        cursor.execute("DELETE FROM events")
        cursor.execute("DELETE FROM holidays")
        cursor.execute("DELETE FROM team_members")
        # Keep the default 'hebo' user, remove any test users
        cursor.execute("DELETE FROM users WHERE username != 'hebo'")
        conn.commit()

    _clean()
    yield
    _clean()

    cursor.close()
    conn.close()
