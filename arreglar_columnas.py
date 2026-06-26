import sqlite3
from config import DB_NAME

def corregir():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("Añadiendo columnas faltantes a la tabla promociones...")
    
    # Lista de columnas nuevas a agregar
    nuevas_columnas = [
        ("es_combo_fijo", "INTEGER DEFAULT 0"),
        ("min_items", "INTEGER DEFAULT 1"),
        ("max_items", "INTEGER DEFAULT 1")
    ]
    
    for nombre, tipo in nuevas_columnas:
        try:
            cursor.execute(f"ALTER TABLE promociones ADD COLUMN {nombre} {tipo}")
            print(f"Columna '{nombre}' agregada con éxito.")
        except sqlite3.OperationalError:
            print(f"La columna '{nombre}' ya existe, omitiendo.")

    conn.commit()
    conn.close()
    print("Proceso finalizado.")

if __name__ == "__main__":
    corregir()