import sqlite3

try:
    conn = sqlite3.connect('data/willguard.db')
    with open('db_out.txt', 'w') as f:
        f.write("--- RECENT NOTIFICATIONS ---\n")
        cursor = conn.execute("SELECT contact_id, status, twilio_sid FROM notifications ORDER BY created_at DESC LIMIT 5")
        for row in cursor.fetchall():
            f.write(f"Contact ID: {row[0]} | Status: {row[1]} | SID: {row[2]}\n")
            
        f.write("\n--- EMERGENCY CONTACTS ---\n")
        cursor = conn.execute("SELECT id, name, phone FROM emergency_contacts ORDER BY id DESC LIMIT 5")
        for row in cursor.fetchall():
            f.write(f"ID: {row[0]} | Name: {row[1]} | Phone: {row[2]}\n")
            
    conn.close()
except Exception as e:
    print("Error:", e)
