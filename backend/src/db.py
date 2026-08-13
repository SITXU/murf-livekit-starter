import sqlite3
import json
import os
from datetime import datetime

# Place the database file in the same directory as this script (src)
DB_PATH = os.path.join(os.path.dirname(__file__), "agent_memory.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            language_preference TEXT,
            facts TEXT,
            last_interaction TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS calls (
            call_id TEXT PRIMARY KEY,
            user_id TEXT,
            status TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()
def get_user(user_id: str):
    """Fetch user details by their ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_id, name, language_preference, facts, last_interaction FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "user_id": row[0],
            "name": row[1],
            "language_preference": row[2],
            "facts": json.loads(row[3]) if row[3] else {},
            "last_interaction": row[4]
        }
    return None

def save_user(user_id: str, name: str, language_preference: str, facts: dict):
    """Save or update user details."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    last_interaction = datetime.now().isoformat()
    facts_str = json.dumps(facts)
    
    c.execute('''
        INSERT INTO users (user_id, name, language_preference, facts, last_interaction)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name=excluded.name,
            language_preference=excluded.language_preference,
            facts=excluded.facts,
            last_interaction=excluded.last_interaction
    ''', (user_id, name, language_preference, facts_str, last_interaction))
    
    conn.commit()
    conn.close()

def save_call(call_id: str, user_id: str, status: str):
    """Save the outcome of a call."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    
    c.execute('''
        INSERT INTO calls (call_id, user_id, status, timestamp)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(call_id) DO UPDATE SET
            status=excluded.status
    ''', (call_id, user_id, status, timestamp))
    
    conn.commit()
    conn.close()

def get_call_stats():
    """Get statistics for the calls dashboard."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute('SELECT COUNT(*) FROM calls')
        total_calls = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM calls WHERE status = "SUCCESS"')
        successful_calls = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM calls WHERE status = "FAILED"')
        failed_calls = c.fetchone()[0]
    except sqlite3.OperationalError:
        total_calls, successful_calls, failed_calls = 0, 0, 0
    
    conn.close()
    
    return {
        "total": total_calls,
        "successful": successful_calls,
        "failed": failed_calls
    }
