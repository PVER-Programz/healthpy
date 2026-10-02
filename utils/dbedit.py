import os
import sqlite3
import sys


def get_db_connection(db_path: str):
    """Establishes connection to the database file."""
    clean_path = db_path.strip("\"'")
    if not os.path.exists(clean_path):
        print(f"\n[Error] Database file not found at: {clean_path}")
        return None
    try:
        conn = sqlite3.connect(clean_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn
    except sqlite3.Error as e:
        print(f"\n[Error] Failed to connect to database: {e}")
        return None


def clear_all_alerts(conn):
    """Deletes all records from the alerts table and resets autoincrement ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM alerts;")
    count = cursor.fetchone()[0]

    if count == 0:
        print("\n[Info] Alerts table is already empty.")
        return

    confirm = (
        input(f"\nAre you sure you want to delete all {count} alert(s)? (y/N): ")
        .strip()
        .lower()
    )
    if confirm == "y":
        cursor.execute("DELETE FROM alerts;")
        # Reset ID sequence for alerts table
        cursor.execute(
            "DELETE FROM sqlite_sequence WHERE name='alerts';"
        )
        conn.commit()
        print(f"\n[Success] Cleared all {count} alert(s) from the database.")
    else:
        print("\n[Cancelled] No alerts were deleted.")


def view_alerts_summary(conn):
    """Displays current alert count and latest alerts."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM alerts;")
    total = cursor.fetchone()[0]

    print(f"\n--- Current Alerts (Total: {total}) ---")
    if total > 0:
        cursor.execute(
            "SELECT id, patient_name, severity, message, timestamp FROM alerts ORDER BY id DESC LIMIT 5;"
        )
        rows = cursor.fetchall()
        print("Latest 5 alerts:")
        for r in rows:
            print(
                f"  [{r['id']}] {r['timestamp']} | {r['patient_name']} | {r['severity']} - {r['message']}"
            )


def update_patient_status(conn):
    """Updates status or risk score for a patient."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, patient_name, risk_score, status FROM patients;")
    patients = cursor.fetchall()

    if not patients:
        print("\n[Info] No patients found in the database.")
        return

    print("\n--- Patients ---")
    for p in patients:
        print(
            f"  ID: {p['id']} | Name: {p['patient_name']} | Risk Score: {p['risk_score']} | Status: {p['status']}"
        )

    p_id = input("\nEnter Patient ID to update: ").strip()
    new_status = input(
        "Enter new status (e.g. 'Stable', 'Nurse Alert', 'General Observation'): "
    ).strip()
    new_score = input("Enter new risk score (or press Enter to skip): ").strip()

    if new_score:
        cursor.execute(
            "UPDATE patients SET status = ?, risk_score = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
            (new_status, float(new_score), p_id),
        )
    else:
        cursor.execute(
            "UPDATE patients SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
            (new_status, p_id),
        )

    conn.commit()
    print("\n[Success] Patient updated.")


def main():
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = input("Enter path to your .db file (e.g. vigilance.db): ")

    conn = get_db_connection(db_path)
    if not conn:
        return

    while True:
        print("\n==============================")
        print("    VIGILANCE DB MANAGER      ")
        print("==============================")
        print("1. CLEAR ALL ALERTS")
        print("2. View Alerts Summary")
        print("3. Update Patient Status / Risk Score")
        print("4. Exit")

        choice = input("\nSelect an option (1-4): ").strip()

        if choice == "1":
            clear_all_alerts(conn)
        elif choice == "2":
            view_alerts_summary(conn)
        elif choice == "3":
            update_patient_status(conn)
        elif choice == "4":
            print("\nClosing connection. Goodbye!")
            conn.close()
            break
        else:
            print("\nInvalid option. Please enter 1, 2, 3, or 4.")


if __name__ == "__main__":
    main()