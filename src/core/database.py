import sqlite3
import json
import threading
try:
    from core import config
except ImportError:
    import config


# --- Thread-local connection pool ---
# Reuse a single SQLite connection per thread instead of opening/closing + running
# 6 PRAGMAs on every single database call.  This saves ~10-20ms per call.
_thread_local = threading.local()

# Event that signals init_db() has completed.  UI reads should wait on this
# to avoid hitting an exclusive schema-migration lock and deadlocking for up to 30s.
init_db_ready = threading.Event()


def _add_column_if_missing(cursor, table_name, column_name, column_def):
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}
    if column_name not in existing:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

CURRENT_DB_SCHEMA_VERSION = 4  # Bumped for FTS5 migration

def get_db_connection():
    """Return a thread-local cached connection.  PRAGMAs execute once per thread."""
    conn = getattr(_thread_local, 'conn', None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")  # health-check
            return conn
        except Exception:
            # Connection is broken — drop it and create a new one
            try:
                conn.close()
            except Exception:
                pass
            _thread_local.conn = None

    conn = sqlite3.connect(config.DB_FILE, check_same_thread=False, timeout=30.0)
    try:
        # High performance tuning — runs ONCE per thread lifetime
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA cache_size=-64000;")  # 64MB memory cache (default is 2MB)
        cursor.execute("PRAGMA mmap_size=268435456;") # 256MB memory mapped I/O
        cursor.execute("PRAGMA temp_store=MEMORY;")
    except Exception:
        pass
    _thread_local.conn = conn
    return conn


def close_thread_connection():
    """Explicitly close the cached connection for the current thread (optional cleanup)."""
    conn = getattr(_thread_local, 'conn', None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _thread_local.conn = None

def init_db(force=False):
    """
    Initializes database tables and indexes safely.
    Skips expensive index/column checks on startup if schema version matches.
    """
    try:
        # Check if already initialized at current schema version
        if not force:
            v = get_info_value("db_schema_version", 0)
            if v == CURRENT_DB_SCHEMA_VERSION:
                return True, "Schema up to date"

        conn = get_db_connection()
        cursor = conn.cursor()
        
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

        # Schema migration for existing databases
        _add_column_if_missing(cursor, "images", "filename", "TEXT")
        _add_column_if_missing(cursor, "images", "dir_id", "INTEGER")
        _add_column_if_missing(cursor, "images", "date_iso", "TEXT")
        _add_column_if_missing(cursor, "images", "mru", "TEXT")

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cid ON images (consumer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date_iso ON images (date_iso)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dir_id ON images (dir_id)')
        
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

        # Drop redundant duplicate indexes (consumer_id is already indexed by PRIMARY KEY,
        # and meter_no is indexed by idx_meter_no)
        cursor.execute('DROP INDEX IF EXISTS idx_meter_consumer_id')
        cursor.execute('DROP INDEX IF EXISTS idx_meter_no_exact')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meter_mobile ON meter_mapping (mobile_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meter_name_nocase ON meter_mapping (name COLLATE NOCASE)')

        # Add default note options if the table is empty
        cursor.execute("SELECT COUNT(*) FROM note_options")
        if cursor.fetchone()[0] == 0:
            default_options = [("OK",), ("CHECK",), ("RECHECK",)]
            cursor.executemany("INSERT INTO note_options VALUES (?)", default_options)

        # FTS5 virtual table for instant name/address search
        # (replaces LIKE '%query%' which causes full table scans)
        try:
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS meter_mapping_fts
                USING fts5(consumer_id, name, address, content='meter_mapping', content_rowid='rowid')
            ''')
        except Exception:
            # FTS5 may not be available in all SQLite builds — graceful fallback
            pass

        conn.commit()
        
        # Mark schema version completed
        set_info_value("db_schema_version", CURRENT_DB_SCHEMA_VERSION)

        # Background worker to populate FTS if table exists but FTS is empty (never blocks UI/init_db)
        def _bg_populate_fts():
            try:
                bg_conn = sqlite3.connect(config.DB_FILE, timeout=60.0)
                bg_cursor = bg_conn.cursor()
                bg_cursor.execute("SELECT COUNT(*) FROM meter_mapping_fts")
                if bg_cursor.fetchone()[0] == 0:
                    bg_cursor.execute("SELECT COUNT(*) FROM meter_mapping")
                    if bg_cursor.fetchone()[0] > 0:
                        bg_cursor.execute("INSERT OR REPLACE INTO meter_mapping_fts(meter_mapping_fts) VALUES('rebuild')")
                        bg_conn.commit()
                bg_conn.close()
            except Exception:
                pass
        threading.Thread(target=_bg_populate_fts, daemon=True).start()

        return True, "Success"
    except Exception as e:
        return False, str(e)
    finally:
        # Signal that schema initialization is complete — safe for UI reads now
        init_db_ready.set()

def get_total_image_count(force_recount=False):
    cached = get_info_value("cached_total_images", None)
    if cached is not None and isinstance(cached, int) and cached >= 0:
        if not force_recount:
            return cached
    if not force_recount:
        # No cache exists — return 0 immediately to avoid blocking the UI thread.
        # A background thread will do the heavy count and push the real value.
        return 0
    # force_recount=True: do the count (called from background thread only)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Superfast ROWID check: for standard SQLite tables with autoincrement / standard rowid,
        # MAX(ROWID) executes in O(1) time (sub-millisecond even on 10M rows)
        cursor.execute("SELECT MAX(ROWID) FROM images")
        row = cursor.fetchone()
        if row and row[0] is not None and row[0] > 0:
            count = row[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM images")
            count = cursor.fetchone()[0]
        set_info_value("cached_total_images", count)
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
        return json.loads(row[0]) if row else default
    except:
        return default

def set_info_value(key, value):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO db_info VALUES (?, ?)", (key, json.dumps(value)))
        conn.commit()
    except:
        pass

def get_additional_folders():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_path FROM additional_folders")
        rows = cursor.fetchall()
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
    except:
        pass

def get_all_notes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT consumer_id, note, remarks FROM notes")
        rows = cursor.fetchall()
        return {row[0]: {'note': row[1], 'remarks': row[2]} for row in rows}
    except:
        return {}

def save_note(consumer_id, note, remarks):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO notes VALUES (?, ?, ?)", (consumer_id, note, remarks))
        conn.commit()
    except:
        pass
        
def delete_note(consumer_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE consumer_id=?", (consumer_id,))
        conn.commit()
    except:
        pass

def get_note_options():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT option_text FROM note_options")
        rows = cursor.fetchall()
        return [row[0] for row in rows]
    except:
        return []

def add_note_option(option):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO note_options VALUES (?)", (option,))
        conn.commit()
    except:
        pass
        
def get_meter_number(consumer_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT meter_no FROM meter_mapping WHERE consumer_id = ?", (consumer_id,))
        row = cursor.fetchone()
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
        return row[0] if row else None
    except:
        return None


def search_consumers_by_name(name_query, limit=200):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        q = name_query.strip()
        if not q:
            return []
        # Try FTS5 first — O(1) token lookup instead of full table scan
        try:
            # FTS5 MATCH with wildcard suffix for prefix matching
            fts_query = " ".join(f'"{w}"*' for w in q.split() if w)
            cursor.execute(
                """
                SELECT m.consumer_id, m.meter_no, m.name, m.address,
                       m.mobile_number, m.contractual_load, m.class
                FROM meter_mapping_fts fts
                JOIN meter_mapping m ON m.rowid = fts.rowid
                WHERE meter_mapping_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, int(limit))
            )
        except Exception:
            # Fallback to LIKE if FTS5 is not available
            cursor.execute(
                """
                SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class
                FROM meter_mapping
                WHERE name LIKE ? COLLATE NOCASE
                ORDER BY name COLLATE NOCASE ASC
                LIMIT ?
                """,
                (f"%{q}%", int(limit))
            )
        rows = cursor.fetchall()
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
        # Rebuild FTS5 index to keep name search in sync
        try:
            cursor.execute("INSERT OR REPLACE INTO meter_mapping_fts(meter_mapping_fts) VALUES('rebuild')")
            conn.commit()
        except Exception:
            pass
        set_info_value("cached_consumer_count", len(data_to_insert))
    except Exception as e:
        print(f"DATABASE ERROR in update_meter_mapping: {e}")

def get_consumer_count(force_recount=False):
    cached = get_info_value("cached_consumer_count", None)
    if cached is not None and isinstance(cached, int) and cached >= 0:
        if not force_recount:
            return cached
    # On 50K consumers, SELECT COUNT(*) takes only ~10ms.
    # Query directly to prevent false 0 counts that trigger 'Consumer data not updated' warnings.
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM meter_mapping")
        row = cursor.fetchone()
        count = row[0] if row else 0
        set_info_value("cached_consumer_count", count)
        return count
    except:
        return 0

def has_meter_data():
    cached = get_info_value("cached_consumer_count", None)
    if cached is not None and isinstance(cached, int):
        return cached > 0
    # Fast O(1) existence check in sub-millisecond time
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM meter_mapping LIMIT 1")
        return cursor.fetchone() is not None
    except:
        return False


def get_all_consumer_profiles():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT consumer_id, meter_no, name, address, mobile_number
            FROM meter_mapping
            """
        )
        rows = cursor.fetchall()
        return [
            {
                "consumer_id": r[0] or "",
                "meter_no": r[1] or "",
                "name": r[2] or "",
                "address": r[3] or "",
                "mobile_number": r[4] or "",
            }
            for r in rows
        ]
    except:
        return []
