import gzip
import json
import sqlite3
import os
from pathlib import Path
import time

def main():
    db_path = Path("db.sqlite3")
    customer_gz = Path("data/customer.json.gz")
    spending_gz = Path("data/customer_spending.json.gz")

    if not customer_gz.exists() or not spending_gz.exists():
        print("Data files not found.")
        return

    print("Connecting to database...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop tables if they exist
    print("Dropping existing tables...")
    cursor.execute("DROP TABLE IF EXISTS customer")
    cursor.execute("DROP TABLE IF EXISTS customer_spending")
    conn.commit()

    # Create tables
    print("Creating tables...")
    cursor.execute("""
        CREATE TABLE customer (
            customer_id INTEGER PRIMARY KEY,
            city TEXT,
            birth_year INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE customer_spending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            billing_year_month TEXT,
            bill_amount REAL,
            data_usage REAL
        )
    """)
    conn.commit()

    # Insert customer data
    print("Inserting customer data...")
    start_time = time.time()
    customers_to_insert = []
    with gzip.open(customer_gz, "rt", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            customers_to_insert.append((item["customer_id"], item["city"], item["birth_year"]))
            if len(customers_to_insert) >= 50000:
                cursor.executemany("INSERT INTO customer (customer_id, city, birth_year) VALUES (?, ?, ?)", customers_to_insert)
                conn.commit()
                customers_to_insert.clear()
        if customers_to_insert:
            cursor.executemany("INSERT INTO customer (customer_id, city, birth_year) VALUES (?, ?, ?)", customers_to_insert)
            conn.commit()
    print(f"Customer data inserted in {time.time() - start_time:.2f} seconds.")

    # Insert customer spending data
    print("Inserting customer spending data...")
    start_time = time.time()
    spendings_to_insert = []
    with gzip.open(spending_gz, "rt", encoding="utf-8") as f:
        count = 0
        for line in f:
            item = json.loads(line)
            spendings_to_insert.append((item["customer_id"], item["billing_year_month"], item["bill_amount"], item["data_usage"]))
            count += 1
            if len(spendings_to_insert) >= 50000:
                cursor.executemany("INSERT INTO customer_spending (customer_id, billing_year_month, bill_amount, data_usage) VALUES (?, ?, ?, ?)", spendings_to_insert)
                conn.commit()
                spendings_to_insert.clear()
                print(f"Processed {count} spending records...")
        if spendings_to_insert:
            cursor.executemany("INSERT INTO customer_spending (customer_id, billing_year_month, bill_amount, data_usage) VALUES (?, ?, ?, ?)", spendings_to_insert)
            conn.commit()
    print(f"Customer spending data inserted in {time.time() - start_time:.2f} seconds.")

    # Create indices
    print("Creating indices...")
    start_time = time.time()
    cursor.execute("CREATE INDEX idx_spending_customer_id ON customer_spending(customer_id)")
    conn.commit()
    print(f"Indices created in {time.time() - start_time:.2f} seconds.")

    # Show count
    cursor.execute("SELECT COUNT(*) FROM customer")
    cust_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM customer_spending")
    spend_count = cursor.fetchone()[0]
    print(f"Total customers: {cust_count}")
    print(f"Total spending records: {spend_count}")

    conn.close()
    print("Data loading completed successfully!")

if __name__ == "__main__":
    main()
