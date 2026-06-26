import os
import glob
import pandas as pd
from azure.identity import DefaultAzureCredential # FIXED: Changed from AzureCliCredential
import struct
import pyodbc

# 1. Connect to Azure SQL securely using Environment Variables mapped by OIDC
server = os.environ['SQL_SERVER']
database = "modelinfodb"
connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server={server};Database={database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

# Use DefaultAzureCredential to automatically process the OIDC Env vars
# FIXED: Explicitly force the credential mechanism to look up the database's exact matching tenant
credential = DefaultAzureCredential(
    tenant_id=target_tenant,
    additionally_allowed_tenants=["*"] # Allows cross-tenant execution fallback if needed
)

# FIXED: Replaced the broken/typo scope string with the exact official Azure SQL URI scope
# 1. Fetch the string token token
token_obj = credential.get_token("https://database.windows.net/.default")

# 2. Encode explicitly to UTF-16 Little Endian bytes
token_bytes = token_obj.token.encode("utf-16-le")

# FIXED: Structural binding logic to strictly prevent 64-bit Linux byte-padding alignment corruption
token_struct = struct.pack("=i", len(token_bytes)) + token_bytes


# 2. Open the SQL connection
# FIXED: Included both 1213 and 1256 token attribute definitions to satisfy ODBC Driver 18 constraints
conn = pyodbc.connect(
    connection_string, 
    attrs_before={
        1213: token_struct,
        1256: token_struct
    }
)
cursor = conn.cursor()

# OPTIMIZATION: Drastically increases bulk insert performance
cursor.fast_executemany = True

# 3. Find and loop through all CSV files in your directory
csv_files = glob.glob("./*.csv")
for file_path in csv_files:
    table_name = os.path.basename(file_path).replace(".csv", "")
    print(f"Ingesting {file_path} into table '{table_name}'...")
    
    df = pd.read_csv(file_path)
    df.columns = [c.replace(' ', '_').replace('-', '_') for c in df.columns]
    
    columns_schema = ", ".join([f"[{col}] NVARCHAR(MAX)" for col in df.columns])
    cursor.execute(f"DROP TABLE IF EXISTS [{table_name}]")
    cursor.execute(f"CREATE TABLE [{table_name}] ({columns_schema})")
    
    placeholders = ", ".join(["?"] * len(df.columns))
    insert_sql = f"INSERT INTO [{table_name}] VALUES ({placeholders})"
    
    # Bulk insert rows with fast_executemany speed boost
    cursor.executemany(insert_sql, df.values.tolist())
    conn.commit()

print("All files successfully synced to Azure SQL!")
cursor.close()
conn.close()
