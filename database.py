import sqlite3
import json
import config


def _add_column_if_missing(cursor, table_name, column_name, column_def):
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}
    if column_name not in existing:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        
        # New directories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS directories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dir_path TEXT UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                consumer_id TEXT,
                date_original TEXT,
                date_iso TEXT,
                mru TEXT,
                filename TEXT,
                dir_id INTEGER,
                UNIQUE(filename, dir_id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cid ON images (consumer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date_iso ON images (date_iso)')
        
        # Other tables...
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS db_info (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS additional_folders (
                folder_path TEXT PRIMARY KEY
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                consumer_id TEXT PRIMARY KEY,
                note TEXT,
                remarks TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS note_options (
                option_text TEXT PRIMARY KEY
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meter_mapping (
                consumer_id TEXT PRIMARY KEY,
                meter_no TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meter_no ON meter_mapping (meter_no)')

        # Ensure newer fields exist for richer search and details support.
        _add_column_if_missing(cursor, "meter_mapping", "name", "TEXT")
        _add_column_if_missing(cursor, "meter_mapping", "address", "TEXT")
        _add_column_if_missing(cursor, "meter_mapping", "mobile_number", "TEXT")
        _add_column_if_missing(cursor, "meter_mapping", "contractual_load", "TEXT")
        _add_column_if_missing(cursor, "meter_mapping", "class", "TEXT")

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meter_consumer_id ON meter_mapping (consumer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meter_no_exact ON meter_mapping (meter_no)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meter_mobile ON meter_mapping (mobile_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meter_name_nocase ON meter_mapping (name COLLATE NOCASE)')

        # Add default note options if the table is empty
        cursor.execute("SELECT COUNT(*) FROM note_options")
        if cursor.fetchone()[0] == 0:
            default_options = [("OK",), ("CHECK",), ("RECHECK",)]
            cursor.executemany("INSERT INTO note_options VALUES (?)", default_options)

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

# --- Functions for new tables ---

def get_info_value(key, default=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM db_info WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return json.loads(row[0]) if row else default
    except:
        return default

def set_info_value(key, value):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO db_info VALUES (?, ?)", (key, json.dumps(value)))
        conn.commit()
        conn.close()
    except:
        pass

def get_additional_folders():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_path FROM additional_folders")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
    except:
        return []

def save_additional_folders(folders):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM additional_folders")
        if folders:
            cursor.executemany("INSERT INTO additional_folders VALUES (?)", [(f,) for f in folders])
        conn.commit()
        conn.close()
    except:
        pass

def get_all_notes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT consumer_id, note, remarks FROM notes")
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: {'note': row[1], 'remarks': row[2]} for row in rows}
    except:
        return {}

def save_note(consumer_id, note, remarks):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO notes VALUES (?, ?, ?)", (consumer_id, note, remarks))
        conn.commit()
        conn.close()
    except:
        pass
        
def delete_note(consumer_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE consumer_id=?", (consumer_id,))
        conn.commit()
        conn.close()
    except:
        pass

def get_note_options():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT option_text FROM note_options")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
    except:
        return []

def add_note_option(option):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO note_options VALUES (?)", (option,))
        conn.commit()
        conn.close()
    except:
        pass
        
def get_meter_number(consumer_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT meter_no FROM meter_mapping WHERE consumer_id = ?", (consumer_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None


def get_consumer_profile(consumer_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class
            FROM meter_mapping
            WHERE consumer_id = ?
            """,
            (consumer_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "consumer_id": row[0],
            "meter_no": row[1],
            "name": row[2],
            "address": row[3],
            "mobile_number": row[4],
            "contractual_load": row[5],
            "class": row[6],
        }
    except:
        return None

def get_consumer_by_meter(meter_no):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT consumer_id FROM meter_mapping WHERE meter_no = ?", (meter_no,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None


def search_consumers_by_name(name_query, limit=200):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class
            FROM meter_mapping
            WHERE name LIKE ? COLLATE NOCASE
            ORDER BY name COLLATE NOCASE ASC
            LIMIT ?
            """,
            (f"%{name_query.strip()}%", int(limit))
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "consumer_id": r[0],
                "meter_no": r[1],
                "name": r[2],
                "address": r[3],
                "mobile_number": r[4],
                "contractual_load": r[5],
                "class": r[6],
            }
            for r in rows
        ]
    except:
        return []


def search_consumers_by_mobile(mobile_number, limit=200):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class
            FROM meter_mapping
            WHERE mobile_number = ?
            ORDER BY name COLLATE NOCASE ASC
            LIMIT ?
            """,
            (mobile_number.strip(), int(limit))
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "consumer_id": r[0],
                "meter_no": r[1],
                "name": r[2],
                "address": r[3],
                "mobile_number": r[4],
                "contractual_load": r[5],
                "class": r[6],
            }
            for r in rows
        ]
    except:
        return []

def update_meter_mapping(mapping_dict):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # You might want to clear the table first if this is a complete refresh
        cursor.execute("DELETE FROM meter_mapping") 

        data_to_insert = []
        for consumer_id, payload in mapping_dict.items():
            if isinstance(payload, dict):
                data_to_insert.append((
                    str(consumer_id).strip(),
                    str(payload.get("meter_no", "")).strip(),
                    str(payload.get("name", "")).strip(),
                    str(payload.get("address", "")).strip(),
                    str(payload.get("mobile_number", "")).strip(),
                    str(payload.get("contractual_load", "")).strip(),
                    str(payload.get("class", "")).strip(),
                ))
            else:
                data_to_insert.append((
                    str(consumer_id).strip(),
                    str(payload).strip(),
                    "",
                    "",
                    "",
                    "",
                    "",
                ))

        cursor.executemany(
            """
            INSERT OR REPLACE INTO meter_mapping
            (consumer_id, meter_no, name, address, mobile_number, contractual_load, class)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            data_to_insert
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DATABASE ERROR in update_meter_mapping: {e}")

def has_meter_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM meter_mapping")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except:
        return False
