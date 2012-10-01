# Database access for just_eat
from twisted.enterprise import adbapi
import settings
import sqlite3

def setup_database():
    conn = sqlite3.connect(settings.JUST_EAT_DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS places (
        id INTEGER PRIMARY KEY,
        identifier TEXT NOT NULL,
        title TEXT NOT NULL,
        address TEXT NOT NULL,
        geopoint TEXT NOT NULL,
        created INTEGER NOT NULL,
        has_chicken BOOLEAN NOT NULL
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS id_index ON places (identifier ASC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS created_index ON places (created ASC)")
    cursor.close()
    conn.close()

setup_database()

pool = adbapi.ConnectionPool("sqlite3", settings.JUST_EAT_DB_NAME)

