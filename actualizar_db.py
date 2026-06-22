import sqlite3
from config import DB_NAME

def actualizar():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Agregamos las 3 columnas necesarias para la nueva lógica
    columnas = [
        ("es_combo_fijo", "INTEGER DEFAULT 0"),
        ("min_items", "INTEGER DEFAULT 1"),
        ("max_items", "INTEGER DEFAULT 1")
    ]
    
    for nombre, tipo in columnas:
        try:
            cursor.execute(f"ALTER TABLE promociones ADD COLUMN {nombre} {tipo}")
            print(f"Columna {nombre} agregada.")
        except sqlite3.OperationalError:
            print(f"La columna {nombre} ya existe.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    actualizar()