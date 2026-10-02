import os
import sqlite3
import sys
import pandas as pd


def db_to_excel(db_path: str):
    # Clean quotes if path was drag-and-dropped into terminal
    db_path = db_path.strip("\"'")

    if not os.path.exists(db_path):
        print(f"\n[Error] Database file not found at: {db_path}")
        return

    # Create output excel path in the same directory as the database file
    db_dir, db_filename = os.path.split(os.path.abspath(db_path))
    db_name = os.path.splitext(db_filename)[0]
    excel_path = os.path.join(db_dir, f"{db_name}_export.xlsx")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all non-system tables
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE"
        " 'sqlite_%';"
    )
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        print(f"\n[Error] No user tables found inside database: {db_path}")
        conn.close()
        return

    print(f"\nFound tables: {', '.join(tables)}")

    # Write each table to a separate sheet
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for table_name in tables:
            df = pd.read_sql_query(f"SELECT * FROM `{table_name}`", conn)
            df.to_excel(
                writer, sheet_name=table_name.capitalize(), index=False
            )
            print(
                f" -> Written sheet '{table_name.capitalize()}' ({len(df)} rows)"
            )

    conn.close()
    print(f"\n[Success] Excel file created: {excel_path}")


if __name__ == "__main__":
    # Check if DB path was passed via command line argument
    if len(sys.argv) > 1:
        input_db = sys.argv[1]
    else:
        # Prompt user if no argument was supplied
        input_db = input("Enter the full path to your .db file: ")

    db_to_excel(input_db)