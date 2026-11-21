from pathlib import Path
import sqlite3

DB_PATH = Path("data/shop.db")


def initialize_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS order_items (
                item_id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(order_id),
                product_id INTEGER NOT NULL REFERENCES products(product_id),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price REAL NOT NULL CHECK (unit_price >= 0)
            );

            INSERT OR IGNORE INTO customers VALUES
                (1, 'Ava'), (2, 'Noah');

            INSERT OR IGNORE INTO orders VALUES
                (101, 1), (102, 2);

            INSERT OR IGNORE INTO products VALUES
                (10, 'Keyboard'), (11, 'Mouse'), (12, 'USB Hub');

            INSERT OR IGNORE INTO order_items VALUES
                (1, 101, 10, 1, 120.00),
                (2, 101, 11, 2, 80.00),
                (3, 102, 12, 1, 40.00);
        """)


def total_revenue(db_path: Path = DB_PATH) -> float:
    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            "SELECT COALESCE(SUM(quantity * unit_price), 0) FROM order_items"
        ).fetchone()

    return float(result[0])


if __name__ == "__main__":
    initialize_db()
    print(f"Database ready: {DB_PATH}")
    print(f"Total demo revenue: ${total_revenue():.2f}")