import sqlite3
conn = sqlite3.connect('restaurante.db')
cursor = conn.cursor()
# Borramos el pedido que tiene el texto mal
cursor.execute("DELETE FROM pedidos WHERE horario_entrega LIKE '%Cerrado%'")
conn.commit()
conn.close()
print("Base de datos limpia de pedidos corruptos.")