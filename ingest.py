import os
import glob
import pandas as pd
from azure.identity import DefaultAzureCredential
import struct
import pyodbc

# 1. Connect to Azure SQL securely using the existing OIDC GitHub Login token
server = os.environ['SQL_SERVER']
database = "modelinfodb"
connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server={server};Database={database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

credential = DefaultAzureCredential()
# Request an access token explicitly for Azure SQL
token_bytes = credential.get_token("https://windows.net").token.encode("utf-16-le")
token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

# 2. Open the SQL connection
conn = pyodbc.connect(connection_string, attrs_before={1213: token_struct})
cursor = conn.cursor()

# 3. Find and loop through all CSV files in your directory
csv_files = glob.glob("./*.csv")
for file_path in csv_files:
    table_name = os.path.basename(file_path).replace(".csv", "")
    print(f"Ingesting {file_path} into table '{table_name}'...")
    
    # Read CSV data into a Pandas DataFrame
    df = pd.read_csv(file_path)
    
    # Clean up column names to be database safe (remove spaces/special characters)
    df.columns = [c.replace(' ', '_').replace('-', '_') for c in df.columns]
    
    # Dynamically create the database table based on your CSV columns
    columns_schema = ", ".join([f"[{col}] NVARCHAR(MAX)" for col in df.columns])
    cursor.execute(f"DROP TABLE IF EXISTS [{table_name}]")
    cursor.execute(f"CREATE TABLE [{table_name}] ({columns_schema})")
    
    # Insert data rows efficiently in chunks
    placeholders = ", ".join(["?"] * len(df.columns))
    insert_sql = f"INSERT INTO [{table_name}] VALUES ({placeholders})"
    
    # Bulk insert rows
    cursor.executemany(insert_sql, df.values.tolist())
    conn.commit()

print("All files successfully synced to Azure SQL!")
cursor.close()
conn.close()
