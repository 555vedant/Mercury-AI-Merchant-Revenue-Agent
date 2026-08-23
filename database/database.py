import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "mercury.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            total_orders INTEGER DEFAULT 0,
            total_spend REAL DEFAULT 0,
            total_profit REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS negotiations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            final_price REAL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()


def create_customer(customer_id):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO customers (customer_id) VALUES (?)",
        (customer_id,)
    )
    conn.commit()
    conn.close()


def get_customer(customer_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM customers WHERE customer_id = ?",
        (customer_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_customer(customer_id, spend, profit):
    conn = get_connection()
    conn.execute(
        """
        UPDATE customers
        SET total_orders = total_orders + 1,
            total_spend = total_spend + ?,
            total_profit = total_profit + ?
        WHERE customer_id = ?
        """,
        (spend, profit, customer_id)
    )
    conn.commit()
    conn.close()


def save_negotiation(customer_id, sku, final_price, status):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO negotiations
        (customer_id, sku, final_price, status)
        VALUES (?, ?, ?, ?)
        """,
        (customer_id, sku, final_price, status)
    )
    conn.commit()
    conn.close()


def save_payment(customer_id, order_id, amount, status):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO payments
        (customer_id, order_id, amount, status)
        VALUES (?, ?, ?, ?)
        """,
        (customer_id, order_id, amount, status)
    )
    conn.commit()
    conn.close()


def save_audit(event, details):
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_events (event, details) VALUES (?, ?)",
        (event, details)
    )
    conn.commit()
    conn.close()