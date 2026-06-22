import sqlite3
from config import DB_NAME

def migrar():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("Iniciando migración de items_pedido...")
    
    # 1. Renombramos la tabla vieja
    cursor.execute("ALTER TABLE items_pedido RENAME TO items_pedido_old")
    
    # 2. Creamos la tabla nueva permitiendo que id_plato sea NULL y agregando id_promocion
    cursor.execute("""
        CREATE TABLE items_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pedido INTEGER NOT NULL,
            id_plato INTEGER, -- Ahora permite vacíos
            id_promocion INTEGER, -- Nueva columna para las promos
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL
        )
    """)
    
    # 3. Copiamos los datos viejos a la nueva
    cursor.execute("""
        INSERT INTO items_pedido (id, id_pedido, id_plato, cantidad, precio_unitario)
        SELECT id, id_pedido, id_plato, cantidad, precio_unitario FROM items_pedido_old
    """)
    
    # 4. Borramos la tabla vieja
    cursor.execute("DROP TABLE items_pedido_old")
    
    conn.commit()
    conn.close()
    print("¡Migración exitosa! Ya podés borrar este archivo.")

if __name__ == "__main__":
    migrar()