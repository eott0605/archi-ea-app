import os
import glob
import pandas as pd
import struct
import pyodbc
from azure.identity import DefaultAzureCredential

# =========================
# CONFIG
# =========================
server = os.environ['SQL_SERVER']
database = "modelinfodb"
CHUNK_SIZE = 2000   

# Connection string (token-based auth)
connection_string = (
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server={server};"
    f"Database={database};"
    f"Encrypt=yes;"
    f"TrustServerCertificate=no;"
    f"Connection Timeout=30;"
)

# =========================
# AUTHENTICATION
# =========================
credential = DefaultAzureCredential()

token_obj = credential.get_token("https://database.windows.net/.default")
token_bytes = token_obj.token.encode("utf-16-le")
token_struct = struct.pack("=i", len(token_bytes)) + token_bytes

# =========================
# DB CONNECTION
# =========================
conn = pyodbc.connect(
    connection_string, 
    attrs_before={
        1213: token_struct,
        1256: token_struct
    }
)

cursor = conn.cursor()
cursor.fast_executemany = True

# =========================
# INGESTION LOGIC
# =========================
csv_files = glob.glob("./*.csv")

for file_path in csv_files:
    table_name = os.path.basename(file_path).replace(".csv", "")
    print(f"Ingesting {file_path} into table '{table_name}'...")
    
    # --- Read only header first to define schema ---
    df_sample = pd.read_csv(file_path, nrows=1)
    df_sample.columns = [
        c.replace(' ', '_').replace('-', '_') for c in df_sample.columns
    ]

    columns = df_sample.columns.tolist()

    columns_schema = ", ".join([f"[{col}] NVARCHAR(255)" for col in columns])

    # Drop + recreate (fine at your scale)
    cursor.execute(f"DROP TABLE IF EXISTS [{table_name}]")
    cursor.execute(f"CREATE TABLE [{table_name}] ({columns_schema})")
    conn.commit()
    
    placeholders = ", ".join(["?"] * len(df.columns))
    insert_sql = f"INSERT INTO [{table_name}] VALUES ({placeholders})"

    total_rows = 0

    # CHUNKED LOAD (big improvement)
    for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
        chunk.columns = columns  # ensure consistent names

        # 🚀 Still using list conversion (acceptable at your scale)
        values = chunk.values.tolist()

        cursor.executemany(insert_sql, values)
        conn.commit()

        total_rows += len(values)
        print(f"  -> Inserted {total_rows} rows so far...")
    
    print(f"✅ Finished loading {total_rows} rows into [{table_name}]")

# =========================
# CLEANUP
# =========================
cursor.close()
conn.close()

print("\n🎉 All files successfully synced to Azure SQL!")
