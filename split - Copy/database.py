import sqlite3
import config

def init_db():
    try:
        conn = sqlite3.connect(config.DB_FILE) # Use the central config!
        cursor = conn.cursor()
        
        # Restored performance optimizations
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                consumer_id TEXT,
                date_original TEXT,
                date_iso TEXT,
                mru TEXT,
                file_path TEXT UNIQUE,
                folder_source TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cid ON images (consumer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date_iso ON images (date_iso)')
        conn.commit()
        conn.close()
        return True, "Success"
    except Exception as e:
        return False, str(e)

def get_db_connection():
    return sqlite3.connect(config.DB_FILE, check_same_thread=False)

def get_total_image_count():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM images")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0