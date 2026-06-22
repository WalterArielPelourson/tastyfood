# config.py


GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY" # ¡REEMPLAZA CON TU API KEY REAL!
# ENVIO_COSTO = 10000.0 # Esta línea se ha eliminado/comentado, ahora se gestiona desde la DB
MAX_PEDIDOS_POR_FRANJA_HORARIA = 5
RADIO_ENVIO_CUADRAS = 200
CUADRA_METROS = 100

DB_NAME = 'restaurante.db' # ASEGÚRATE DE QUE ESTE NOMBRE ES CORRECTO Y CONSISTENTE

# Coordenadas de la sucursal (ejemplo: Buenos Aires). Se actualizarán si Google Maps las encuentra.
SUCURSAL_LAT = -34.6037
SUCURSAL_LON = -58.3816

# Horario de operación por defecto (si no se carga de Google Maps)
#HORA_APERTURA = "12:00"
#HORA_CIERRE = "23:00"
INTERVALO_FRANJAS_MINUTOS = 15

# config.py
# Ahora definimos una lista de listas [Apertura, Cierre]
HORARIOS_TURNOS = [
    ["08:00", "11:00"],
    ["19:00", "23:30"]
]

# Mantener estas para compatibilidad de otras funciones si es necesario, 
# pero la lógica principal usará la lista.
HORA_APERTURA = HORARIOS_TURNOS[0][0] 
HORA_CIERRE = HORARIOS_TURNOS[-1][1]




# Nueva configuración para la empresa por defecto a la que los clientes hacen pedidos
DEFAULT_COMPANY_FOR_ORDERS = 2 # ID de la empresa por defecto para pedidos de clientes