import sqlite3
import json
from datetime import datetime

def format_datetime(dt_str):
    if dt_str:
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return str(dt_str)
    return None

# Connect to database
conn = sqlite3.connect('challenges.db')
cursor = conn.cursor()

print("=== CHALLENGES DATABASE VIEWER ===\n")

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"Tables: {[t[0] for t in tables]}\n")

# Dictionary to store all data
database_data = {}

# View each table and collect data
for table in tables:
    table_name = table[0]
    print(f"--- {table_name.upper()} ---")
    
    # Get column names
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Get data
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    # Convert rows to list of dictionaries
    table_data = []
    if rows:
        for row in rows:
            row_dict = {}
            for i, value in enumerate(row):
                col_name = columns[i]
                if 'date' in col_name.lower() or 'at' in col_name.lower():
                    row_dict[col_name] = format_datetime(value)
                else:
                    row_dict[col_name] = value
            table_data.append(row_dict)
            print(f"  {row}")
    else:
        print("  (empty)")
    
    # Store table data
    database_data[table_name] = {
        "columns": columns,
        "row_count": len(table_data),
        "data": table_data
    }
    
    print()

conn.close()

# Save to JSON file
with open('database_export.json', 'w', encoding='utf-8') as f:
    json.dump(database_data, f, indent=2, ensure_ascii=False, default=str)

print(f"\n=== DATABASE EXPORTED TO 'database_export.json' ===")
print("File contains all tables with their structure and data in JSON format.")
