import sqlite3
import sys

DB_FILENAME = "database.db"  # Change this to match your actual .db filename


def inspect_database(db_path: str):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Fetch all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print(f"No tables found in database '{db_path}'.")
            return

        print(f"=== Database File: {db_path} ===")

        for (table_name,) in tables:
            print(f"\n{'=' * 50}")
            print(f"TABLE: {table_name}")
            print(f"{'=' * 50}")

            # Get table schema (column names and types)
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns_info = cursor.fetchall()
            col_names = [col[1] for col in columns_info]

            print("Columns:", ", ".join(col_names))
            print("-" * 50)

            # Retrieve all rows
            cursor.execute(f"SELECT * FROM {table_name};")
            rows = cursor.fetchall()

            if not rows:
                print("(No records found)")
            else:
                for row_idx, row in enumerate(rows, start=1):
                    print(f"--- Row {row_idx} ---")
                    for col_name, val in zip(col_names, row):
                        print(f"  {col_name}: {val}")

        conn.close()

    except sqlite3.Error as e:
        print(f"An error occurred while reading SQLite database: {e}")


if __name__ == "__main__":
    # If a database file is passed as a command-line argument, use it; otherwise use default
    db_file = sys.argv[1] if len(sys.argv) > 1 else DB_FILENAME
    inspect_database(db_file)