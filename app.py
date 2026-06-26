# 1. Importaciones de librerías estándar
import mysql.connector
import os
import sys
import sqlite3
import json
import math
import secrets  # Necesario para los tokens de seguimiento
import requests
import urllib.parse
import mercadopago
import base64 # <--- AGREGA ESTA LÍNEA AL PRINCIPIO DEL ARCHIVO
from datetime import datetime, timedelta, time
# Hora
import pytz

from datetime import datetime, timedelta, time

# 2. Importaciones de Flask y extensiones
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, current_app, abort,render_template_string
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# 3. Importaciones de módulos locales (tus archivos)
from models import Usuario, Plato, Pedido 
#from config import (
#    GOOGLE_MAPS_API_KEY, MAX_PEDIDOS_POR_FRANJA_HORARIA,
#    RADIO_ENVIO_CUADRAS, CUADRA_METROS, DB_NAME,
#    SUCURSAL_LAT, SUCURSAL_LON, HORA_APERTURA, HORA_CIERRE, INTERVALO_FRANJAS_MINUTOS,
#    DEFAULT_COMPANY_FOR_ORDERS
#)
# Busca esta sección al principio de app.py
from config import (
    GOOGLE_MAPS_API_KEY, MAX_PEDIDOS_POR_FRANJA_HORARIA,
    RADIO_ENVIO_CUADRAS, CUADRA_METROS, DB_NAME,
    SUCURSAL_LAT, SUCURSAL_LON, HORA_APERTURA, HORA_CIERRE, 
    INTERVALO_FRANJAS_MINUTOS, DEFAULT_COMPANY_FOR_ORDERS,
    HORARIOS_TURNOS  # <--- AGREGA ESTA LÍNEA AQUÍ
)


VALOR_PUNTO_POR_PESO = 0.01  # Significa que $100 = 1 punto

# 4. INSTANCIACIÓN DE LA APP (Debe ir antes de cualquier configuración de app.config)
app = Flask(__name__)
app.secret_key = 'super_secreto_de_casa_comida_web_202024' 




# 5. Configuración de subida de imágenes
# Esto detecta la ruta real de tu carpeta sin importar dónde esté el proyecto
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'platos')

# ... (después de los imports y de crear la instancia 'app')

# Configuración de subida de imágenes
UPLOAD_FOLDER = 'static/uploads/platos'

# ESTA ES LA LÍNEA QUE TE FALTA O ESTÁ MAL UBICADA:
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Asegurar que la carpeta exista
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Ahora la función ya puede encontrar ALLOWED_EXTENSIONS
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Crear la carpeta si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 6. Inicializar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message = "Por favor, inicie sesión para acceder a esta página."
login_manager.login_message_category = "warning"

# 7. Constantes globales
DEFAULT_ENVIO_COSTO = 500.00
DEFAULT_PAGO_REPARTIDOR_POR_ENVIO = 300.00


# Si estamos en PythonAnywhere usamos = ?, si no usamos ?
if os.getenv('PYTHONANYWHERE_DOMAIN'):
    PL = "= ?" 
else:
    PL = "?"

# 8. Equivalencia: 1 punto = $1 peso de descuento (puedes ajustarlo)
VALOR_PESO_POR_PUNTO_CANJE = 1.0


# Configuración Hora
ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

# Busca estas funciones y asegúrate de que se vean así:
def get_now_arg():
    """Retorna el objeto datetime actual con la zona horaria de Argentina."""
    return datetime.now(ARG_TZ)

def get_now_iso():
    """Retorna la fecha y hora actual en string formato YYYY-MM-DD HH:MM:SS para la DB."""
    # Usamos el formato estándar de SQLite para que las comparaciones funcionen bien
    return get_now_arg().strftime('%Y-%m-%d %H:%M:= ?')


# --- Funciones de Base de Datos ---
#def conectar_db():
#    conn = sqlite3.connect(DB_NAME)
#    conn.row_factory = sqlite3.Row 
#    return conn




def conectar_db():
    # Detectamos si la App corre en PythonAnywhere
    if os.getenv('PYTHONANYWHERE_DOMAIN'):
        # CONFIGURACIÓN PARA PRODUCCIÓN (MySQL)
        conn = mysql.connector.connect(
            host="WalterArielPelourson.mysql.pythonanywhere-services.com",
            user="WalterArielPelourson",
            password="TU_CONTRASEÑA_DE_DATABASE", # La que creas en el panel de PA
            database="WalterArielPelourson$restaurante"
        )
        return conn
    else:
        # CONFIGURACIÓN PARA TU PC (SQLite)
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

# NUEVA FUNCIÓN: Úsala siempre para obtener el cursor
def obtener_cursor(conn):
    if os.getenv('PYTHONANYWHERE_DOMAIN'):
        # En MySQL, dictionary=True hace que funcione igual que Row de SQLite
        return conn.cursor(dictionary=True)
    else:
        return conn.cursor()


def crear_tablas():
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS platos (
            id_plato INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT NOT NULL, descripcion TEXT, 
            precio REAL NOT NULL, 
            activo INTEGER DEFAULT 1, 
            id_empresa INTEGER, 
            rubro TEXT,
            imagen TEXT)
        """)
    cursor.execute("CREATE TABLE IF NOT EXISTS repartidores (id_repartidor INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, apellido TEXT NOT NULL, telefono TEXT, activo INTEGER DEFAULT 1, id_empresa INTEGER)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE, -- <--- NUEVA COLUMNA
            cliente_nombre TEXT NOT NULL,
            cliente_apellido TEXT NOT NULL,
            direccion_entrega TEXT NOT NULL,
            es_envio INTEGER NOT NULL,
            horario_entrega TEXT NOT NULL,
            costo_envio REAL NOT NULL,
            costo_total REAL NOT NULL,
            forma_pago TEXT NOT NULL,
            estado_pago TEXT NOT NULL DEFAULT 'Pendiente',
            estado_envio TEXT DEFAULT 'Recibido',
            fecha_creacion TEXT NOT NULL,
            fecha_pago TEXT,
            lat_cliente REAL,
            lon_cliente REAL,
            id_repartidor INTEGER,
            id_empresa INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            id_empresa INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT NOT NULL UNIQUE, 
            telefono TEXT, 
            direccion TEXT, -- Seguiremos guardando la dirección completa aquí para compatibilidad
            calle TEXT,
            altura TEXT,
            localidad TEXT,
            provincia TEXT,
            activo INTEGER DEFAULT 1
        )
    """)
    
    # Dentro de crear_tablas() en app.py
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promociones (
            id_promocion INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio_total REAL NOT NULL,
            activo INTEGER DEFAULT 1,
            id_empresa INTEGER,
            imagen TEXT,
            FOREIGN KEY(id_empresa) REFERENCES empresas(id_empresa)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promocion_platos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_promocion INTEGER,
            id_plato INTEGER,
            cantidad INTEGER DEFAULT 1,
            FOREIGN KEY(id_promocion) REFERENCES promociones(id_promocion),
            FOREIGN KEY(id_plato) REFERENCES platos(id_plato)
        )
    """)
    
    #cursor.execute("CREATE TABLE IF NOT EXISTS items_pedido (id INTEGER PRIMARY KEY AUTOINCREMENT, id_pedido INTEGER NOT NULL, id_plato INTEGER NOT NULL, cantidad INTEGER NOT NULL, precio_unitario REAL NOT NULL)")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items_pedido (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        id_pedido INTEGER NOT NULL, 
        id_plato INTEGER, -- Quitamos el NOT NULL
        id_promocion INTEGER, -- Agregamos esta columna
        cantidad INTEGER NOT NULL, 
        precio_unitario REAL NOT NULL)""")

    cursor.execute("CREATE TABLE IF NOT EXISTS ingresos_egresos (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, monto REAL NOT NULL, descripcion TEXT, fecha_hora TEXT NOT NULL, id_pedido_origen INTEGER, id_repartidor_origen INTEGER, id_empresa INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS configuracion (clave TEXT PRIMARY KEY, valor TEXT, id_empresa INTEGER)")
    #cursor.execute("CREATE TABLE IF NOT EXISTS empresas (id_empresa INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, telefono TEXT, direccion TEXT, activo INTEGER DEFAULT 1)")
    cursor.execute("CREATE TABLE IF NOT EXISTS roles (id_rol INTEGER PRIMARY KEY AUTOINCREMENT, nombre_rol TEXT NOT NULL UNIQUE)")
    cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (id_usuario INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL, nombre TEXT NOT NULL, apellido TEXT NOT NULL, id_rol INTEGER NOT NULL, id_empresa INTEGER, activo INTEGER DEFAULT 1, primer_login_requerido INTEGER DEFAULT 1)")
    
    # Dentro de crear_tablas() en app.py
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plato_modificadores (
            id_modificador INTEGER PRIMARY KEY AUTOINCREMENT,
            id_plato INTEGER NOT NULL,
            nombre TEXT NOT NULL, -- Ej: "Punto de la carne", "Agregados"
            tipo TEXT CHECK( tipo IN ('radio', 'checkbox') ) NOT NULL, -- radio = obligatorio elegir uno, checkbox = múltiples
            obligatorio INTEGER DEFAULT 0, -- 1 = Sí, 0 = No
            FOREIGN KEY(id_plato) REFERENCES platos(id_plato)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plato_opciones (
            id_opcion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_modificador INTEGER NOT NULL,
            nombre TEXT NOT NULL, -- Ej: "Bien cocida", "Bacon"
            precio_extra REAL DEFAULT 0, -- Ej: 500.00
            FOREIGN KEY(id_modificador) REFERENCES plato_modificadores(id_modificador)
        )
    """)

    # Tabla para guardar qué modificadores eligió el cliente en su pedido
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items_pedido_modificadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_item_pedido INTEGER NOT NULL,
            nombre_modificador TEXT, -- Ej: "Punto de carne"
            nombre_opcion TEXT, -- Ej: "A punto"
            precio_pagado REAL, -- Guardamos el precio del extra en ese momento
            FOREIGN KEY(id_item_pedido) REFERENCES items_pedido(id)
        )
    """)
    
    # Dentro de crear_tablas() en app.py

    # 1. Tabla de Clientes (CRM)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            apellido TEXT,
            telefono TEXT UNIQUE, -- El teléfono será la clave del cliente
            email TEXT,
            puntos INTEGER DEFAULT 0,
            id_empresa INTEGER,
            fecha_registro TEXT
        )
    """)

    # 2. Tabla de Cupones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cupones (
            id_cupon INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL, -- Ej: 'BIENVENIDA20'
            tipo TEXT CHECK( tipo IN ('porcentaje', 'monto') ) NOT NULL,
            valor REAL NOT NULL, -- Ej: 20 (para 20%) o 500 (para $500)
            minimo_compra REAL DEFAULT 0,
            activo INTEGER DEFAULT 1,
            id_empresa INTEGER
        )
    """)
    
    # 1. Tabla de Materia Prima (Insumos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insumos (
            id_insumo INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            unidad_medida TEXT, -- Ej: 'kg', 'unidades', 'litros'
            stock_actual REAL DEFAULT 0,
            stock_minimo REAL DEFAULT 0, -- Para alertas
            precio_compra REAL DEFAULT 0, -- Para calcular el costo real del plato
            id_empresa INTEGER,
            FOREIGN KEY(id_empresa) REFERENCES empresas(id_empresa)
        )
    """)

    # 2. Tabla de Recetas (Relación Plato -> Insumos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recetas (
            id_receta INTEGER PRIMARY KEY AUTOINCREMENT,
            id_plato INTEGER,
            id_insumo INTEGER,
            cantidad_requerida REAL, -- Ej: 0.200 (para 200g de carne)
            FOREIGN KEY(id_plato) REFERENCES platos(id_plato),
            FOREIGN KEY(id_insumo) REFERENCES insumos(id_insumo)
        )
    """)

    # 3. Tabla para Insumos de los Modificadores (Ej: El insumo que gasta el 'Extra Bacon')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opciones_insumos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_opcion INTEGER, -- Vinculado a plato_opciones
            id_insumo INTEGER,
            cantidad_requerida REAL,
            FOREIGN KEY(id_opcion) REFERENCES plato_opciones(id_opcion),
            FOREIGN KEY(id_insumo) REFERENCES insumos(id_insumo)
        )
    """)
    
    # Dentro de crear_tablas() en app.py
    try:
        cursor.execute("ALTER TABLE empresas ADD COLUMN horarios_json TEXT")
    except sqlite3.OperationalError:
        pass # Ya existe


    # MIGRACIÓN: Agregar id_cliente y descuento_aplicado a pedidos
    #numero de celular de usuarios
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN telefono TEXT")
    except:
        pass # Ya existe

    try:
        cursor.execute("ALTER TABLE empresas ADD COLUMN mp_access_token TEXT")
    except:
        pass
            
    
    try:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN cupon_codigo TEXT")
    except:
        pass
        
    try:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN eta_minutos INTEGER")
        cursor.execute("ALTER TABLE pedidos ADD COLUMN fecha_salida_reparto TEXT")
    except:
        pass


    try:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN id_cliente INTEGER")
        cursor.execute("ALTER TABLE pedidos ADD COLUMN descuento_aplicado REAL DEFAULT 0")
        cursor.execute("ALTER TABLE pedidos ADD COLUMN telefono_cliente TEXT") # <--- Importante para CRM
    except:
        pass    
        
    # Migraciones
    cursor.execute("PRAGMA table_info(pedidos)")
    cols = [col[1] for col in cursor.fetchall()]
    if 'estado_envio' not in cols: cursor.execute("ALTER TABLE pedidos ADD COLUMN estado_envio TEXT DEFAULT 'Recibido'")
    
    cursor.execute("INSERT OR IGNORE INTO roles (id_rol, nombre_rol) VALUES (1, 'super_admin'), (2, 'admin_empresa'), (3, 'empleado'), (4, 'repartidor')")
    
    # MIGRACIÓN: Por si la tabla ya existe, intentamos añadir la columna
    # Dentro de crear_tablas() en app.py, agrega esta migración:
    try:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN pago_repartidor_status TEXT DEFAULT 'Pendiente'")
    except sqlite3.OperationalError:
        pass # Ya existe
    
    # Dentro de crear_tablas() en app.py, añade estas columnas de tiempo:
    try:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN fecha_preparacion TEXT")
        cursor.execute("ALTER TABLE pedidos ADD COLUMN fecha_despacho TEXT")
        cursor.execute("ALTER TABLE pedidos ADD COLUMN fecha_entrega TEXT")
    except sqlite3.OperationalError:
        pass # Ya existen

    #Repartidor Usuario
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN id_repartidor_vinculado INTEGER")
    except:
        pass
    
    
    
    try:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN token TEXT UNIQUE")
    except sqlite3.OperationalError:
        pass # La columna ya existe
    
    try:
        cursor.execute("ALTER TABLE platos ADD COLUMN imagen TEXT")
    except sqlite3.OperationalError:
        pass 
    
    for col in ['calle', 'altura', 'localidad', 'provincia']:
        try:
            cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass 
        
    # Dentro de crear_tablas, añade estas migraciones:
    try:
        cursor.execute("ALTER TABLE empresas ADD COLUMN lat REAL")
        cursor.execute("ALTER TABLE empresas ADD COLUMN lon REAL")
    except sqlite3.OperationalError:
        pass # Ya existen
    
    
    # --- BLOQUE DE MIGRACIÓN AUTOMÁTICA PARA PROMOCIONES ---
    try:
        # Intentamos agregar las 3 columnas una por una
        cursor.execute("ALTER TABLE promociones ADD COLUMN es_combo_fijo INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE promociones ADD COLUMN min_items INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE promociones ADD COLUMN max_items INTEGER DEFAULT 1")
        print("Columnas de Modo Combo agregadas con éxito.")
    except sqlite3.OperationalError:
        # Si da error es porque las columnas ya existen, así que no hacemos nada
        pass
    
   
    # En app.py, dentro de crear_tablas()
    try:
        cursor.execute("ALTER TABLE platos ADD COLUMN precio_oferta REAL DEFAULT NULL")
    except:
        pass
    
    
    conn.commit(); conn.close()




#@login_manager.user_loader
##def load_user(user_id):
#    conn = conectar_db(); cursor = conn.cursor()
#    # Usamos LEFT JOIN para asegurar que traiga el nombre del rol
#    cursor.execute("""
#        SELECT u.*, r.nombre_rol 
#        FROM usuarios u 
#        LEFT JOIN roles r ON u.id_rol = r.id_rol 
#        WHERE u.id_usuario = ?
#    """, (user_id,))
#    u = cursor.fetchone(); conn.close()
#    
#    if u: 
#        # Si por alguna razón nombre_rol es None, le asignamos un string vacío para evitar errores
#        n_rol = u['nombre_rol'] if u['nombre_rol'] else ""
#        
#        return Usuario(
#            id_usuario=u['id_usuario'], 
#            email=u['email'], 
#            password=u['password'], 
#            nombre=u['nombre'], 
#            apellido=u['apellido'], 
#            id_rol=u['id_rol'], 
#            id_empresa=u['id_empresa'], 
#            activo=u['activo'], 
#            primer_login_requerido=u['primer_login_requerido'], 
#            nombre_rol=n_rol, # <--- IMPORTANTE
#            id_repartidor_vinculado=u['id_repartidor_vinculado'],
#            telefono=u['telefono']
#        )
#    return None

@login_manager.user_loader
def load_user(user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Usamos f-string para meter la variable PL ({PL})
    query = f"""
        SELECT u.*, r.nombre_rol 
        FROM usuarios u 
        LEFT JOIN roles r ON u.id_rol = r.id_rol 
        WHERE u.id_usuario = {PL}
    """
    
    cursor.execute(query, (user_id,))
    u = cursor.fetchone()
    conn.close()
    
    if u: 
        # Aseguramos que u sea un diccionario (para MySQL) o un Row (para SQLite)
        n_rol = u['nombre_rol'] if u['nombre_rol'] else ""
        return Usuario(
            id_usuario=u['id_usuario'], 
            email=u['email'], 
            password=u['password'], 
            nombre=u['nombre'], 
            apellido=u['apellido'], 
            id_rol=u['id_rol'], 
            id_empresa=u['id_empresa'], 
            activo=u['activo'], 
            primer_login_requerido=u['primer_login_requerido'], 
            nombre_rol=n_rol,
            id_repartidor_vinculado=u['id_repartidor_vinculado'],
            telefono=u['telefono']
        )
    return None




def verificar_disponibilidad_plato(id_plato, cantidad_solicitada=1):
    """
    Verifica si hay stock suficiente en la tabla 'insumos' para cubrir 
    la receta base de un plato multiplicado por la cantidad solicitada.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Buscamos los insumos requeridos por la receta base del plato
    cursor.execute("""
        SELECT i.nombre, i.stock_actual, r.cantidad_requerida
        FROM recetas r
        JOIN insumos i ON r.id_insumo = i.id_insumo
        WHERE r.id_plato = ?
    """, (id_plato,))
    
    ingredientes = cursor.fetchall()
    conn.close()
    
    # Si no tiene receta cargada, asumimos que hay stock (o podrías decidir lo contrario)
    if not ingredientes:
        return True, None

    for ing in ingredientes:
        total_necesario = ing['cantidad_requerida'] * cantidad_solicitada
        if ing['stock_actual'] < total_necesario:
            # Retornamos Falso y el nombre del ingrediente que falta
            return False, ing['nombre']
            
    return True, None



# --- Helpers ---

@app.context_processor
def inject_helpers():
    return dict(cargar_configuracion=cargar_configuracion)


def calcular_tiempo_ruta_osrm(lat_origen, lon_origen, lat_destino, lon_destino):
    """
    Calcula el tiempo de viaje en auto/moto usando calles reales (OSRM).
    Retorna los minutos estimados.
    """
    # Formato OSRM: lon,lat;lon,lat
    url = f"http://router.project-osrm.org/route/v1/driving/{lon_origen},{lat_origen};{lon_destino},{lat_destino}?overview=false"
    
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['code'] == 'Ok':
            # 'duration' viene en segundos, pasamos a minutos
            segundos = data['routes'][0]['duration']
            minutos = round(segundos / 60)
            # Añadimos un margen de 5 minutos por semáforos/estacionamiento
            return minutos + 5
    except Exception as e:
        print(f"Error calculando ruta: {e}")
    
    return None # Si falla, el sistema usará un valor por defecto


def get_company_filter_conditions_and_params(table_alias=''):
    cond, params = [], []
    if current_user.is_authenticated and not current_user.has_role('super_admin'):
        col = f"{table_alias}.id_empresa" if table_alias else "id_empresa"
        cond.append(f"{col} = ?"); params.append(current_user.id_empresa)
    return cond, params

def get_pago_repartidor(id_empresa=None):
    # Si no pasan empresa, usamos la del usuario o la de por defecto
    if id_empresa is None:
        id_empresa = current_user.id_empresa if (current_user.is_authenticated and current_user.id_empresa) else DEFAULT_COMPANY_FOR_ORDERS
    
    # Buscamos en la DB la clave 'PAGO_REPARTIDOR'
    costo = cargar_configuracion('PAGO_REPARTIDOR', str(DEFAULT_PAGO_REPARTIDOR_POR_ENVIO), id_empresa)
    return float(costo)

def obtener_coordenadas(direccion):
    """
    Busca coordenadas de forma GRATUITA usando OpenStreetMap (Nominatim).
    No requiere API Key ni tarjeta de crédito.
    """
    # 1. Limpieza y preparación de la dirección
    # Eliminamos espacios extra y aseguramos que termine en Argentina
    direccion_limpia = direccion.strip()
    if not direccion_limpia.lower().endswith("argentina"):
        direccion_busqueda = f"{direccion_limpia}, Argentina"
    else:
        direccion_busqueda = direccion_limpia
    
    # 2. URL de Nominatim (OpenStreetMap)
    url = "https://nominatim.openstreetmap.org/search"
    
    # 3. Parámetros de la consulta
    params = {
        'q': direccion_busqueda,
        'format': 'json',
        'limit': 1,
        'addressdetails': 1
    }
    
    # 4. Cabeceras (User-Agent es OBLIGATORIO para Nominatim)
    headers = {
        'User-Agent': 'RestauranteMultiSabor/1.0 (contacto@tusitio.com)' 
    }
    
    try:
        print(f"--- INICIANDO BÚSQUEDA GEOGRÁFICA ---")
        print(f"Buscando dirección: {direccion_busqueda}")
        
        # Realizamos la petición con un timeout para que no se quede colgada la app
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            print(f"ÉXITO: Ubicación encontrada en Lat: {lat}, Lon: {lon}")
            return lat, lon
        else:
            print(f"AVISO: Nominatim no encontró resultados para: {direccion_busqueda}")
            
    except Exception as e:
        print(f"ERROR en conexión de mapas: {e}")
        
    # Si falla, devolvemos None para que el sistema sepa que no pudo validar la distancia
    return None, None


def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    """Calcula la distancia en metros entre dos puntos."""
    radio_tierra = 6371000  # Radio en metros
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radio_tierra * c



#def obtener_franjas_disponibles(id_empresa=None):
#    # 1. Traer configuración (puedes usar los de config.py o cargar de DB)
#    h_apertura = HORA_APERTURA  # Ej: "11:00"
#    h_cierre = HORA_CIERRE      # Ej: "23:00"
#    intervalo = INTERVALO_FRANJAS_MINUTOS  # Ej: 15
    
#    franjas = []
#    ahora = datetime.now()
#    hoy = ahora.date()

#    # Convertir strings de config a objetos datetime para hoy
#    apertura_dt = datetime.combine(hoy, time.fromisoformat(h_apertura))
#    cierre_dt = datetime.combine(hoy, time.fromisoformat(h_cierre))

    # Definir el inicio: El máximo entre la hora de apertura 
    # y "ahora" + 30 minutos (margen de preparación)
#    margen_preparacion = ahora + timedelta(minutes=30)
#    inicio = max(apertura_dt, margen_preparacion)

    # Redondear al siguiente intervalo (Ej: si son 12:07 y el intervalo es 15, ir a 12:15)
#    minutos_a_sumar = (intervalo - (inicio.minute % intervalo)) % intervalo
#    actual = inicio + timedelta(minutes=minutos_a_sumar)
#    actual = actual.replace(second=0, microsecond=0)

    # --- INICIO DE CAMBIOS PARA VALIDACIÓN DE CAPACIDAD ---
#    conn = conectar_db()
#    cursor = conn.cursor()

    # Generar la lista hasta el cierre validando disponibilidad en DB
 #   while actual <= cierre_dt:
 #       hora_str = actual.strftime("%H:%M")
 #       # El formato debe coincidir con cómo guardas en la DB: 'YYYY-MM-DD HH:MM:00'
 #       fecha_hora_busqueda = f"{hoy} {hora_str}:00"
        
        # Consultar cuántos pedidos existen ya para esa franja y esa empresa
 #       cursor.execute("""
 #           SELECT COUNT(*) FROM pedidos 
 #           WHERE horario_entrega = ? AND id_empresa = ?
 #       """, (fecha_hora_busqueda, id_empresa))
        
 #       cantidad_pedidos = cursor.fetchone()[0]
        
        # Solo agregar la franja si no se ha superado el máximo configurado
 #       if cantidad_pedidos < MAX_PEDIDOS_POR_FRANJA_HORARIA:
 #           franjas.append(hora_str)
            
 #       actual += timedelta(minutes=intervalo)
    
 #   conn.close()
    # --- FIN DE CAMBIOS ---
    
 #   return franjas


def obtener_horarios_empresa(id_empresa):
    """Carga los horarios de la DB. Si no hay, devuelve un turno por defecto."""
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT horarios_json FROM empresas WHERE id_empresa = ?", (id_empresa,))
    res = cursor.fetchone()
    conn.close()
    
    if res and res['horarios_json']:
        return json.loads(res['horarios_json'])
    # Horario por defecto si la empresa es nueva o no tiene configurado
    return [["08:00", "23:00"]]

#def esta_abierto(id_empresa):
#    """Comprueba si la empresa específica está abierta ahora."""
#    turnos = obtener_horarios_empresa(id_empresa)
#    ahora = datetime.now().time()
#    
#    for turno in turnos:
#        apertura = time.fromisoformat(turno[0])
#        cierre = time.fromisoformat(turno[1])
#        if apertura <= cierre:
#            if apertura <= ahora <= cierre: return True
#        else: # Cruza medianoche
#            if ahora >= apertura or ahora <= cierre: return True
#    return False


# --- HELPERS DE HORARIOS ---
DIAS_SEMANA = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

def esta_abierto(id_empresa):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT horarios_json FROM empresas WHERE id_empresa = ?", (id_empresa,))
    res = cursor.fetchone(); conn.close()
    if not res or not res['horarios_json']: return True

    horarios = json.loads(res['horarios_json'])
    #dia_actual = datetime.now().strftime('%w')
    #ahora = datetime.now().time()
    ahora = get_now_arg().time()
    # --- CAMBIO AQUÍ ---
    ahora_dt = get_now_arg() 
    dia_actual = ahora_dt.strftime('%w') # '0' a '6'
    ahora_time = ahora_dt.time()
    # -------------------



    if dia_actual in horarios and horarios[dia_actual].get('abierto'):
        # Ahora recorremos la LISTA de turnos del día
        for turno in horarios[dia_actual].get('turnos', []):
            h_inicio = time.fromisoformat(turno['inicio'])
            h_fin = time.fromisoformat(turno['fin'])
            
            if h_inicio <= h_fin:
                if h_inicio <= ahora_time <= h_fin: return True
            else: # Cruce de medianoche
                if ahora_time >= h_inicio or ahora_time <= h_fin: return True
    return False


#def obtener_franjas_disponibles(id_empresa=None):
#    if not id_empresa: return []
#    
#    intervalo = INTERVALO_FRANJAS_MINUTOS
#    turnos = obtener_horarios_empresa(id_empresa)
#    franjas = []
#    ahora = datetime.now()
#    hoy = ahora.date()
#    margen_preparacion = ahora + timedelta(minutes=30)
#
#    conn = conectar_db(); cursor = conn.cursor()
#
#    for turno in turnos:
#        apertura_dt = datetime.combine(hoy, time.fromisoformat(turno[0]))
#        cierre_dt = datetime.combine(hoy, time.fromisoformat(turno[1]))
#        
#        # El cierre podría ser al día siguiente si cruza medianoche
#        if cierre_dt <= apertura_dt:
#            cierre_dt += timedelta(days=1)
#
#        actual = max(apertura_dt, margen_preparacion)
#        # Redondear
#        minutos_a_sumar = (intervalo - (actual.minute % intervalo)) % intervalo
#        actual = (actual + timedelta(minutes=minutos_a_sumar)).replace(second=0, microsecond=0)

#        while actual <= cierre_dt:
#            hora_str = actual.strftime("%H:%M")
#            fecha_hora_busqueda = f"{actual.strftime('%Y-%m-%d')} {hora_str}:00"
#            
#            cursor.execute("SELECT COUNT(*) FROM pedidos WHERE horario_entrega = ? AND id_empresa = ? AND estado_envio != 'Cancelado'", (fecha_hora_busqueda, id_empresa))
#            if cursor.fetchone()[0] < MAX_PEDIDOS_POR_FRANJA_HORARIA:
#                franjas.append(hora_str)
#            actual += timedelta(minutes=intervalo)
#    
#    conn.close()
#    return franjas

def obtener_franjas_disponibles(id_empresa=None):
    """Genera las horas de entrega disponibles detectando el formato de horario y múltiples turnos."""
    if not id_empresa: return []
    
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT horarios_json FROM empresas WHERE id_empresa = ?", (id_empresa,))
    res = cursor.fetchone()
    
    if not res or not res['horarios_json']:
        conn.close(); return []

    try:
        horarios_data = json.loads(res['horarios_json'])
    except:
        conn.close(); return []
    #-----------------------------------------------------------------------------------------------------
    #ahora = datetime.now()
    ahora = get_now_arg() # <--- CAMBIAR ESTO
    dia_actual_str = ahora.strftime('%w') # '0' a '6'
    #----------------------------------------------------------------------------------------------------
    # --- NORMALIZACIÓN DE TURNOS ---
    # Creamos una lista unificada de turnos para procesar sin importar el formato de origen
    turnos_a_procesar = []

    if isinstance(horarios_data, list):
        # FORMATO ANTIGUO: [["08:00", "23:00"]]
        for t in horarios_data:
            turnos_a_procesar.append({'inicio': t[0], 'fin': t[1]})
    else:
        # FORMATO NUEVO: Diccionario {"0": {"abierto": True, "turnos": [...]}}
        config_hoy = horarios_data.get(dia_actual_str)
        if config_hoy and config_hoy.get('abierto'):
            # Si tiene la lista de turnos (formato multi-turno)
            if 'turnos' in config_hoy and config_hoy['turnos']:
                turnos_a_procesar = config_hoy['turnos']
            # Si es el formato nuevo pero simple (inicio y fin directos)
            elif 'inicio' in config_hoy and 'fin' in config_hoy:
                turnos_a_procesar = [{'inicio': config_hoy['inicio'], 'fin': config_hoy['fin']}]

    if not turnos_a_procesar:
        conn.close(); return []

    franjas = []
    intervalo = INTERVALO_FRANJAS_MINUTOS
    margen_preparacion = ahora + timedelta(minutes=30)

    # Procesamos cada turno encontrado
    for turno in turnos_a_procesar:
        try:
            h_inicio = time.fromisoformat(turno['inicio'])
            h_fin = time.fromisoformat(turno['fin'])
            #--------------------------------------------------------------------------
            #inicio_dt = datetime.combine(ahora.date(), h_inicio)
            # así que forzamos la localización:
            inicio_dt = ARG_TZ.localize(datetime.combine(ahora.date(), h_inicio))
            #--------------------------------------------------------------------------
            #fin_dt = datetime.combine(ahora.date(), h_fin)
            fin_dt = ARG_TZ.localize(datetime.combine(ahora.date(), h_fin))
            
            # Manejo de cruce de medianoche
            if fin_dt <= inicio_dt:
                fin_dt += timedelta(days=1)

            # Punto de partida: El máximo entre el inicio del turno y el ahora + margen
            actual = max(inicio_dt, margen_preparacion)
            
            # Redondeo al siguiente intervalo
            minutos_a_sumar = (intervalo - (actual.minute % intervalo)) % intervalo
            actual = (actual + timedelta(minutes=minutos_a_sumar)).replace(second=0, microsecond=0)

            while actual <= fin_dt:
                hora_str = actual.strftime("%H:%M")
                fecha_hora_db = actual.strftime("%Y-%m-%d %H:%M:= ?")
                
                cursor.execute("""
                    SELECT COUNT(*) FROM pedidos 
                    WHERE horario_entrega = ? AND id_empresa = ? AND estado_envio != 'Cancelado'
                """, (fecha_hora_db, id_empresa))
                
                if cursor.fetchone()[0] < MAX_PEDIDOS_POR_FRANJA_HORARIA:
                    # Evitar duplicados si los turnos se solapan
                    if hora_str not in franjas:
                        franjas.append(hora_str)
                
                actual += timedelta(minutes=intervalo)
        except Exception as e:
            print(f"Error procesando turno individual: {e}")
            continue
    
    conn.close()
    # Ordenar las franjas por si los turnos estaban desordenados
    franjas.sort()
    return franjas


def verificar_acceso_empresa(id_empresa_recurso):
    """Bloquea el acceso si la empresa del recurso no coincide con la del usuario."""
    if not current_user.is_authenticated:
        abort(401) # No logueado
    
    if current_user.has_role('super_admin', 'admin_empresa'):
        return True # El super_admin siempre pasa
    
    # Convertimos ambos a entero para evitar el error de comparacion "2" == 2
    try:
        user_emp = int(current_user.id_empresa)
        resource_emp = int(id_empresa_recurso)
    except (ValueError, TypeError):
        # Si alguno es None o no es número, bloqueamos y mandamos info a la terminal
        print(f"BLOQUEO 403: Usuario Empresa({current_user.id_empresa}) vs Recurso Empresa({id_empresa_recurso})")
        abort(403)
    
    if user_emp != resource_emp:
        print(f"BLOQUEO 403: No coinciden IDs ({user_emp} != {resource_emp})")
        abort(403)
    
    return True




def get_company_id_for_frontend_context():
    # 1. Si el cliente eligió una sucursal en el Index, usamos esa
    if 'empresa_seleccionada_id' in session:
        return session['empresa_seleccionada_id']
    
    # 2. Si es un empleado logueado, usamos la suya
    if current_user.is_authenticated and not current_user.has_role('super_admin') and current_user.id_empresa:
        return current_user.id_empresa
        
    # 3. Si no, la de por defecto
    return DEFAULT_COMPANY_FOR_ORDERS

def guardar_configuracion(clave, valor, id_empresa=None):
    conn = conectar_db(); cursor = conn.cursor()
    if id_empresa: cursor.execute("REPLACE INTO configuracion (clave, valor, id_empresa) VALUES (?, ?, ?)", (clave, str(valor), id_empresa))
    else: cursor.execute("REPLACE INTO configuracion (clave, valor, id_empresa) VALUES (?, ?, NULL)", (clave, str(valor)))
    conn.commit(); conn.close()

def cargar_configuracion(clave, valor_defecto=None, id_empresa=None):
    conn = conectar_db(); cursor = conn.cursor()
    if id_empresa: cursor.execute("SELECT valor FROM configuracion WHERE clave = ? AND id_empresa = ?", (clave, id_empresa))
    else: cursor.execute("SELECT valor FROM configuracion WHERE clave = ? AND id_empresa IS NULL", (clave,))
    res = cursor.fetchone(); conn.close()
    return res['valor'] if res else valor_defecto

def get_costo_envio(id_empresa=None):
    # Si no nos pasan empresa, intentamos sacar la del usuario logueado
    if id_empresa is None:
        id_empresa = current_user.id_empresa if (current_user.is_authenticated and current_user.id_empresa) else DEFAULT_COMPANY_FOR_ORDERS
    
    costo = cargar_configuracion('ENVIO_COSTO', str(DEFAULT_ENVIO_COSTO), id_empresa)
    return float(costo)

def procesar_descuento_stock(id_pedido):
    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Obtener todos los items del pedido
    cursor.execute("SELECT id, id_plato, cantidad FROM items_pedido WHERE id_pedido = ?", (id_pedido,))
    items = cursor.fetchall()
    
    for item in items:
        # A. Descontar por la RECETA BASE del plato
        cursor.execute("""
            SELECT id_insumo, cantidad_requerida 
            FROM recetas WHERE id_plato = ?
        """, (item['id_plato'],))
        
        insumos_base = cursor.fetchall()
        for ins in insumos_base:
            total_a_descontar = ins['cantidad_requerida'] * item['cantidad']
            cursor.execute("""
                UPDATE insumos SET stock_actual = stock_actual - ? 
                WHERE id_insumo = ?
            """, (total_a_descontar, ins['id_insumo']))

        # B. Descontar por MODIFICADORES (Ej: Opciones elegidas)
        # Buscamos qué opciones eligió el cliente para este item
        cursor.execute("""
            SELECT ipm.nombre_opcion, po.id_opcion 
            FROM items_pedido_modificadores ipm
            JOIN plato_opciones po ON ipm.nombre_opcion = po.nombre
            WHERE ipm.id_item_pedido = ?
        """, (item['id'],))
        
        opciones_elegidas = cursor.fetchall()
        for opt in opciones_elegidas:
            cursor.execute("""
                SELECT id_insumo, cantidad_requerida 
                FROM opciones_insumos WHERE id_opcion = ?
            """, (opt['id_opcion'],))
            
            insumos_opt = cursor.fetchall()
            for ins_o in insumos_opt:
                total_o = ins_o['cantidad_requerida'] * item['cantidad']
                cursor.execute("""
                    UPDATE insumos SET stock_actual = stock_actual - ? 
                    WHERE id_insumo = ?
                """, (total_o, ins_o['id_insumo']))
                
    conn.commit(); conn.close()


def procesar_devolucion_stock(id_pedido):
    """Devuelve los insumos al inventario cuando un pedido se cancela."""
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT id, id_plato, cantidad FROM items_pedido WHERE id_pedido = ?", (id_pedido,))
    items = cursor.fetchall()
    
    for item in items:
        # A. Devolución por RECETA BASE
        cursor.execute("SELECT id_insumo, cantidad_requerida FROM recetas WHERE id_plato = ?", (item['id_plato'],))
        for ins in cursor.fetchall():
            total_a_devolver = ins['cantidad_requerida'] * item['cantidad']
            cursor.execute("UPDATE insumos SET stock_actual = stock_actual + ? WHERE id_insumo = ?", (total_a_devolver, ins['id_insumo']))

        # B. Devolución por MODIFICADORES/OPCIONES
        cursor.execute("""
            SELECT po.id_opcion FROM items_pedido_modificadores ipm
            JOIN plato_opciones po ON ipm.nombre_opcion = po.nombre
            WHERE ipm.id_item_pedido = ?
        """, (item['id'],))
        for opt in cursor.fetchall():
            cursor.execute("SELECT id_insumo, cantidad_requerida FROM opciones_insumos WHERE id_opcion = ?", (opt['id_opcion'],))
            for ins_o in cursor.fetchall():
                total_o = ins_o['cantidad_requerida'] * item['cantidad']
                cursor.execute("UPDATE insumos SET stock_actual = stock_actual + ? WHERE id_insumo = ?", (total_o, ins_o['id_insumo']))
                
    conn.commit(); conn.close()
    
 
 
@app.route('/gestion/pedido/<int:id_pedido>/cancelar', methods=['POST'])
@login_required
def cancelar_pedido(id_pedido):
    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Obtener datos del pedido antes de cancelar
    cursor.execute("SELECT estado_envio, id_cliente, descuento_aplicado FROM pedidos WHERE id_pedido = ?", (id_pedido,))
    pedido = cursor.fetchone()
    
    if not pedido:
        conn.close(); abort(404)

    # 2. LÓGICA DE STOCK: Si el pedido ya estaba en proceso, devolvemos los ingredientes
    if pedido['estado_envio'] in ['Recibido', 'En Preparación', 'En Camino']:
        procesar_devolucion_stock(id_pedido)

    # 3. LÓGICA DE PUNTOS: Si el cliente usó puntos, se los devolvemos
    # (Asumiendo que 1 punto = 1 peso, ajusta según tu VALOR_PESO_POR_PUNTO_CANJE)
    if pedido['id_cliente'] and pedido['descuento_aplicado'] > 0:
        puntos_a_devolver = int(pedido['descuento_aplicado'] / VALOR_PESO_POR_PUNTO_CANJE)
        cursor.execute("UPDATE clientes SET puntos = puntos + ? WHERE id_cliente = ?", 
                       (puntos_a_devolver, pedido['id_cliente']))

    # 4. Actualizamos el estado del pedido y el pago
    cursor.execute("""
        UPDATE pedidos 
        SET estado_envio = 'Cancelado', 
            estado_pago = 'Cancelado' 
        WHERE id_pedido = ?
    """, (id_pedido,))
    
    conn.commit(); conn.close()
    
    flash(f"Pedido #{id_pedido} cancelado. Stock y puntos revertidos.", "info")
    return redirect(url_for('gestion_pedidos'))

    

def procesar_descuento_stock(id_pedido):
    """Busca los platos del pedido y descuenta sus ingredientes del inventario"""
    conn = conectar_db(); cursor = conn.cursor()
    
    # Buscamos todos los productos de este pedido
    cursor.execute("SELECT id, id_plato, cantidad FROM items_pedido WHERE id_pedido = ?", (id_pedido,))
    items = cursor.fetchall()
    
    for item in items:
        # A. DESCUENTO POR RECETA BASE
        # Buscamos qué insumos gasta este plato según la tabla recetas
        cursor.execute("""
            SELECT id_insumo, cantidad_requerida 
            FROM recetas WHERE id_plato = ?
        """, (item['id_plato'],))
        
        insumos_base = cursor.fetchall()
        for ins in insumos_base:
            total_a_descontar = ins['cantidad_requerida'] * item['cantidad']
            cursor.execute("""
                UPDATE insumos SET stock_actual = stock_actual - ? 
                WHERE id_insumo = ?
            """, (total_a_descontar, ins['id_insumo']))

        # B. DESCUENTO POR MODIFICADORES (Ej: Extra Bacon, Doble Carne)
        # Buscamos los modificadores que el cliente eligió para este item
        cursor.execute("""
            SELECT po.id_opcion 
            FROM items_pedido_modificadores ipm
            JOIN plato_opciones po ON ipm.nombre_opcion = po.nombre
            WHERE ipm.id_item_pedido = ?
        """, (item['id'],))
        
        opciones_elegidas = cursor.fetchall()
        for opt in opciones_elegidas:
            cursor.execute("""
                SELECT id_insumo, cantidad_requerida 
                FROM opciones_insumos WHERE id_opcion = ?
            """, (opt['id_opcion'],))
            
            insumos_opt = cursor.fetchall()
            for ins_o in insumos_opt:
                total_o = ins_o['cantidad_requerida'] * item['cantidad']
                cursor.execute("""
                    UPDATE insumos SET stock_actual = stock_actual - ? 
                    WHERE id_insumo = ?
                """, (total_o, ins_o['id_insumo']))
                
    conn.commit(); conn.close()




# --- Rutas ---
@app.route('/')
def index():
    conn = conectar_db()
    cursor = conn.cursor()
    # Traemos todas las empresas que estén activas
    cursor.execute("SELECT * FROM empresas WHERE activo = 1")
    todas_las_empresas = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', empresas=todas_las_empresas)


#Repartidor App
@app.route('/repartidor/mis-pedidos')
@login_required
def panel_repartidor():
    # --- DEBUG: Esto aparecerá en tu terminal negra de VS Code/CMD ---
    print(f"DEBUG: Usuario: {current_user.email}")
    print(f"DEBUG: Rol en el objeto: '{current_user.nombre_rol}'")
    print(f"DEBUG: ID Repartidor Vinculado: {current_user.id_repartidor_vinculado}")
    # ----------------------------------------------------------------

    # CAMBIO DE SEGURIDAD: Identificamos el rol en minúsculas
    rol_actual = str(current_user.nombre_rol).lower()
    
    # Verificamos si tiene permiso para entrar al panel
    if "repartidor" not in rol_actual and "admin" not in rol_actual and "empleado" not in rol_actual:
        print("DEBUG: ACCESO DENEGADO POR ROL INCORRECTO")
        abort(403)

    conn = conectar_db(); cursor = conn.cursor()
    
    # --- LÓGICA DE FILTRADO INTELIGENTE ---

    # 1. CASO REPARTIDOR: Solo ve sus pedidos asignados
    if "repartidor" in rol_actual:
        if not current_user.id_repartidor_vinculado:
            conn.close()
            flash("Acceso denegado: Tu usuario de repartidor no tiene un repartidor físico vinculado.", "danger")
            return redirect(url_for('index'))
            
        cursor.execute("""
            SELECT p.id_pedido, p.cliente_nombre, p.cliente_apellido, p.direccion_entrega, 
                   p.estado_envio, p.lat_cliente, p.lon_cliente, p.telefono_cliente, 
                   p.fecha_creacion, p.token, p.eta_minutos
            FROM pedidos p 
            WHERE p.id_repartidor = ? 
            AND p.estado_envio NOT IN ('Entregado', 'Cancelado')
            ORDER BY p.horario_entrega ASC
        """, (current_user.id_repartidor_vinculado,))

    # 2. CASO SUPER ADMIN: Ve toda la flota de todas las sucursales
    elif "super_admin" in rol_actual:
        cursor.execute("""
            SELECT p.id_pedido, p.cliente_nombre, p.cliente_apellido, p.direccion_entrega, 
                   p.estado_envio, p.lat_cliente, p.lon_cliente, p.telefono_cliente, 
                   p.fecha_creacion, p.token, p.eta_minutos,
                   r.nombre as rep_n, r.apellido as rep_a
            FROM pedidos p 
            LEFT JOIN repartidores r ON p.id_repartidor = r.id_repartidor
            WHERE p.estado_envio NOT IN ('Entregado', 'Cancelado')
            AND p.es_envio = 1
            ORDER BY p.horario_entrega ASC
        """)

    # 3. CASO ADMIN/EMPLEADO DE EMPRESA: Ve todos los envíos de SU sucursal
    else:
        cursor.execute("""
            SELECT p.id_pedido, p.cliente_nombre, p.cliente_apellido, p.direccion_entrega, 
                   p.estado_envio, p.lat_cliente, p.lon_cliente, p.telefono_cliente, 
                   p.fecha_creacion, p.token, p.eta_minutos,
                   r.nombre as rep_n, r.apellido as rep_a
            FROM pedidos p 
            LEFT JOIN repartidores r ON p.id_repartidor = r.id_repartidor
            WHERE p.id_empresa = ? 
            AND p.es_envio = 1
            AND p.estado_envio NOT IN ('Entregado', 'Cancelado')
            ORDER BY p.horario_entrega ASC
        """, (current_user.id_empresa,))
    
    pedidos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('repartidor_panel.html', pedidos=pedidos)



@app.route('/gestion/catalogo/precios', methods=['GET', 'POST'])
@login_required
def gestion_precios():
    if not (current_user.has_role('super_admin') or current_user.has_role('admin_empresa')):
        abort(403)
    
    conn = conectar_db(); cursor = conn.cursor()
    cid = current_user.id_empresa if not current_user.has_role('super_admin') else request.args.get('id_empresa') or DEFAULT_COMPANY_FOR_ORDERS

    if request.method == 'POST':
        accion = request.form.get('accion')
        platos_ids = request.form.getlist('platos_seleccionados')

        if not platos_ids:
            flash("No seleccionaste ningún plato.", "warning")
        else:
            if accion == 'masivo':
                porcentaje = float(request.form.get('porcentaje_masivo', 0)) / 100
                for pid in platos_ids:
                    # Buscamos el precio base para calcular el descuento
                    cursor.execute("SELECT precio FROM platos WHERE id_plato = ?", (pid,))
                    res = cursor.fetchone()
                    if res:
                        precio_base = res['precio']
                        nuevo_precio = precio_base * (1 - porcentaje)
                        cursor.execute("UPDATE platos SET precio_oferta = ? WHERE id_plato = ?", (nuevo_precio, pid))
                flash(f"Se aplicó un {int(porcentaje*100)}% de descuento a los platos seleccionados.", "success")
            
            # --- LÓGICA PARA QUITAR OFERTAS Y VOLVER AL PRECIO ANTERIOR ---
            elif accion == 'limpiar':
                for pid in platos_ids:
                    # Al ponerlo en NULL, el sistema vuelve a tomar el precio normal
                    cursor.execute("UPDATE platos SET precio_oferta = NULL WHERE id_plato = ?", (pid,))
                flash("Ofertas eliminadas. Los platos volvieron a su precio original.", "info")

            conn.commit()
        
        return redirect(url_for('gestion_precios', id_empresa=cid))

    # Cargar platos para la vista
    cursor.execute("SELECT * FROM platos WHERE id_empresa = ? AND activo = 1 ORDER BY rubro", (cid,))
    platos = cursor.fetchall()
    conn.close()
    return render_template('gestion_precios.html', platos=platos, cid=cid)


import urllib.parse # Asegúrate de tener este import arriba

@app.route('/repartidor/pedido/<int:id_pedido>/despachar', methods=['POST'])
@login_required
def repartidor_despachar(id_pedido):
    conn = conectar_db(); cursor = conn.cursor()
    ahora_str = get_now_iso() 
    # 1. Obtener datos necesarios
    cursor.execute("""
        SELECT p.lat_cliente, p.lon_cliente, e.lat, e.lon 
        FROM pedidos p 
        JOIN empresas e ON p.id_empresa = e.id_empresa 
        WHERE p.id_pedido = ?
    """, (id_pedido,))
    data = cursor.fetchone()
    
    # 2. Calcular ETA Real (OSRM)
    eta = calcular_tiempo_ruta_osrm(data['lat'], data['lon'], data['lat_cliente'], data['lon_cliente'])
    
    # 3. Actualizar estado a 'En Camino' y guardar el ETA
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:= ?')
    cursor.execute("""
        UPDATE pedidos 
        SET estado_envio = 'En Camino', 
            fecha_despacho = ?, 
            eta_minutos = ? 
        WHERE id_pedido = ?
    """, (ahora_str, eta, id_pedido))
    
    conn.commit(); conn.close()
    flash(f"Pedido #{id_pedido} marcado EN CAMINO. Puedes notificar al cliente ahora.", "info")
    return redirect(url_for('panel_repartidor'))



# NUEVA RUTA: Para seleccionar la empresa y guardarla en la sesión
@app.route('/seleccionar_sucursal/<int:id_empresa>')
def seleccionar_sucursal(id_empresa):
    session['empresa_seleccionada_id'] = id_empresa
    return redirect(url_for('hacer_pedido'))




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT u.*, r.nombre_rol FROM usuarios u JOIN roles r ON u.id_rol = r.id_rol WHERE u.email = ?", (email,))
        u = cursor.fetchone(); conn.close()
        if u and check_password_hash(u['password'], password):
            user = Usuario(u['id_usuario'], u['email'], u['password'], u['nombre'], u['apellido'], u['id_rol'], u['id_empresa'], u['activo'], u['primer_login_requerido'], u['nombre_rol'])
            login_user(user); return redirect(url_for('index'))
        
            # --- REDIRECCIÓN INTELIGENTE ---
            if user.has_role('repartidor'):
                return redirect(url_for('panel_repartidor'))
            
            return redirect(url_for('index'))    
            
        
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

import secrets # <--- ASEGÚRATE DE TENER ESTA LÍNEA AL INICIO DE APP.PY

def calcular_totales_carrito(id_empresa):
    carrito = session.get('carrito', {})
    # Usamos precio_total_unitario que es el que tiene los extras sumados
    subtotal = sum(item['precio_total_unitario'] * item['cantidad'] for item in carrito.values())
    
    costo_envio = get_costo_envio(id_empresa)
    return {
        "subtotal": subtotal,
        "envio": costo_envio,
        "total_con_envio": subtotal + costo_envio
    }



@app.route('/api/validar_cupon', methods=['POST'])
def validar_cupon():
    data = request.json
    codigo = data.get('codigo', '').strip().upper()
    total_carrito = float(data.get('total', 0))
    telefono = data.get('telefono', '').strip() # <--- Recibimos el teléfono
    cid = get_company_id_for_frontend_context()

    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Buscar si el cupón existe
    cursor.execute("SELECT * FROM cupones WHERE codigo = ? AND id_empresa = ? AND activo = 1", (codigo, cid))
    cup = cursor.fetchone()

    if not cup:
        conn.close()
        return jsonify({"success": False, "message": "Cupón no válido."})

    # 2. NUEVO: Verificar si este teléfono ya usó este código antes
    if telefono:
        cursor.execute("""
            SELECT COUNT(*) FROM pedidos 
            WHERE telefono_cliente = ? AND cupon_codigo = ? AND estado_envio != 'Cancelado'
        """, (telefono, codigo))
        
        if cursor.fetchone()[0] > 0:
            conn.close()
            return jsonify({"success": False, "message": "Ya utilizaste esta promoción anteriormente."})

    # 3. Validar mínimo de compra
    if total_carrito < cup['minimo_compra']:
        conn.close()
        return jsonify({"success": False, "message": f"Mínimo para este cupón: ${cup['minimo_compra']}"})

    # Calcular descuento
    descuento = total_carrito * (cup['valor'] / 100) if cup['tipo'] == 'porcentaje' else cup['valor']

    session['cupon_aplicado'] = {'codigo': codigo, 'descuento': descuento}
    conn.close()
    return jsonify({"success": True, "descuento": descuento, "message": "¡Cupón aplicado!"})



@app.route('/gestion/cupones')
@login_required
def gestion_cupones():
    # Solo administradores y super_admin
    if not current_user.has_role('super_admin') and not current_user.has_role('admin_empresa'):
        abort(403)
        
    conn = conectar_db(); cursor = conn.cursor()
    
    # Filtro por empresa
    if current_user.has_role('super_admin'):
        cursor.execute("SELECT c.*, e.nombre as empresa_n FROM cupones c LEFT JOIN empresas e ON c.id_empresa = e.id_empresa")
    else:
        cursor.execute("SELECT * FROM cupones WHERE id_empresa = ?", (current_user.id_empresa,))
    
    cupones = cursor.fetchall()
    conn.close()
    return render_template('gestion_cupones.html', cupones=cupones)

@app.route('/gestion/cupones/agregar', methods=['GET', 'POST'])
@login_required
def agregar_cupon():
    if not (current_user.has_role('super_admin') or current_user.has_role('admin_empresa')):
        abort(403)

    if request.method == 'POST':
        codigo = request.form.get('codigo').strip().upper()
        tipo = request.form.get('tipo')
        valor = float(request.form.get('valor'))
        minimo = float(request.form.get('minimo_compra', 0))
        
        # Determinar empresa
        id_empresa = request.form.get('id_empresa') if current_user.has_role('super_admin') else current_user.id_empresa

        conn = conectar_db(); cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO cupones (codigo, tipo, valor, minimo_compra, activo, id_empresa) 
                VALUES (?, ?, ?, ?, 1, ?)
            """, (codigo, tipo, valor, minimo, id_empresa))
            conn.commit()
            flash(f"Cupón '{codigo}' creado con éxito.", "success")
            return redirect(url_for('gestion_cupones'))
        except Exception as e:
            flash(f"Error al crear el cupón: {e}", "danger")
        finally:
            conn.close()

    empresas = []
    if current_user.has_role('super_admin'):
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1")
        empresas = cursor.fetchall(); conn.close()

    return render_template('agregar_cupon.html', empresas=empresas)



# --- RUTA PARA INACTIVAR / ACTIVAR CUPÓN ---
@app.route('/gestion/cupones/toggle/<int:id_cupon>', methods=['POST'])
@login_required
def toggle_cupon(id_cupon):
    if not (current_user.has_role('super_admin') or current_user.has_role('admin_empresa')):
        abort(403)
        
    conn = conectar_db(); cursor = conn.cursor()
    # Obtenemos el estado actual
    cursor.execute("SELECT activo FROM cupones WHERE id_cupon = ?", (id_cupon,))
    res = cursor.fetchone()
    
    if res:
        nuevo_estado = 0 if res['activo'] == 1 else 1
        # Actualizamos
        cursor.execute("UPDATE cupones SET activo = ? WHERE id_cupon = ?", (nuevo_estado, id_cupon))
        conn.commit()
        estado_txt = "activado" if nuevo_estado == 1 else "inactivado"
        flash(f"Cupón {estado_txt} correctamente.", "info")
    
    conn.close()
    return redirect(url_for('gestion_cupones'))

# --- RUTA PARA EDITAR CUPÓN ---
@app.route('/gestion/cupones/editar/<int:id_cupon>', methods=['GET', 'POST'])
@login_required
def editar_cupon(id_cupon):
    if not (current_user.has_role('super_admin') or current_user.has_role('admin_empresa')):
        abort(403)

    conn = conectar_db(); cursor = conn.cursor()

    if request.method == 'POST':
        codigo = request.form.get('codigo').strip().upper()
        tipo = request.form.get('tipo')
        valor = float(request.form.get('valor'))
        minimo = float(request.form.get('minimo_compra', 0))
        
        cursor.execute("""
            UPDATE cupones 
            SET codigo=?, tipo=?, valor=?, minimo_compra=? 
            WHERE id_cupon=?
        """, (codigo, tipo, valor, minimo, id_cupon))
        conn.commit(); conn.close()
        flash("Cupón actualizado con éxito.", "success")
        return redirect(url_for('gestion_cupones'))

    cursor.execute("SELECT * FROM cupones WHERE id_cupon = ?", (id_cupon,))
    cupon = cursor.fetchone(); conn.close()
    
    if not cupon: abort(404)
    return render_template('editar_cupon.html', cupon=cupon)


#envio de cupones masivos

@app.route('/gestion/cupones/difusion')
@login_required
def difusion_cupones():
    if not (current_user.has_role('super_admin') or current_user.has_role('admin_empresa')):
        abort(403)
        
    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Obtener solo los cupones ACTIVOS de la empresa
    cid = current_user.id_empresa
    cursor.execute("SELECT * FROM cupones WHERE id_empresa = ? AND activo = 1", (cid,))
    cupones_activos = cursor.fetchall()
    
    # 2. Obtener lista de clientes (CRM)
    cursor.execute("SELECT nombre, apellido, telefono FROM clientes WHERE id_empresa = ?", (cid,))
    clientes_db = cursor.fetchall()

    # --- MEJORA DE COMPATIBILIDAD (Punto 1: Limpieza y Formato 549) ---
    clientes_procesados = []
    for cli in clientes_db:
        # Extraemos solo los números del teléfono guardado
        tel_solo_numeros = "".join(filter(str.isdigit, str(cli['telefono'])))
        
        # Lógica para que WhatsApp reconozca el número aunque no esté agendado
        # Si tiene 10 dígitos (ej: 1122334455), agregamos 549
        if len(tel_solo_numeros) == 10:
            tel_wa = "549" + tel_solo_numeros
        # Si ya tiene el 54 pero le falta el 9 (ej: 5411...), se lo inyectamos
        elif tel_solo_numeros.startswith("54") and not tel_solo_numeros.startswith("549"):
            tel_wa = "549" + tel_solo_numeros[2:]
        else:
            tel_wa = tel_solo_numeros

        clientes_procesados.append({
            'nombre': cli['nombre'],
            'apellido': cli['apellido'],
            'telefono_original': cli['telefono'],
            'telefono_wa': tel_wa # Este se usará para el link de WhatsApp
        })
    # -----------------------------------------------------------------
    
    # 3. Construir el Mensaje Maestro (Tu código original preservado)
    # Traemos el nombre real de la empresa para que el mensaje sea profesional
    cursor.execute("SELECT nombre FROM empresas WHERE id_empresa = ?", (cid,))
    emp_data = cursor.fetchone()
    empresa_nombre = emp_data['nombre'] if emp_data else "Nuestra Sucursal"
    
    mensaje = f"🎉 *¡PROMOCIONES DE LA SEMANA EN {empresa_nombre.upper()}!* 🎉\n\n"
    mensaje += "Aprovechá estos beneficios exclusivos para tus pedidos de esta semana:\n\n"
    
    for c in cupones_activos:
        desc = f"{int(c['valor'])}%" if c['tipo'] == 'porcentaje' else f"${int(c['valor'])}"
        mensaje += f"🏷️ *CÓDIGO: {c['codigo']}*\n"
        mensaje += f"🎁 Beneficio: *{desc} de descuento*\n"
        if c['minimo_compra'] > 0:
            mensaje += f"💰 Mínimo de compra: ${int(c['minimo_compra'])}\n"
        mensaje += "--------------------------\n"
    
    mensaje += "\n🚀 *Hacé tu pedido online aquí:* \n"
    mensaje += url_for('hacer_pedido', _external=True)
    mensaje += "\n\n_¡Te esperamos!_ 😋"
    
    conn.close()
    
    # Pasamos el mensaje ya codificado para URL
    mensaje_url = urllib.parse.quote(mensaje)
    
    return render_template('cupones_difusion.html', 
                           clientes=clientes_procesados, # Usamos la lista procesada
                           mensaje_texto=mensaje, 
                           mensaje_url=mensaje_url)
    
    

@app.route('/gestion/clientes')
@login_required
def gestion_clientes():
    if not (current_user.has_role('super_admin') or current_user.has_role('admin_empresa')):
        abort(403)
        
    conn = conectar_db(); cursor = conn.cursor()
    
    # Consulta avanzada: Une clientes con sus pedidos para calcular totales
    query = """
        SELECT c.*, 
               COUNT(p.id_pedido) as total_pedidos, 
               SUM(p.costo_total) as gasto_total
        FROM clientes c
        LEFT JOIN pedidos p ON c.id_cliente = p.id_cliente
    """
    
    if current_user.has_role('super_admin'):
        query += " GROUP BY c.id_cliente ORDER BY total_pedidos DESC"
        cursor.execute(query)
    else:
        query += " WHERE c.id_empresa = ? GROUP BY c.id_cliente ORDER BY total_pedidos DESC"
        cursor.execute(query, (current_user.id_empresa,))
    
    clientes = cursor.fetchall()
    conn.close()
    return render_template('gestion_clientes.html', clientes=clientes)


@app.route('/gestion/cupones/eliminar/<int:id_cupon>', methods=['POST'])
@login_required
def eliminar_cupon(id_cupon):
    conn = conectar_db(); cursor = conn.cursor()
    # Verificación de seguridad: No borrar cupones de otra empresa
    if not current_user.has_role('super_admin'):
        cursor.execute("DELETE FROM cupones WHERE id_cupon = ? AND id_empresa = ?", (id_cupon, current_user.id_empresa))
    else:
        cursor.execute("DELETE FROM cupones WHERE id_cupon = ?", (id_cupon,))
    conn.commit(); conn.close()
    flash("Cupón eliminado.", "info")
    return redirect(url_for('gestion_cupones'))


@app.route('/api/limpiar_cupon', methods=['POST'])
def limpiar_cupon():
    session.pop('cupon_aplicado', None)
    session.modified = True # <--- Forzamos a Flask a guardar el cambio en la sesión
    return jsonify({"success": True})



@app.route('/hacer_pedido', methods=['GET', 'POST'])
def hacer_pedido():
    # Detectamos el ID de la empresa (sucursal) seleccionada
    cid = get_company_id_for_frontend_context()
    ahora_arg = get_now_arg() 
    carrito = session.get('carrito', {})
    
    # 1. Obtenemos los datos de la empresa seleccionada (incluyendo horarios_json)
    conn_info = conectar_db()
    cursor_info = conn_info.cursor()
    cursor_info.execute("SELECT * FROM empresas WHERE id_empresa = ?", (cid,))
    empresa_actual = cursor_info.fetchone()
    conn_info.close()

    # --- INICIALIZACIÓN CLAVE ---
    request_form = {} 
    config_hoy = {'abierto': False, 'turnos': []} # Se inicializa aquí para que siempre exista
    turnos_de_hoy = []
    # ----------------------------

    # --- LÓGICA DE HORARIOS MULTI-TURNO (CORREGIDA) ---
    abierto = esta_abierto(cid)

    if empresa_actual and empresa_actual['horarios_json']:
        try:
            horarios_data = json.loads(empresa_actual['horarios_json'])
        except:
            horarios_data = {}
        
        dia_hoy_str = ahora_arg.strftime('%w') # '0' es Domingo, '1' Lunes, etc.

        # Extraer la configuración según el formato guardado en DB
        if isinstance(horarios_data, list):
            # Formato antiguo: [["08:00", "23:00"]]
            turnos_temp = []
            for t in horarios_data:
                if len(t) >= 2:
                    turnos_temp.append({'inicio': t[0], 'fin': t[1]})
            config_hoy = {'abierto': True, 'turnos': turnos_temp}
            
        elif isinstance(horarios_data, dict):
            # Formato nuevo: {"1": {"abierto": True, "turnos": [...]}}
            config_hoy = horarios_data.get(dia_hoy_str, {'abierto': False, 'turnos': []})

    # Asignar los turnos finales para la vista con seguridad
    if isinstance(config_hoy, dict):
        turnos_de_hoy = config_hoy.get('turnos', [])
    # --------------------------------------------------
    
    
    if request.method == 'POST':
        if not abierto:
            flash("Lo sentimos, el restaurante está cerrado actualmente.", "danger")
            return redirect(url_for('hacer_pedido'))
            
        request_form = request.form
        
        if not carrito:
            flash("Tu carrito está vacío. Agrega productos antes de finalizar.", "warning")
            return redirect(url_for('hacer_pedido'))

        # 1. Obtener datos del formulario
        n = request.form.get('nombre', '').strip()
        a = request.form.get('apellido', '').strip()
        tel = request.form.get('telefono', '').strip() 
        
        calle = request.form.get('calle', '').strip()
        altura = request.form.get('altura', '').strip()
        localidad = request.form.get('localidad', '').strip()
        provincia = request.form.get('provincia', '').strip()
        piso_depto = request.form.get('piso_depto', '').strip()
        
        d_completa = f"{calle} {altura}, {localidad}, {provincia}"
        if piso_depto:
            d_completa += f" ({piso_depto})"
        
        ho = request.form.get('horario_entrega')
        fp = request.form.get('forma_pago', 'Efectivo')
        es_envio = 'es_envio_solicitado' in request.form
        
        # --- AÑADE ESTA VALIDACIÓN ---
        if not ho or ho == "Cerrado" or ":" not in ho:
            flash("Error: El horario de entrega seleccionado no es válido. Es posible que el local haya cerrado recientemente.", "danger")
            return redirect(url_for('hacer_pedido'))
        # ------------------------------

        # Solo si pasa la validación, seguimos:
        horario_entrega_completo = f"{ahora_arg.strftime('%Y-%m-%d')} {ho}:00"
                
        
        
        
        
        
        # Validación: Teléfono obligatorio para CRM
        if not n or not ho or not tel:
            flash("Nombre, Teléfono y Horario son obligatorios.", "danger")
        else:
            lat_cliente = None
            lon_cliente = None
            error_geoloc = False

            if es_envio:
                if not calle or not altura or not localidad or not provincia:
                    flash("Calle, Altura, Localidad y Provincia son obligatorias para el envío.", "danger")
                    error_geoloc = True
                else:
                    lat_cliente, lon_cliente = obtener_coordenadas(d_completa)
                    if lat_cliente is None:
                        flash("No pudimos validar la dirección exacta. Revisa la calle y la altura.", "danger")
                        error_geoloc = True
                    else:
                        if empresa_actual and empresa_actual['lat'] and empresa_actual['lon']:
                            suc_lat = empresa_actual['lat']
                            suc_lon = empresa_actual['lon']
                        else:
                            suc_lat = -37.3287
                            suc_lon = -59.1369

                        distancia_m = calcular_distancia_metros(suc_lat, suc_lon, lat_cliente, lon_cliente)
                        max_distancia_m = RADIO_ENVIO_CUADRAS * CUADRA_METROS
                        if distancia_m > max_distancia_m:
                            cuadras_reales = int(distancia_m / CUADRA_METROS)
                            flash(f"Fuera de radio: {cuadras_reales} cuadras (Máximo: {RADIO_ENVIO_CUADRAS}).", "warning")
                            error_geoloc = True
            
            if not error_geoloc:
                # 2. Calcular totales considerando cupones Y PUNTOS
                stats = calcular_totales_carrito(cid)
                costo_envio_final = stats['envio'] if es_envio else 0
                
                # --- LÓGICA DE DESCUENTOS COMBINADOS (CUPÓN + PUNTOS) ---
                datos_cupon = session.get('cupon_aplicado', {})
                monto_descuento_cupon = float(datos_cupon.get('descuento', 0))

                datos_puntos = session.get('puntos_a_canjear', {})
                monto_descuento_puntos = float(datos_puntos.get('descuento_pesos', 0))
                
                # Descuento total que va a la base de datos
                descuento_total_pedido = monto_descuento_cupon + monto_descuento_puntos
                
                total_final = (stats['subtotal'] - descuento_total_pedido) + costo_envio_final
                # -------------------------------------------------------

                token_pedido = secrets.token_urlsafe(16)

                # 3. Guardar en Base de Datos
                conn = conectar_db(); cursor = conn.cursor()
                try:
                    # --- LÓGICA CRM: BUSCAR O CREAR CLIENTE ---
                    cursor.execute("SELECT id_cliente, puntos FROM clientes WHERE telefono = ?", (tel,))
                    res_cliente = cursor.fetchone()

                    if res_cliente:
                        id_cliente_crm = res_cliente['id_cliente']
                        cursor.execute("""
                            UPDATE clientes SET nombre = ?, apellido = ?, id_empresa = ? WHERE id_cliente = ?
                        """, (n, a, cid, id_cliente_crm))
                        
                        # --- NUEVO: RESTAR PUNTOS SI SE USARON ---
                        if monto_descuento_puntos > 0:
                            puntos_usados = datos_puntos.get('puntos', 0)
                            cursor.execute("UPDATE clientes SET puntos = puntos - ? WHERE id_cliente = ?", 
                                           (puntos_usados, id_cliente_crm))
                    else:
                        #fecha_reg = datetime.now().strftime('%Y-%m-%d')
                        fecha_reg = get_now_arg().strftime('%Y-%m-%d') 
                        cursor.execute("""
                            INSERT INTO clientes (nombre, apellido, telefono, id_empresa, fecha_registro) 
                            VALUES (?, ?, ?, ?, ?)
                        """, (n, a, tel, cid, fecha_reg))
                        id_cliente_crm = cursor.lastrowid
                    # ----------------------------------------------------------------------------------

                    #fecha_actual_str = datetime.now().strftime('%Y-%m-%d %H:%M:= ?')
                    #horario_entrega_completo = f"{datetime.now().strftime('%Y-%m-%d')} {ho}:00"

                    # --- REEMPLÁZALO POR ESTO ---
                    ahora_arg = get_now_arg()
                    fecha_actual_str = ahora_arg.strftime('%Y-%m-%d %H:%M:= ?')

                    # Para el horario de entrega, usamos la fecha de hoy en Argentina + el horario elegido
                    horario_entrega_completo = f"{ahora_arg.strftime('%Y-%m-%d')} {ho}:00"
                    
                    #-------------------------------------------------------------------------------------
                                        
                    codigo_promo = datos_cupon.get('codigo')

                    # --- CÓDIGO CORREGIDO EN hacer_pedido (app.py) ---
                    cursor.execute("""
                        INSERT INTO pedidos (
                            token, cliente_nombre, cliente_apellido, direccion_entrega, es_envio, 
                            horario_entrega, costo_envio, costo_total, forma_pago, 
                            estado_pago, estado_envio, fecha_creacion, id_empresa,
                            lat_cliente, lon_cliente, id_cliente, telefono_cliente, 
                            descuento_aplicado, cupon_codigo
                        ) VALUES (?,?,?,?,?,?,?,?,?,'Pendiente','Pendiente',?,?,?,?,?,?,?,?)
                    """, (token_pedido, n, a, d_completa, int(es_envio), horario_entrega_completo, 
                        costo_envio_final, total_final, fp, fecha_actual_str, cid,
                        lat_cliente, lon_cliente, id_cliente_crm, tel, 
                        descuento_total_pedido, codigo_promo)) 
                                        
                    pid = cursor.lastrowid
                    # Guardado de items
                    for cart_key, data in carrito.items():
                            # Detectamos de forma segura si es un plato o una promo
                        id_plato = int(data['id_plato']) if data.get('id_plato') else None
                        id_promocion = int(data['id_promocion']) if data.get('id_promocion') else None

                        # La consulta ahora tiene 5 columnas y 5 valores (?)
                        cursor.execute("""
                            INSERT INTO items_pedido (id_pedido, id_plato, id_promocion, cantidad, precio_unitario) 
                            VALUES (?, ?, ?, ?, ?)
                        """, (pid, id_plato, id_promocion, data['cantidad'], data['precio_total_unitario']))
                        
                        
                        item_id = cursor.lastrowid
                        if data.get('opciones_texto'):
                            cursor.execute("INSERT INTO items_pedido_modificadores (id_item_pedido, nombre_modificador, nombre_opcion, precio_pagado) VALUES (?, 'Opciones', ?, 0)", (item_id, data['opciones_texto']))
                        if data.get('notas'):
                            cursor.execute("INSERT INTO items_pedido_modificadores (id_item_pedido, nombre_modificador, nombre_opcion, precio_pagado) VALUES (?, 'Notas', ?, 0)", (item_id, data['notas']))
                    
                    conn.commit()
                    
                    
                    
                    # --- LÓGICA DE MERCADO PAGO ---
                    if fp == 'Mercado Pago' and empresa_actual['mp_access_token']:
                        sdk = mercadopago.SDK(empresa_actual['mp_access_token'])
                        
                        preference_data = {
                            "items": [
                                {
                                    "title": f"Pedido #{pid} - {empresa_actual['nombre']}",
                                    "quantity": 1,
                                    "unit_price": float(total_final),
                                    "currency_id": "ARS"
                                }
                            ],
                            "back_urls": {
                                "success": url_for('pago_resultado', status='success', _external=True) + f"?id_pedido={pid}",
                                "failure": url_for('pago_resultado', status='failure', _external=True) + f"?id_pedido={pid}",
                                "pending": url_for('pago_resultado', status='pending', _external=True) + f"?id_pedido={pid}"
                            },
                            "auto_return": "approved",
                            "external_reference": str(pid)
                        }
                        
                        preference_response = sdk.preference().create(preference_data)
                        url_pago = preference_response["response"]["init_point"]
                        
                        session.pop('carrito', None)
                        session.pop('puntos_a_canjear', None) # Limpiar puntos
                        return redirect(url_pago)
                    
                    # Si es efectivo u otro medio
                    session.pop('carrito', None)
                    session.pop('cupon_aplicado', None)
                    session.pop('puntos_a_canjear', None) # Limpiar puntos
                   
                    flash("Pedido registrado. Por favor, confírmalo por WhatsApp.", "info")
                    return redirect(url_for('seguimiento_pedido', token=token_pedido))
                    
                except Exception as e:
                    conn.rollback()
                    flash(f"Error crítico al guardar: {e}", "danger")
                finally:
                    conn.close()

   # --- LÓGICA DE RENDERIZADO (GET) ---
    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Carga de platos y rubros
    cursor.execute("SELECT * FROM platos WHERE activo = 1 AND id_empresa = ?", (cid,))
    platos_db = [dict(row) for row in cursor.fetchall()]
    
    # --- APLICACIÓN DEL PUNTO 2: VALIDACIÓN DE STOCK REAL ---
    for plato in platos_db:
        disponible, motivo_faltante = verificar_disponibilidad_plato(plato['id_plato'])
        plato['disponible'] = disponible
        plato['motivo_faltante'] = motivo_faltante
    # ---------------------------------------------------------
    
    # 2. Carga de cupones
    cursor.execute("SELECT * FROM cupones WHERE id_empresa = ? AND activo = 1", (cid,))
    promos_disponibles = [dict(row) for row in cursor.fetchall()]

    # 3. CARGA DE PROMOCIONES (PUNTO 1 & 3)
    # Inicializamos la variable como lista vacía para evitar el UnboundLocalError
    promociones_db = []
    try:
        cursor.execute("SELECT * FROM promociones WHERE activo = 1 AND id_empresa = ?", (cid,))
        promociones_db = [dict(row) for row in cursor.fetchall()]

        for promo in promociones_db:
            # Buscamos los nombres de los platos que integran esta promo
            cursor.execute("""
                SELECT p.nombre FROM platos p 
                JOIN promocion_platos pp ON p.id_plato = pp.id_plato 
                WHERE pp.id_promocion = ?
            """, (promo['id_promocion'],))
            # Guardamos los nombres como una lista: ["Pizza", "Cerveza"]
            promo['platos_incluidos'] = [r['nombre'] for r in cursor.fetchall()]
    except Exception as e:
        print(f"Error cargando promos: {e}")
        # Si falla la tabla (ej: no existe aún), promociones_db seguirá siendo []

    conn.close() # Cerramos la conexión principal aquí

    # 4. Cálculos de Carrito, Franjas y Sesión
    franjas = obtener_franjas_disponibles(cid)
    stats = calcular_totales_carrito(cid)
    cupon_actual = session.get('cupon_aplicado', {})
    puntos_actual = session.get('puntos_a_canjear', {})
    
    carrito_detalle = []
    for k, v in carrito.items():
        carrito_detalle.append({
            'cart_key': k, 'id_plato': v['id_plato'], 'nombre': v['nombre'],
            'cantidad': v['cantidad'], 'opciones': v.get('opciones_texto', ''),
            'notas': v.get('notas', ''), 'precio_unitario': v['precio_total_unitario'],
            'subtotal': v['precio_total_unitario'] * v['cantidad']
        })

    # 5. Obtener horarios para la vista
    horarios_para_vista = obtener_horarios_empresa(cid)
    
    # 6. Renderizado final con todas las variables
    return render_template('hacer_pedido.html', 
                           empresa=empresa_actual,
                           platos=platos_db, 
                           franjas_horarias=franjas,
                           total_carrito=stats['subtotal'], 
                           costo_envio=stats['envio'], 
                           carrito_detalle=carrito_detalle,
                           carrito=carrito,
                           cid=cid,
                           promos_disponibles=promos_disponibles,
                           cupon_actual=cupon_actual,
                           puntos_actual=puntos_actual,
                           request_form=request_form,
                           HORARIOS_TURNOS=config_hoy['turnos'], #horarios_para_vista, 
                           abierto=abierto,
                           promociones=promociones_db) # <--- Variable garantizada



@app.route('/api/cart/decrease', methods=['POST'])
def decrease_cart_qty():
    data = request.json
    key = data.get('cart_key')
    
    if 'carrito' in session and key in session['carrito']:
        # Restamos 1 a la cantidad
        session['carrito'][key]['cantidad'] -= 1
        
        # Si llega a 0, eliminamos el producto del carrito
        if session['carrito'][key]['cantidad'] <= 0:
            del session['carrito'][key]
            
        session.modified = True
        return jsonify({"success": True})
    
    return jsonify({"success": False, "message": "Item no encontrado"}), 404




    
@app.route('/api/add_promo_cart', methods=['POST'])
def add_promo_cart():
    data = request.json
    promo_id = data.get('promo_id')
    
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM promociones WHERE id_promocion = ?", (promo_id,))
    promo = cursor.fetchone()
    
    if not promo:
        return jsonify({"success": False}), 404

    if 'carrito' not in session:
        session['carrito'] = {}
    
    # Creamos una clave única para la promo en el carrito
    cart_key = f"promo_{promo_id}"
    
    # Si ya estaba, sumamos 1, si no, la creamos
    if cart_key in session['carrito']:
        session['carrito'][cart_key]['cantidad'] += 1
    else:
        session['carrito'][cart_key] = {
            'id_plato': None, # Importante: No es un plato único
            'id_promocion': promo_id,
            'nombre': f"PROMO: {promo['nombre']}",
            'precio_total_unitario': promo['precio_total'],
            'cantidad': 1,
            'opciones_texto': "Combo / Promoción",
            'notas': ""
        }
    
    session.modified = True
    conn.close()
    return jsonify({"success": True})


    
import urllib.parse # <--- Añadir al inicio de app.py

@app.route('/pago/resultado/<status>')
def pago_resultado(status):
    id_pedido = request.args.get('id_pedido')
    
    if status == 'success':
        conn = conectar_db(); cursor = conn.cursor()
        #ahora = datetime.now().strftime('%Y-%m-%d %H:%M:= ?')
        ahora = get_now_iso() # <--- CAMBIO AQUÍ
        
        # 1. Ponemos el pedido en RECIBIDO
        cursor.execute("""
            UPDATE pedidos 
            SET estado_pago = 'Pagado', 
                estado_envio = 'Recibido', 
                fecha_pago = ? 
            WHERE id_pedido = ?
        """, (ahora, id_pedido))
        
        # 2. Registramos el dinero en caja
        cursor.execute("SELECT costo_total, id_empresa FROM pedidos WHERE id_pedido = ?", (id_pedido,))
        p = cursor.fetchone()
        cursor.execute("""
            INSERT INTO ingresos_egresos (tipo, monto, descripcion, fecha_hora, id_pedido_origen, id_empresa) 
            VALUES ('Ingreso', ?, ?, ?, ?, ?)
        """, (p['costo_total'], f"Pago Online Pedido #{id_pedido}", ahora, id_pedido, p['id_empresa']))
        
        conn.commit(); conn.close()
        
        # --- LÓGICA DE STOCK ---
        # Aquí descontamos los insumos porque el estado ya es 'Recibido'
        procesar_descuento_stock(id_pedido)
        
        # Buscamos el token para redirigir
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT token FROM pedidos WHERE id_pedido = ?", (id_pedido,))
        token = cursor.fetchone()['token']
        conn.close()
        
        flash("¡Pago confirmado! Tu pedido ya está en cocina.", "success")
        return redirect(url_for('seguimiento_pedido', token=token))
    
    else:
        flash("El pago no pudo procesarse.", "danger")
        return redirect(url_for('hacer_pedido'))
    
 
 
 
@app.route('/gestion/promociones/agregar', methods=['GET', 'POST'])
@login_required
def agregar_promocion():
    if not (current_user.has_role('super_admin') or current_user.has_role('admin_empresa')):
        abort(403)
    
    # 1. Abrimos la conexión al principio de la función
    conn = conectar_db(); cursor = conn.cursor()

    # Determinación de empresa
    if current_user.has_role('super_admin'):
        cid = request.args.get('id_empresa') or request.form.get('id_empresa') or DEFAULT_COMPANY_FOR_ORDERS
    else:
        cid = current_user.id_empresa

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        desc = request.form.get('descripcion')
        precio = request.form.get('precio')
        platos_ids = request.form.getlist('platos_seleccionados')
        
        # Captura de nuevos campos (Switch y Límites)
        es_combo_fijo = 1 if request.form.get('es_combo_fijo') == 'on' else 0
        min_items = int(request.form.get('min_items', 1))
        max_items = int(request.form.get('max_items', 1))

        # Lógica de imagen
        nombre_imagen = None
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = get_now_arg().strftime('%Y%m%d%H%M= ?')
                filename = f"promo_{timestamp}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                nombre_imagen = filename

        try:
            # Insertamos la promo
            cursor.execute("""
                INSERT INTO promociones (
                    nombre, descripcion, precio_total, id_empresa, activo, 
                    imagen, es_combo_fijo, min_items, max_items
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
            """, (nombre, desc, precio, cid, nombre_imagen, es_combo_fijo, min_items, max_items))
            promo_id = cursor.lastrowid
            
            # Vinculamos platos
            if platos_ids:
                for p_id in platos_ids:
                    cursor.execute("INSERT INTO promocion_platos (id_promocion, id_plato) VALUES (?, ?)", (promo_id, p_id))
            
            conn.commit()
            conn.close() # Cerramos solo porque vamos a redirigir (salimos de la función)
            flash("Promoción creada con éxito.", "success")
            return redirect(url_for('gestion_catalogo'))
        except Exception as e:
            conn.rollback()
            flash(f"Error al guardar: {e}", "danger")
            # Si hubo error, NO cerramos la conexión aquí porque el código sigue abajo 
            # para mostrar el formulario otra vez.

    # 2. Lógica para mostrar el formulario (GET o POST fallido)
    # Aquí es donde fallaba porque la conexión estaba cerrada
    try:
        cursor.execute("SELECT id_plato, nombre, precio FROM platos WHERE id_empresa = ? AND activo = 1", (cid,))
        platos_disponibles = cursor.fetchall()

        empresas = []
        if current_user.has_role('super_admin'):
            cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1")
            empresas = cursor.fetchall()
    except Exception as e:
        print(f"Error en consulta GET: {e}")
        platos_disponibles = []
        empresas = []

    conn.close() # Cerramos la conexión al final de todo
    return render_template('agregar_promocion.html', 
                           platos=platos_disponibles, 
                           id_empresa_actual=cid,
                           empresas_admin=empresas)

@app.route('/api/promocion/<int:id_promo>/datos')
def api_datos_promo(id_promo):
    """
    Devuelve los datos completos de la promo (incluyendo configuración de combo fijo)
    y la lista de platos asociados para que el cliente elija.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # 1. Buscamos toda la información de la promoción
        cursor.execute("SELECT * FROM promociones WHERE id_promocion = ?", (id_promo,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({"success": False, "message": "Promoción no encontrada"}), 404
        
        # Convertimos la fila a un diccionario de Python
        promo = dict(row)
        
        # --- BLOQUE DE SEGURIDAD DE TIPOS (PUNTO 2) ---
        # Forzamos la conversión a números. En SQLite, si no hacemos esto, 
        # los valores podrían llegar como texto y romper las comparaciones en JS.
        promo['es_combo_fijo'] = int(promo.get('es_combo_fijo', 0))
        promo['min_items'] = int(promo.get('min_items', 1))
        promo['max_items'] = int(promo.get('max_items', 1))
        promo['precio_total'] = float(promo.get('precio_total', 0))
        # -----------------------------------------------
        
        # 2. Buscamos los platos que el administrador vinculó a esta promoción
        # Nota: No traemos el precio individual de los platos para no confundir al cliente,
        # ya que el precio que manda es el de la PROMOCIÓN.
        cursor.execute("""
            SELECT p.id_plato, p.nombre, p.descripcion 
            FROM platos p 
            JOIN promocion_platos pp ON p.id_plato = pp.id_plato 
            WHERE pp.id_promocion = ? AND p.activo = 1
        """, (id_promo,))
        
        platos = [dict(r) for r in cursor.fetchall()]
        conn.close()
        
        # Retornamos los datos limpios al frontend
        return jsonify({
            "success": True,
            "promo": promo, 
            "platos": platos
        })

    except Exception as e:
        if conn:
            conn.close()
        print(f"Error crítico en api_datos_promo: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    
    
    

@app.route('/pedido/seguimiento/<token>')
def seguimiento_pedido(token):
    pedido = _obtener_pedido_por_token(token)
    if not pedido: 
        flash("Pedido no encontrado.", "danger")
        return redirect(url_for('index'))
    
    # Abrimos conexión para buscar datos de empresa y puntos del cliente
    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Buscamos los datos de la empresa (útil para mostrar info en el seguimiento)
    cursor.execute("SELECT nombre, telefono FROM empresas WHERE id_empresa = ?", (pedido.id_empresa,))
    empresa = cursor.fetchone()

    # 2. NUEVO: Buscamos los puntos acumulados del cliente (Lógica de Puntos CRM)
    puntos_totales = 0
    if pedido.id_cliente:
        cursor.execute("SELECT puntos FROM clientes WHERE id_cliente = ?", (pedido.id_cliente,))
        res_c = cursor.fetchone()
        if res_c:
            puntos_totales = res_c['puntos']
    
    conn.close()

    # --- CAMBIO PUNTO 4: ANULACIÓN DEL LINK DE WHATSAPP DEL CLIENTE ---
    # Forzamos la variable a None para que el botón de confirmación no aparezca
    # en el archivo HTML del cliente.
    whatsapp_url = None
    # ------------------------------------------------------------------

    # Retornamos el template incluyendo la variable puntos_cliente, pero sin el link de WhatsApp
    return render_template('pedido_seguimiento.html', 
                           pedido=pedido, 
                           whatsapp_url=whatsapp_url, 
                           puntos_cliente=puntos_totales)
    
    
    
  #Confirmacion de cliente por wsp  
#@app.route('/pedido/seguimiento/<token>')
#def seguimiento_pedido(token):
#    pedido = _obtener_pedido_por_token(token)
#    if not pedido: 
#        flash("Pedido no encontrado.", "danger")
#        return redirect(url_for('index'))
#    
#    # Abrimos conexión para buscar datos de empresa y puntos del cliente
#    conn = conectar_db(); cursor = conn.cursor()
#    
#    # 1. Buscamos los datos de la empresa para el link de WhatsApp (Original)
#    cursor.execute("SELECT nombre, telefono FROM empresas WHERE id_empresa = ?", (pedido.id_empresa,))
#    empresa = cursor.fetchone()
#
#    # 2. NUEVO: Buscamos los puntos acumulados del cliente (Lógica de Puntos CRM)
#    puntos_totales = 0
#    if pedido.id_cliente:
#        cursor.execute("SELECT puntos FROM clientes WHERE id_cliente = ?", (pedido.id_cliente,))
#        res_c = cursor.fetchone()
#        if res_c:
#            puntos_totales = res_c['puntos']
#    
#    conn.close()
#
#    # 3. Lógica para el link de WhatsApp (Original)
#    whatsapp_url = None
#    if pedido.estado_envio == 'Pendiente de WhatsApp' and empresa['telefono']:
#        # Preparamos el mensaje para el restaurante
#        mensaje = f"✅ *CONFIRMACIÓN DE PEDIDO #{pedido.id_pedido}*\n\n"
#        mensaje += f"Hola {empresa['nombre']}, mi nombre es {pedido.cliente_nombre}.\n"
#        mensaje += f"Confirmo mi pedido por un total de *${pedido.costo_total}*.\n\n"
#        mensaje += f"Link de seguimiento:\n{request.base_url}"
#        
#        # Limpiamos el teléfono (solo números)
#        tel_limpio = "".join(filter(str.isdigit, empresa['telefono']))
#        
#        # URL final
#        whatsapp_url = f"https://wa.me/{tel_limpio}?text={urllib.parse.quote(mensaje)}"
#
#    # Retornamos el template incluyendo la variable puntos_cliente
#    return render_template('pedido_seguimiento.html', 
#                           pedido=pedido, 
#                           whatsapp_url=whatsapp_url, 
#                           puntos_cliente=puntos_totales)


# Consulta de puntos
@app.route('/api/consultar_puntos', methods=['POST'])
def consultar_puntos():
    data = request.json
    telefono = data.get('telefono', '').strip()
    
    if not telefono:
        return jsonify({"success": False, "message": "Ingrese un teléfono."})

    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT puntos FROM clientes WHERE telefono = ?", (telefono,))
    res = cursor.fetchone()
    conn.close()

    if res:
        puntos = res['puntos']
        monto_descuento = puntos * VALOR_PESO_POR_PUNTO_CANJE
        return jsonify({
            "success": True, 
            "puntos": puntos, 
            "monto_pesos": monto_descuento
        })
    else:
        return jsonify({"success": False, "message": "Cliente no encontrado o sin puntos."})

@app.route('/api/aplicar_puntos', methods=['POST'])
def aplicar_puntos():
    data = request.json
    telefono = data.get('telefono', '').strip()
    puntos_a_canjear = int(data.get('puntos', 0))
    
    # Guardamos en sesión que el cliente quiere usar sus puntos
    session['puntos_a_canjear'] = {
        'telefono': telefono,
        'puntos': puntos_a_canjear,
        'descuento_pesos': puntos_a_canjear * VALOR_PESO_POR_PUNTO_CANJE
    }
    session.modified = True
    return jsonify({"success": True})

@app.route('/api/quitar_puntos', methods=['POST'])
def quitar_puntos():
    session.pop('puntos_a_canjear', None)
    return jsonify({"success": True})







# --- Gestión ---
@app.route('/gestion/pedidos')
@login_required
def gestion_pedidos():
    conn = conectar_db(); cursor = conn.cursor()
    
    # --- CAPTURAR FILTROS DE LA URL ---
    f_envio = request.args.get('f_envio', '').strip()
    f_pago = request.args.get('f_pago', '').strip()
    f_tipo = request.args.get('f_tipo', '').strip() # <--- NUEVO FILTRO
    
    # --- 1. LÓGICA DE ALERTAS DE STOCK BAJO ---
    alertas_stock = []
    try:
        if current_user.has_role('super_admin', 'admin_empresa'):
            cursor.execute("""
                SELECT i.*, e.nombre as empresa_n 
                FROM insumos i 
                JOIN empresas e ON i.id_empresa = e.id_empresa
                WHERE i.stock_actual <= i.stock_minimo
            """)
        else:
            cursor.execute("""
                SELECT * FROM insumos 
                WHERE stock_actual <= stock_minimo AND id_empresa = ?
            """, (current_user.id_empresa,))
        alertas_stock = cursor.fetchall()
    except sqlite3.OperationalError:
        alertas_stock = []

    # --- 2. LÓGICA DE PEDIDOS CON PRIORIDAD (FILTRADA) ---
    # Empezamos con la base. Nota: No cerramos la consulta con ";" para poder agregar filtros.
    base = """
        SELECT p.*, r.nombre as rep_n, e.nombre as empresa_n 
        FROM pedidos p 
        LEFT JOIN repartidores r ON p.id_repartidor = r.id_repartidor 
        LEFT JOIN empresas e ON p.id_empresa = e.id_empresa
        WHERE date(p.horario_entrega) >= date('now', 'localtime')
    """
    hoy_arg = get_now_arg().strftime('%Y-%m-%d')
    params = []

    # A. Filtro de Empresa (Seguridad Multi-sucursal)
    cond_cia, params_cia = get_company_filter_conditions_and_params(table_alias='p')
    if cond_cia: 
        base += " AND " + " AND ".join(cond_cia)
        params.extend(params_cia)
    
    # --- NUEVO: APLICACIÓN REAL DE LOS FILTROS DE LA BARRA ---
    if f_envio:
        base += " AND p.estado_envio = ?"
        params.append(f_envio)
    
    if f_pago:
        base += " AND p.estado_pago = ?"
        params.append(f_pago)
        
        
    # --- NUEVO: FILTRO DE TIPO DE ENTREGA ---
    if f_tipo == '1': # Domicilio
        base += " AND p.es_envio = 1"
    elif f_tipo == '0': # Local
        base += " AND p.es_envio = 0"
    # ----------------------------------------
    # --------------------------------------------------------

    
    base += """
        ORDER BY 
            CASE 
                WHEN p.estado_envio NOT IN ('Entregado', 'Cancelado') THEN 1
                WHEN p.estado_envio = 'Entregado' THEN 2
                ELSE 3 
            END ASC,
            p.horario_entrega ASC
    """
    
    cursor.execute(base, params)
    resultados = cursor.fetchall()
    
    pedidos_p = []
    for r in resultados:
        p = dict(r)
        try:
            p['horario_entrega_dt'] = datetime.strptime(p['horario_entrega'], '%Y-%m-%d %H:%M:= ?')
        except:
            p['horario_entrega_dt'] = None
        pedidos_p.append(p)

    # --- 3. LÓGICA DE REPARTIDORES (SOLO ACTIVOS) ---
    try:
        id_e = int(current_user.id_empresa)
    except:
        id_e = None

    if current_user.has_role('super_admin', 'admin_empresa'):
        cursor.execute("SELECT * FROM repartidores WHERE activo = 1")
    else:
        cursor.execute("""
            SELECT * FROM repartidores 
            WHERE id_empresa = ? AND activo = 1
        """, (id_e,))
    
    reps = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Log para que verifiques en tu terminal
    print(f"DEBUG: Filtros Aplicados -> Envio: {f_envio} | Pago: {f_pago}")

    # --- 4. RENDERIZADO FINAL ---
    return render_template('gestion_pedidos.html', 
                           pedidos=pedidos_p, 
                           repartidores=reps, 
                           alertas_stock=alertas_stock,
                           f_envio=f_envio, 
                           f_pago=f_pago,
                           f_tipo=f_tipo) # <--- PASAR f_tipo AL HTML


    
# --- GESTIÓN DE INSUMOS (Materia Prima) ---
@app.route('/gestion/insumos', methods=['GET', 'POST'])
@login_required
def gestion_insumos():
    conn = conectar_db(); cursor = conn.cursor()
    
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        unidad = request.form.get('unidad_medida')
        # Cantidad que estamos comprando/ingresando ahora
        cantidad_ingresada = float(request.form.get('stock_actual', 0))
        stock_m = float(request.form.get('stock_minimo', 0))
        precio_c = float(request.form.get('precio_compra', 0))
        
        eid = current_user.id_empresa if current_user.id_empresa else DEFAULT_COMPANY_FOR_ORDERS

        # 1. VALIDACIÓN: ¿Ya existe este insumo en esta empresa?
        cursor.execute("SELECT id_insumo, stock_actual FROM insumos WHERE nombre = ? AND id_empresa = ?", (nombre, eid))
        insumo_existente = cursor.fetchone()

        if insumo_existente:
            # 2. SI EXISTE: Sumamos el stock y actualizamos el precio de compra
            nuevo_stock = insumo_existente['stock_actual'] + cantidad_ingresada
            cursor.execute("""
                UPDATE insumos 
                SET stock_actual = ?, precio_compra = ?, stock_minimo = ?
                WHERE id_insumo = ?
            """, (nuevo_stock, precio_c, stock_m, insumo_existente['id_insumo']))
            flash(f"Se sumaron {cantidad_ingresada} {unidad} a '{nombre}'. Stock total actualizado.", "info")
        else:
            # 3. NO EXISTE: Creamos el registro nuevo
            cursor.execute("""
                INSERT INTO insumos (nombre, unidad_medida, stock_actual, stock_minimo, precio_compra, id_empresa)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (nombre, unidad, cantidad_ingresada, stock_m, precio_c, eid))
            flash(f"Nuevo insumo '{nombre}' registrado con éxito.", "success")
        
        conn.commit()

    # --- LISTADO ---
    if current_user.has_role('super_admin'):
        cursor.execute("SELECT i.*, e.nombre as empresa_n FROM insumos i LEFT JOIN empresas e ON i.id_empresa = e.id_empresa")
    else:
        cursor.execute("SELECT * FROM insumos WHERE id_empresa = ?", (current_user.id_empresa,))
    
    insumos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('gestion_insumos.html', insumos=insumos)



# --- GESTIÓN DE RECETAS (Vincular Plato con Insumo) ---
@app.route('/gestion/plato/<int:id_plato>/receta', methods=['GET', 'POST'])
@login_required
def gestion_receta(id_plato):
    conn = conectar_db(); cursor = conn.cursor()

    # 1. Buscamos los datos del plato y sus opciones (modificadores)
    cursor.execute("SELECT * FROM platos WHERE id_plato = ?", (id_plato,))
    plato = cursor.fetchone()
    
    if not plato:
        conn.close(); abort(404)

    # Traemos todas las opciones (variantes) del plato para el selector
    cursor.execute("""
        SELECT po.id_opcion, po.nombre as opcion_n, pm.nombre as mod_n 
        FROM plato_opciones po 
        JOIN plato_modificadores pm ON po.id_modificador = pm.id_modificador 
        WHERE pm.id_plato = ?
    """, (id_plato,))
    opciones_plato = [dict(row) for row in cursor.fetchall()]

    target_eid = plato['id_empresa']

    if request.method == 'POST':
        tipo_destino = request.form.get('tipo_destino') # 'base' o 'opt_ID'
        id_insumo = request.form.get('id_insumo')
        cantidad = float(request.form.get('cantidad'))
        
        if tipo_destino == 'base':
            # --- LÓGICA RECETA BASE ---
            cursor.execute("SELECT id_receta FROM recetas WHERE id_plato = ? AND id_insumo = ?", (id_plato, id_insumo))
            existente = cursor.fetchone()
            if existente:
                cursor.execute("UPDATE recetas SET cantidad_requerida = ? WHERE id_receta = ?", (cantidad, existente['id_receta']))
                flash("Ingrediente base actualizado.", "success")
            else:
                cursor.execute("INSERT INTO recetas (id_plato, id_insumo, cantidad_requerida) VALUES (?, ?, ?)", (id_plato, id_insumo, cantidad))
                flash("Ingrediente base añadido.", "success")
        else:
            # --- LÓGICA EXTRAS (VARIANTES) ---
            id_opcion = tipo_destino.replace('opt_', '')
            cursor.execute("SELECT id FROM opciones_insumos WHERE id_opcion = ? AND id_insumo = ?", (id_opcion, id_insumo))
            existente = cursor.fetchone()
            if existente:
                cursor.execute("UPDATE opciones_insumos SET cantidad_requerida = ? WHERE id = ?", (cantidad, existente['id']))
                flash("Ingrediente de variante actualizado.", "success")
            else:
                cursor.execute("INSERT INTO opciones_insumos (id_opcion, id_insumo, cantidad_requerida) VALUES (?, ?, ?)", (id_opcion, id_insumo, cantidad))
                flash("Ingrediente añadido a la variante.", "success")
            
        conn.commit()

    # 2. Insumos disponibles de la empresa
    cursor.execute("SELECT * FROM insumos WHERE id_empresa = ?", (target_eid,))
    insumos_disponibles = [dict(row) for row in cursor.fetchall()]

    # 3. Traemos la RECETA UNIFICADA (Base + Extras) para mostrar en la tabla
    # Ingredientes Base
    cursor.execute("""
        SELECT r.id_receta as id_u, r.cantidad_requerida, i.nombre, i.unidad_medida, i.precio_compra, 
               'Base' as aplica_a, 'base' as origen
        FROM recetas r 
        JOIN insumos i ON r.id_insumo = i.id_insumo 
        WHERE r.id_plato = ?
    """, (id_plato,))
    receta_base = cursor.fetchall()

    # Ingredientes de Extras
    cursor.execute("""
        SELECT oi.id as id_u, oi.cantidad_requerida, i.nombre, i.unidad_medida, i.precio_compra, 
               po.nombre as aplica_a, 'opcion' as origen
        FROM opciones_insumos oi 
        JOIN insumos i ON oi.id_insumo = i.id_insumo 
        JOIN plato_opciones po ON oi.id_opcion = po.id_opcion
        JOIN plato_modificadores pm ON po.id_modificador = pm.id_modificador
        WHERE pm.id_plato = ?
    """, (id_plato,))
    receta_extras = cursor.fetchall()

    # Combinamos ambas listas para la tabla
    receta_completa = [dict(r) for r in receta_base] + [dict(r) for r in receta_extras]
    
    conn.close()
    return render_template('gestion_receta.html', 
                           plato=plato, 
                           insumos=insumos_disponibles, 
                           receta=receta_completa,
                           opciones=opciones_plato)
    

@app.route('/gestion/receta/eliminar_universal/<int:id_u>/<string:tipo>', methods=['POST'])
@login_required
def eliminar_ingrediente_universal(id_u, tipo):
    conn = conectar_db(); cursor = conn.cursor()
    id_plato = request.referrer.split('/')[-2] # Truco para volver a la misma página

    if tipo == 'base':
        cursor.execute("DELETE FROM recetas WHERE id_receta = ?", (id_u,))
    else:
        cursor.execute("DELETE FROM opciones_insumos WHERE id = ?", (id_u,))
    
    conn.commit(); conn.close()
    flash("Ingrediente eliminado.", "info")
    return redirect(request.referrer)


@app.route('/gestion/reporte_rentabilidad')
@login_required
def reporte_rentabilidad():
    if not current_user.has_role('admin_empresa') and not current_user.has_role('super_admin'):
        abort(403)
    ahora = get_now_arg()
    start_date = request.args.get('start', (ahora - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end', ahora.strftime('%Y-%m-%d'))
    #start_date = request.args.get('start', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    #end_date = request.args.get('end', datetime.now().strftime('%Y-%m-%d'))
    cid = current_user.id_empresa if not current_user.has_role('super_admin') else request.args.get('cid')

    conn = conectar_db(); cursor = conn.cursor()
    
    # Pedidos entregados
    cursor.execute("""
        SELECT * FROM pedidos 
        WHERE date(fecha_creacion) BETWEEN ? AND ? 
        AND estado_envio = 'Entregado'
        """ + (" AND id_empresa = ?" if cid else ""), 
        [start_date, end_date, cid] if cid else [start_date, end_date])
    pedidos = [dict(row) for row in cursor.fetchall()]

    # Egresos de caja
    cursor.execute("""
        SELECT * FROM ingresos_egresos 
        WHERE tipo = 'Egreso' 
        AND date(fecha_hora) BETWEEN ? AND ?
        """ + (" AND id_empresa = ?" if cid else ""), 
        [start_date, end_date, cid] if cid else [start_date, end_date])
    egresos_lista = [dict(row) for row in cursor.fetchall()]

    # INICIALIZACIÓN COMPLETA (Aseguramos que 'descuentos' exista)
    totales = {
        'ingreso_bruto': 0,        # Venta total antes de descuentos
        'descuentos': 0,           # Cupones y puntos aplicados
        'ingreso_neto': 0,         # Lo que realmente entró a caja (Bruto - Descuento)
        'costo_materia_prima': 0,
        'egresos_repartidores': 0,
        'egresos_manuales': 0,
        'utilidad_neta': 0
    }

    for p in pedidos:
        id_p = p['id_pedido']
        costo_recetas = 0
        
        # Calcular costos (Recetas base)
        cursor.execute("SELECT ip.cantidad, r.cantidad_requerida, i.precio_compra FROM items_pedido ip JOIN recetas r ON ip.id_plato = r.id_plato JOIN insumos i ON r.id_insumo = i.id_insumo WHERE ip.id_pedido = ?", (id_p,))
        for ing in cursor.fetchall():
            costo_recetas += (ing['cantidad'] * ing['cantidad_requerida'] * ing['precio_compra'])

        # Calcular costos (Modificadores/Extras)
        cursor.execute("SELECT ip.cantidad, oi.cantidad_requerida, ins.precio_compra FROM items_pedido ip JOIN items_pedido_modificadores ipm ON ip.id = ipm.id_item_pedido JOIN plato_opciones po ON ipm.nombre_opcion = po.nombre JOIN opciones_insumos oi ON po.id_opcion = oi.id_opcion JOIN insumos ins ON oi.id_insumo = ins.id_insumo WHERE ip.id_pedido = ?", (id_p,))
        for extra in cursor.fetchall():
            costo_recetas += (extra['cantidad'] * extra['cantidad_requerida'] * extra['precio_compra'])

        # ACUMULAR DATOS
        venta_real_comida = p['costo_total'] - p['costo_envio']
        totales['descuentos'] += (p['descuento_aplicado'] or 0)
        totales['ingreso_neto'] += venta_real_comida
        totales['ingreso_bruto'] += (venta_real_comida + (p['descuento_aplicado'] or 0))
        totales['costo_materia_prima'] += costo_recetas

    for e in egresos_lista:
        if e['id_repartidor_origen']: totales['egresos_repartidores'] += e['monto']
        else: totales['egresos_manuales'] += e['monto']

    # GANANCIA FINAL
    totales['utilidad_neta'] = totales['ingreso_neto'] - totales['costo_materia_prima'] - totales['egresos_repartidores'] - totales['egresos_manuales']

    conn.close()
    return render_template('reporte_rentabilidad.html', totales=totales, egresos_detalle=egresos_lista, start=start_date, end=end_date)



    
@app.route('/gestion/receta/eliminar/<int:id_receta>', methods=['POST'])
@login_required
def eliminar_ingrediente_receta(id_receta):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT id_plato FROM recetas WHERE id_receta = ?", (id_receta,))
    res = cursor.fetchone()
    if res:
        pid = res['id_plato']
        cursor.execute("DELETE FROM recetas WHERE id_receta = ?", (id_receta,))
        conn.commit()
        flash("Componente eliminado.", "info")
        conn.close()
        return redirect(url_for('gestion_receta', id_plato=pid))
    conn.close()
    return redirect(url_for('gestion_catalogo'))    


@app.route('/gestion/insumos/editar/<int:id_insumo>', methods=['GET', 'POST'])
@login_required
def editar_insumo(id_insumo):
    conn = conectar_db(); cursor = conn.cursor()
    
    # Buscamos el insumo
    cursor.execute("SELECT * FROM insumos WHERE id_insumo = ?", (id_insumo,))
    insumo = cursor.fetchone()
    
    if not insumo:
        conn.close(); abort(404)

    # Seguridad: Solo el dueño de la empresa puede editarlo
    verificar_acceso_empresa(insumo['id_empresa'])

    if request.method == 'POST':
        n = request.form.get('nombre')
        u = request.form.get('unidad_medida')
        s_min = float(request.form.get('stock_minimo', 0))
        p_compra = float(request.form.get('precio_compra', 0))

        cursor.execute("""
            UPDATE insumos 
            SET nombre=?, unidad_medida=?, stock_minimo=?, precio_compra=?
            WHERE id_insumo=?
        """, (n, u, s_min, p_compra, id_insumo))
        conn.commit(); conn.close()
        flash("Insumo actualizado.", "success")
        return redirect(url_for('gestion_insumos'))

    conn.close()
    return render_template('editar_insumo.html', insumo=insumo)


@app.route('/gestion/opcion/<int:id_opcion>/receta', methods=['GET', 'POST'])
@login_required
def gestion_receta_opcion(id_opcion):
    conn = conectar_db(); cursor = conn.cursor()

    # 1. Buscamos los datos de la opción y el plato al que pertenece
    cursor.execute("""
        SELECT po.nombre as opcion_nombre, pm.nombre as modificador_nombre, p.id_empresa, p.nombre as plato_nombre, p.id_plato
        FROM plato_opciones po
        JOIN plato_modificadores pm ON po.id_modificador = pm.id_modificador
        JOIN platos p ON pm.id_plato = p.id_plato
        WHERE po.id_opcion = ?
    """, (id_opcion,))
    data = cursor.fetchone()

    if request.method == 'POST':
        id_insumo = request.form.get('id_insumo')
        cantidad = float(request.form.get('cantidad'))
        
        # Guardar ingrediente para la variante
        cursor.execute("""
            INSERT INTO opciones_insumos (id_opcion, id_insumo, cantidad_requerida) 
            VALUES (?, ?, ?)
        """, (id_opcion, id_insumo, cantidad))
        conn.commit()
        flash("Ingrediente añadido a la variante.", "success")

    # 2. Insumos disponibles y receta de la variante
    cursor.execute("SELECT * FROM insumos WHERE id_empresa = ?", (data['id_empresa'],))
    insumos_disponibles = cursor.fetchall()

    cursor.execute("""
        SELECT oi.*, i.nombre, i.unidad_medida, i.precio_compra 
        FROM opciones_insumos oi 
        JOIN insumos i ON oi.id_insumo = i.id_insumo 
        WHERE oi.id_opcion = ?
    """, (id_opcion,))
    receta_variante = cursor.fetchall()
    
    conn.close()
    return render_template('gestion_receta_opcion.html', data=data, insumos=insumos_disponibles, receta=receta_variante)


    
#@app.route('/gestion/pedido/<int:id_pedido>/detalle')
#@login_required
#def detalle_pedido(id_pedido):
#    pedido = _obtener_pedido_completo_por_id(id_pedido)
#    if not pedido:
#        # Si el pedido no es suyo o no existe, lanzamos un 404 o 403
#        flash("Pedido no encontrado o acceso denegado.", "danger")
#        return redirect(url_for('gestion_pedidos'))
#    
#    # Doble verificación por seguridad
#    verificar_acceso_empresa(pedido.id_empresa)
#    
#    return render_template('pedido_confirmacion.html', pedido=pedido, ticket_html=pedido.generar_ticket(), admin_view=True)

@app.route('/gestion/pedido/<int:id_pedido>/detalle')
@login_required
def detalle_pedido(id_pedido):
    pedido = _obtener_pedido_completo_por_id(id_pedido)
    if not pedido:
        flash("Pedido no encontrado.", "danger")
        return redirect(url_for('gestion_pedidos'))
    
    verificar_acceso_empresa(pedido.id_empresa)
    
    # Traer nombre de la empresa para el ticket
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM empresas WHERE id_empresa = ?", (pedido.id_empresa,))
    empresa = cursor.fetchone(); conn.close()
    nombre_e = empresa['nombre'] if empresa else "Restaurante"

    # RENDERIZAMOS EL TICKET USANDO EL TEMPLATE
    ticket_html = render_template('tickets/pedido_ticket.html', pedido=pedido, nombre_empresa=nombre_e)
    
    return render_template('pedido_confirmacion.html', pedido=pedido, ticket_html=ticket_html, admin_view=True)


    
@app.route('/gestion/pedido/<int:id_pedido>/imprimir')
@login_required
def imprimir_pedido(id_pedido):
    # 1. Obtenemos el pedido completo
    pedido = _obtener_pedido_completo_por_id(id_pedido)
    if not pedido: abort(404)
    
    # 2. Obtenemos datos de la empresa
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM empresas WHERE id_empresa = ?", (pedido.id_empresa,))
    empresa = cursor.fetchone(); conn.close()
    nombre_e = empresa['nombre'] if empresa else "Restaurante"
    
    # 3. Renderizamos las dos partes del ticket por separado
    # (Asegúrate de haber creado estos archivos en la carpeta templates/tickets/)
    t_cocina = render_template('tickets/pedido_ticket_cocina.html', 
                               pedido=pedido, 
                               nombre_empresa=nombre_e)
    
    t_cliente = render_template('tickets/pedido_ticket_cliente.html', 
                                pedido=pedido, 
                                nombre_empresa=nombre_e,
                                empresa_datos=empresa)
    
    # --- AQUÍ APLICAS EL CAMBIO ---
    # Esta línea une todo y lo manda al navegador para imprimir
    return render_template('tickets/imprimir_wrapper_dual.html', 
                           ticket_cocina=t_cocina, 
                           ticket_cliente=t_cliente, 
                           id_pedido=id_pedido)
    
    
    

# Ejemplo de cómo actualizar los estados en tus rutas de gestión:
# Modificación sugerida en app.py
@app.route('/gestion/pedido/<int:id_pedido>/actualizar_estado_envio', methods=['POST'])
@login_required
def actualizar_estado_envio(id_pedido):
    nuevo_estado = request.form.get('nuevo_estado')
    ahora_str = get_now_iso()
    #ahora = datetime.now().strftime('%Y-%m-%d %H:%M:= ?')
    
    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Obtenemos los datos actuales del pedido antes de actualizar
    cursor.execute("SELECT id_cliente, costo_total, estado_envio FROM pedidos WHERE id_pedido = ?", (id_pedido,))
    pedido = cursor.fetchone()

    if not pedido:
        conn.close(); abort(404)

    columna_fecha = ""
    if nuevo_estado == 'En Preparación': columna_fecha = "fecha_preparacion"
    elif nuevo_estado == 'En Camino': columna_fecha = "fecha_despacho"
    elif nuevo_estado == 'Entregado': columna_fecha = "fecha_entrega"

    # 2. LÓGICA DE PUNTOS: Si el nuevo estado es 'Entregado' y antes no lo estaba
    if nuevo_estado == 'Entregado' and pedido['estado_envio'] != 'Entregado' and pedido['id_cliente']:
        # Calculamos los puntos (Ej: $10.000 * 0.01 = 100 puntos)
        puntos_ganados = int(float(pedido['costo_total']) * VALOR_PUNTO_POR_PESO)
        
        # Acreditamos los puntos al cliente en la tabla CRM
        cursor.execute("UPDATE clientes SET puntos = puntos + ? WHERE id_cliente = ?", 
                       (puntos_ganados, pedido['id_cliente']))
        
        print(f"PUNTOS CRM: Cliente {pedido['id_cliente']} ganó {puntos_ganados} puntos.")

    # 3. Actualizamos el estado del pedido
    if columna_fecha:
        cursor.execute(f"UPDATE pedidos SET estado_envio = ?, {columna_fecha} = ? WHERE id_pedido = ?", 
                       (nuevo_estado, ahora_str, id_pedido))
    else:
        cursor.execute("UPDATE pedidos SET estado_envio = ? WHERE id_pedido = ?", (nuevo_estado, id_pedido))
    
    conn.commit(); conn.close()
    
    # --- REDIRECCIÓN INTELIGENTE ---
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'api' in request.path:
        return jsonify({"success": True})
        
    # Si el usuario es un repartidor, lo mandamos a su panel de entregas
    if current_user.has_role('repartidor'):
        flash(f"¡Pedido #{id_pedido} actualizado con éxito!", "success")
        return redirect(url_for('panel_repartidor'))
    
    # Si es administrador o empleado del local, lo mandamos al detalle normal
    # return redirect(url_for('detalle_pedido', id_pedido=id_pedido))
    return redirect(url_for('gestion_pedidos')) # <--- ESTO ES LO QUE CAMBIAMOS




# --- RUTA 1: CONFIRMACIÓN INICIAL ---
@app.route('/gestion/pedido/<int:id_pedido>/confirmar_whatsapp', methods=['POST'])
@login_required
def confirmar_whatsapp(id_pedido):
    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Capturamos la hora que editaste en el panel
    nueva_hora = request.form.get('nueva_hora')
    
    # 2. ACTUALIZAMOS ESTADO A 'RECIBIDO' Y LA NUEVA HORA
    if nueva_hora:
        hoy = get_now_arg().strftime('%Y-%m-%d')
        horario_final = f"{hoy} {nueva_hora}:00"
        cursor.execute("""
            UPDATE pedidos 
            SET estado_envio = 'Recibido', 
                horario_entrega = ? 
            WHERE id_pedido = ?
        """, (horario_final, id_pedido))
    else:
        # Por si no cambias la hora, solo cambiamos el estado
        cursor.execute("UPDATE pedidos SET estado_envio = 'Recibido' WHERE id_pedido = ?", (id_pedido,))
    
    conn.commit(); conn.close()

    # 3. AHORA SÍ: Descontamos stock (porque ya lo aceptaste)
    try:
        procesar_descuento_stock(id_pedido)
    except Exception as e:
        print(f"Error stock: {e}")

    # 4. Buscamos datos para el mensaje (Usando tu lógica de Puente)
    pedido = _obtener_pedido_completo_por_id(id_pedido)
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM empresas WHERE id_empresa = ?", (pedido.id_empresa,))
    res_e = cursor.fetchone()
    nombre_e = res_e['nombre'] if res_e else "Tasty Food"
    alias = cargar_configuracion('TRANSFERENCIA_ALIAS', 'Consultar', pedido.id_empresa)
    conn.close()

    tel = "".join(filter(str.isdigit, str(pedido.telefono_cliente)))
    if len(tel) == 10: tel = "549" + tel

    # 5. Enviamos al template del puente (compartir_whatsapp.html)
    return render_template('compartir_whatsapp.html', 
                           pedido=pedido, nombre_e=nombre_e, 
                           alias=alias, tel=tel, tipo='confirmacion')

# --- RUTA 2: REENVÍO MANUAL (Recordatorio) ---
@app.route('/gestion/pedido/<int:id_pedido>/enviar_confirmacion_cliente')
@login_required
def enviar_confirmacion_cliente(id_pedido):
    pedido = _obtener_pedido_completo_por_id(id_pedido)
    if not pedido:
        flash("Pedido no encontrado.", "danger")
        return redirect(url_for('gestion_pedidos'))

    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM empresas WHERE id_empresa = ?", (pedido.id_empresa,))
    res_e = cursor.fetchone()
    nombre_e = res_e['nombre'] if res_e else "Tasty"
    alias = cargar_configuracion('TRANSFERENCIA_ALIAS', 'Consultar', pedido.id_empresa)
    conn.close()

    tel = "".join(filter(str.isdigit, str(pedido.telefono_cliente)))
    if len(tel) == 10: tel = "549" + tel

    return render_template('compartir_whatsapp.html', 
                           pedido=pedido, nombre_e=nombre_e, 
                           alias=alias, tel=tel, tipo='reenvio')
    
    
@app.route('/gestion/pedido/<int:id_pedido>/marcar_pagado', methods=['POST'])
@login_required
def marcar_pedido_pagado(id_pedido):
    p = _obtener_pedido_completo_por_id(id_pedido)
    conn = conectar_db(); cursor = conn.cursor(); f = datetime.now().strftime('%Y-%m-%d %H:%M:= ?')
    ahora = get_now_iso() # <--- CAMBIO AQUÍ
    cursor.execute("UPDATE pedidos SET estado_pago = 'Pagado', fecha_pago = ? WHERE id_pedido = ?", (ahora, id_pedido))
    cursor.execute("INSERT INTO ingresos_egresos (tipo, monto, descripcion, fecha_hora, id_pedido_origen, id_empresa) VALUES ('Ingreso', ?, ?, ?, ?, ?)", (p.costo_total, f"Pago #{id_pedido}", ahora, id_pedido, p.id_empresa))
    conn.commit(); conn.close(); return redirect(url_for('gestion_pedidos'))

@app.route('/gestion/pedido/<int:id_pedido>/asignar_repartidor', methods=['POST'])
@login_required
def asignar_repartidor(id_pedido):
    rid = request.form.get('id_repartidor')
    conn = conectar_db(); cursor = conn.cursor(); cursor.execute("UPDATE pedidos SET id_repartidor = ? WHERE id_pedido = ?", (rid, id_pedido)); conn.commit(); conn.close()
    return redirect(url_for('gestion_pedidos'))

@app.route('/gestion/repartidores', methods=['GET', 'POST'])
@login_required
def gestion_repartidores():
    conn = conectar_db(); cursor = conn.cursor(); cursor.execute("SELECT * FROM repartidores"); reps = cursor.fetchall(); conn.close()
    return render_template('gestion_repartidores.html', repartidores=reps)

@app.route('/gestion/repartidores/agregar', methods=['GET', 'POST'])
@login_required
def agregar_repartidor():
    if request.method == 'POST':
        # 1. Obtenemos los datos del formulario
        nombre = request.form.get('nombre', '').strip()
        apellido = request.form.get('apellido', '').strip()
        telefono = request.form.get('telefono', '').strip()
        
        # 2. Determinamos la empresa (si es super_admin la elige, si no, es la suya)
        if current_user.has_role('super_admin'):
            id_empresa = request.form.get('id_empresa_asignar')
            if not id_empresa:
                id_empresa = DEFAULT_COMPANY_FOR_ORDERS
        else:
            id_empresa = current_user.id_empresa

        # 3. Validación básica
        if not nombre or not apellido:
            flash("Nombre y Apellido son campos obligatorios.", "danger")
            return redirect(url_for('agregar_repartidor'))

        # 4. Guardamos en la base de datos
        try:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO repartidores (nombre, apellido, telefono, activo, id_empresa) 
                VALUES (?, ?, ?, 1, ?)
            """, (nombre, apellido, telefono, id_empresa))
            conn.commit()
            conn.close()
            flash(f"Repartidor {nombre} {apellido} guardado con éxito.", "success")
            return redirect(url_for('gestion_repartidores'))
        except Exception as e:
            flash(f"Error al guardar: {e}", "danger")
            return redirect(url_for('agregar_repartidor'))

    # Si es GET, mostramos el formulario
    empresas = []
    if current_user.has_role('super_admin'):
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1")
        empresas = cursor.fetchall()
        conn.close()
    
    return render_template('agregar_repartidor.html', empresas_disponibles=empresas)


@app.route('/gestion/repartidores/editar/<int:id_repartidor>', methods=['GET', 'POST'])
@login_required
def editar_repartidor(id_repartidor):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM repartidores WHERE id_repartidor = ?", (id_repartidor,))
    r = cursor.fetchone()
    
    if not r:
        conn.close(); abort(404)
    
    # VALIDACIÓN CLAVE:
    verificar_acceso_empresa(r['id_empresa'])
    
    if request.method == 'POST':
        # ... (lógica de actualización que ya tienes)
        n, a, t = request.form['nombre'], request.form['apellido'], request.form['telefono']
        ac = (1 if 'activo' in request.form else 0)
        cursor.execute("UPDATE repartidores SET nombre=?, apellido=?, telefono=?, activo=? WHERE id_repartidor=?", (n, a, t, ac, id_repartidor))
        conn.commit(); conn.close()
        return redirect(url_for('gestion_repartidores'))
    
    conn.close()
    return render_template('editar_repartidor.html', repartidor=r)


@app.route('/gestion/repartidores/eliminar/<int:id_repartidor>', methods=['POST'])
@login_required
def eliminar_repartidor(id_repartidor):
    conn = conectar_db(); cursor = conn.cursor(); cursor.execute("UPDATE repartidores SET activo = 0 WHERE id_repartidor = ?", (id_repartidor,)); conn.commit(); conn.close()
    return redirect(url_for('gestion_repartidores'))

@app.route('/gestion/reporte_repartidores', methods=['GET', 'POST'])
@login_required
def reporte_repartidores():
    conn = conectar_db(); cursor = conn.cursor()
    
    # --- CORRECCIÓN DE BÚSQUEDA DE REPARTIDORES ---
    if current_user.has_role('super_admin', 'admin_empresa'):
        # El super_admin ve a todos los repartidores activos de todas las empresas
        cursor.execute("SELECT id_repartidor, nombre, apellido FROM repartidores WHERE activo = 1")
    else:
        # El admin de empresa ve solo sus repartidores
        cursor.execute("""
            SELECT id_repartidor, nombre, apellido 
            FROM repartidores 
            WHERE activo = 1 AND id_empresa = ?
        """, (current_user.id_empresa,))
    
    repartidores = cursor.fetchall()
    # ----------------------------------------------

    reporte = None
    if request.method == 'POST':
        id_r = request.form.get('id_repartidor')
        # ... (el resto de tu lógica POST sigue igual)
        fi = request.form.get('fecha_inicio') + " 00:00:00"
        ff = request.form.get('fecha_fin') + " 23:59:59"
        
        cursor.execute("""
            SELECT id_pedido, cliente_nombre, cliente_apellido, fecha_creacion, costo_envio 
            FROM pedidos 
            WHERE id_repartidor = ? AND estado_envio = 'Entregado' 
            AND pago_repartidor_status = 'Pendiente'
            AND fecha_creacion BETWEEN ? AND ?
        """, (id_r, fi, ff))
        viajes = [dict(v) for v in cursor.fetchall()]
        
        cursor.execute("SELECT nombre, apellido, id_empresa FROM repartidores WHERE id_repartidor = ?", (id_r,))
        rep_info = cursor.fetchone()

        if rep_info:
            reporte = {
                'repartidor': f"{rep_info['nombre']} {rep_info['apellido']}",
                'id_repartidor': id_r,
                'viajes': viajes,
                'pago_por_viaje': get_pago_repartidor(rep_info['id_empresa']), # Usamos el costo de su empresa
                'fecha_inicio': request.form.get('fecha_inicio'),
                'fecha_fin': request.form.get('fecha_fin')
            }

    conn.close()
    return render_template('reporte_repartidores.html', repartidores=repartidores, reporte=reporte, now=get_now_arg())



@app.route('/gestion/procesar_pago_repartidor', methods=['POST'])
@login_required
def procesar_pago_repartidor():
    ids_pedidos = request.form.getlist('pedidos_a_pagar') # Recibe lista de IDs seleccionados
    id_r = request.form.get('id_repartidor')
    nombre_rep = request.form.get('nombre_repartidor')
    
    if not ids_pedidos:
        flash("No seleccionaste ningún viaje para pagar.", "warning")
        return redirect(url_for('reporte_repartidores'))

    conn = conectar_db(); cursor = conn.cursor()
    
    try:
        # 1. BUSCAMOS LA EMPRESA DEL REPARTIDOR
        cursor.execute("SELECT id_empresa FROM repartidores WHERE id_repartidor = ?", (id_r,))
        rep_data = cursor.fetchone()
        
        # --- LÓGICA DE ASIGNACIÓN DE EMPRESA PARA CAJA ---
        # Priorizamos el ID de la empresa del administrador que está realizando la acción.
        # Si el admin de la sucursal 2 paga, el gasto DEBE quedar en la sucursal 2.
        try:
            if current_user.id_empresa:
                id_empresa_pago = int(current_user.id_empresa)
            elif rep_data and rep_data['id_empresa']:
                id_empresa_pago = int(rep_data['id_empresa'])
            else:
                id_empresa_pago = int(DEFAULT_COMPANY_FOR_ORDERS)
        except:
            id_empresa_pago = int(DEFAULT_COMPANY_FOR_ORDERS)
        
        # 2. OBTENEMOS LA TARIFA DE PAGO
        pago_por_viaje = get_pago_repartidor(id_empresa_pago)
        total_monto = float(len(ids_pedidos) * pago_por_viaje)
        #fecha_hoy = datetime.now().strftime('%Y-%m-%d %H:%M:= ?')
        fecha_hoy = get_now_iso() # <--- USA LA FUNCIÓN QUE YA TIENE EL FORMATO
        
        # 3. Marcar los pedidos como PAGADOS
        placeholders = ','.join(['?' for _ in ids_pedidos])
        query_update = f"UPDATE pedidos SET pago_repartidor_status = 'Pagado' WHERE id_pedido IN ({placeholders})"
        cursor.execute(query_update, ids_pedidos)

        # 4. Registrar el EGRESO en la caja
        descripcion_pago = f"Liquidación de {len(ids_pedidos)} viajes a {nombre_rep}"
        
        cursor.execute("""
            INSERT INTO ingresos_egresos (tipo, monto, descripcion, fecha_hora, id_repartidor_origen, id_empresa) 
            VALUES ('Egreso', ?, ?, ?, ?, ?)
        """, (total_monto, descripcion_pago, fecha_hoy, id_r, id_empresa_pago))
        
        conn.commit()
        
        # DEBUG PARA TERMINAL: Muy útil para ver si el ID de empresa es el correcto
        print(f"DEBUG PAGO: Usuario {current_user.email} | Empresa de Caja: {id_empresa_pago} | Monto: ${total_monto}")
        
        flash(f"Pago de ${total_monto} registrado para {nombre_rep}. Se descontó de la caja de la sucursal.", "success")
        
    except Exception as e:
        conn.rollback()
        print(f"ERROR EN PROCESAR PAGO: {e}")
        flash(f"Error crítico al procesar el pago: {e}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('reporte_repartidores'))



@app.route('/gestion/pagar_repartidor', methods=['POST'])
@login_required
def pagar_repartidor():
    id_r = request.form.get('id_repartidor')
    monto = float(request.form.get('monto'))
    fi = request.form.get('fecha_inicio')
    ff = request.form.get('fecha_fin')
    nombre_rep = request.form.get('nombre_repartidor')
    
    conn = conectar_db(); cursor = conn.cursor()
    #fecha_hoy = datetime.now().strftime('%Y-%m-%d %H:%M:= ?')
    fecha_hoy = get_now_iso()
    
    # 1. Registramos el EGRESO en la caja
    cursor.execute("""
        INSERT INTO ingresos_egresos (tipo, monto, descripcion, fecha_hora, id_repartidor_origen, id_empresa) 
        VALUES ('Egreso', ?, ?, ?, ?, ?)
    """, (monto, f"Pago de viajes a {nombre_rep} (Periodo: {fi} a {ff})", fecha_hoy, id_r, current_user.id_empresa))
    
    conn.commit(); conn.close()
    
    flash(f"Se ha registrado el pago de ${monto} a {nombre_rep}. El monto se descontó de la caja.", "success")
    return redirect(url_for('reporte_repartidores'))


    
@app.route('/gestion/reportes/ventas', methods=['GET', 'POST'])
@login_required
def reportes_ventas():
    ahora = get_now_arg() # <--- CAMBIO AQUÍ
    start = request.form.get('fecha_inicio', (ahora - timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.form.get('fecha_fin', ahora.strftime('%Y-%m-%d'))
    sid = request.form.get('id_empresa_reporte'); reportes = None
    if request.method == 'POST':
        reportes = _fetch_report_data(start, end, sid)
    conn = conectar_db(); cursor = conn.cursor(); cursor.execute("SELECT id_empresa, nombre FROM empresas"); emps = cursor.fetchall(); conn.close()
    return render_template('reportes_ventas.html', start_date=start, end_date=end, reportes=reportes, empresas_disponibles=emps, selected_company_id=sid)

@app.route('/gestion/caja', methods=['GET', 'POST'])
@login_required
def arqueo_caja():
    conn = conectar_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        # CASO A: Registrar un egreso manual
        if 'registrar_egreso' in request.form:
            monto = float(request.form.get('monto', 0))
            desc = request.form.get('descripcion')
            #fecha = datetime.now().strftime('%Y-%m-%d %H:%M:= ?')
            fecha = get_now_iso() #
            
            cursor.execute("""
                INSERT INTO ingresos_egresos (tipo, monto, descripcion, fecha_hora, id_empresa) 
                VALUES ('Egreso', ?, ?, ?, ?)
            """, (monto, desc, fecha, current_user.id_empresa))
            conn.commit()
            flash("Egreso registrado correctamente.", "success")
            return redirect(url_for('arqueo_caja'))
        
          # --- NUEVO CASO C: Registrar un INGRESO manual (Apertura de caja) ---
        elif 'registrar_ingreso' in request.form:
            monto = float(request.form.get('monto', 0))
            desc = request.form.get('descripcion') # Ej: "Apertura de caja" o "Refuerzo"
            #fecha = datetime.now().strftime('%Y-%m-%d %H:%M:= ?')
            fecha = get_now_iso() 
            cursor.execute("""
                INSERT INTO ingresos_egresos (tipo, monto, descripcion, fecha_hora, id_empresa) 
                VALUES ('Ingreso', ?, ?, ?, ?)
            """, (monto, desc, fecha, current_user.id_empresa))
            conn.commit()
            flash("Ingreso manual registrado correctamente.", "success")
            return redirect(url_for('arqueo_caja'))
        # -------------------------------------------------------------------

        # CASO B: Realizar el arqueo (búsqueda)
     
        elif 'realizar_arqueo' in request.form:
            fi = request.form.get('fecha_inicio') + " 00:00:00"
            ff = request.form.get('fecha_fin') + " 23:59:59"
            
            # --- CONSULTA ACTUALIZADA CON JOIN PARA TRAER DATOS DEL CLIENTE ---
            query = """
                        SELECT ie.*, p.cliente_nombre, p.cliente_apellido, p.forma_pago, r.nombre as rep_nombre
                        FROM ingresos_egresos ie
                        LEFT JOIN pedidos p ON ie.id_pedido_origen = p.id_pedido
                        LEFT JOIN repartidores r ON ie.id_repartidor_origen = r.id_repartidor -- <--- ESTO ES CLAVE
                        WHERE ie.fecha_hora BETWEEN ? AND ?
                    """
            params = [fi, ff]
            
            if not current_user.has_role('super_admin'):
                # Usamos ie.id_empresa para evitar ambigüedad con la tabla pedidos
                query += " AND ie.id_empresa = ?"
                params.append(current_user.id_empresa)
                
            cursor.execute(query, params)
            movs = [dict(m) for m in cursor.fetchall()]
            
            ingresos = sum(m['monto'] for m in movs if m['tipo'] == 'Ingreso')
            egresos = sum(m['monto'] for m in movs if m['tipo'] != 'Ingreso')
            
            # GUARDAMOS TODO, INCLUYENDO EL BALANCE Y LOS NUEVOS CAMPOS
            session['arqueo_resultados'] = {
                'movimientos': movs, 
                'total_ingresos': ingresos, 
                'total_egresos': egresos,
                'balance': ingresos - egresos
            }
            return redirect(url_for('arqueo_caja'))

    conn.close()
    res = session.pop('arqueo_resultados', None)
    return render_template('arqueo_caja.html', arqueo_resultados=res, now=get_now_arg())



@app.route('/gestion/configuracion', methods=['GET', 'POST']) 
@login_required
def gestion_configuracion():
    # Determinamos de qué empresa estamos viendo/editando la configuración
    eid = current_user.id_empresa if not current_user.has_role('super_admin') else request.form.get('config_for_company')
    if not eid: eid = DEFAULT_COMPANY_FOR_ORDERS

    if request.method == 'POST':
        # Guardar costo de envío
        if 'costo_envio' in request.form: 
            guardar_configuracion('ENVIO_COSTO', request.form['costo_envio'], eid)
        
        # GUARDAR PAGO REPARTIDOR
        if 'pago_repartidor' in request.form:
            guardar_configuracion('PAGO_REPARTIDOR', request.form['pago_repartidor'], eid)
            
        # --- Guardar el Alias ---
        if 'transferencia_alias' in request.form:
            guardar_configuracion('TRANSFERENCIA_ALIAS', request.form['transferencia_alias'], eid)
        # ------------------------------------------------
            
        # Si el cambio fue solo por el selector de empresa del Super Admin (sin datos de ahorro), 
        # evitamos el redirect para que la página cargue los nuevos valores de esa empresa.
        if not any(k in request.form for k in ['costo_envio', 'pago_repartidor', 'transferencia_alias']):
            pass
        else:
            flash("Configuración actualizada correctamente.", "success")
            return redirect(url_for('gestion_configuracion'))

    # Para el selector de empresas (solo Super Admin)
    empresas = []
    if current_user.has_role('super_admin'):
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1")
        empresas = cursor.fetchall(); conn.close()

    return render_template('gestion_configuracion.html', 
                           costo_envio_actual=get_costo_envio(eid), 
                           pago_repartidor_actual=get_pago_repartidor(eid),
                           id_empresa_actual=eid, # <--- LÍNEA CLAVE PARA QUE EL HTML FUNCIONE
                           empresas_para_config=empresas)
    
    
       
#@app.route('/gestion/usuarios')
#@login_required
#def gestion_usuarios():
#    conn = conectar_db(); cursor = conn.cursor(); cursor.execute("SELECT u.*, r.nombre_rol, e.nombre as empresa_n FROM usuarios u JOIN roles r ON u.id_rol = r.id_rol LEFT JOIN empresas e ON u.id_empresa = e.id_empresa"); usrs = cursor.fetchall(); conn.close()
#    return render_template('gestion_usuarios.html', usuarios=usrs)

@app.route('/gestion/usuarios')
@login_required
def gestion_usuarios():
    # Validar acceso
    if not current_user.has_role('super_admin', 'admin_empresa'):
        abort(403)

    conn = conectar_db()
    cursor = conn.cursor()
    
    if current_user.has_role('super_admin'):
        # El super admin ve a TODOS
        cursor.execute("""
            SELECT u.*, r.nombre_rol, e.nombre as empresa_n 
            FROM usuarios u 
            JOIN roles r ON u.id_rol = r.id_rol 
            LEFT JOIN empresas e ON u.id_empresa = e.id_empresa
        """)
    else:
         # Convertimos a int por seguridad
        cid = int(current_user.id_empresa)
        # El admin de empresa ve solo los de su empresa y oculta al super_admin
        cursor.execute("""
            SELECT u.*, r.nombre_rol, e.nombre as empresa_n 
            FROM usuarios u 
            JOIN roles r ON u.id_rol = r.id_rol 
            LEFT JOIN empresas e ON u.id_empresa = e.id_empresa
            WHERE u.id_empresa = ? AND r.nombre_rol != 'super_admin'
        """, (cid,))
        
    usrs = cursor.fetchall()
    conn.close()
    return render_template('gestion_usuarios.html', usuarios=usrs)






@app.route('/gestion/usuarios/agregar', methods=['GET', 'POST'])
@login_required
def agregar_usuario():
    # Seguridad: Ahora permitimos a super_admin Y admin_empresa
    if not current_user.has_role('super_admin', 'admin_empresa'):
        flash("No tienes permiso para realizar esta acción.", "danger")
        return redirect(url_for('index'))

    # Abrimos la conexión al inicio
    conn = conectar_db()
    cursor = conn.cursor()
    request_form = {}

    if request.method == 'POST':
        request_form = request.form
        email = request.form.get('email')
        password = request.form.get('password_inicial')
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        id_rol = request.form.get('id_rol')
        
        # --- LÓGICA DE EMPRESA RESTRINGIDA ---
        if current_user.has_role('super_admin'):
            id_empresa = request.form.get('id_empresa')
            if not id_empresa or id_empresa == "": id_empresa = None
        else:
            # Si es Admin de Empresa, forzamos el ID de su propia empresa
            id_empresa = current_user.id_empresa
        
        telefono = request.form.get('telefono') 
        id_rep_vinculado = request.form.get('id_repartidor_vinculado')
        
        if not id_rep_vinculado or id_rep_vinculado == "": id_rep_vinculado = None

        try:
            hp = generate_password_hash(password, method='pbkdf2:sha256')
            cursor.execute("""
                INSERT INTO usuarios (email, password, nombre, apellido, id_rol, id_empresa, activo, primer_login_requerido, id_repartidor_vinculado, telefono) 
                VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
            """, (email, hp, nombre, apellido, id_rol, id_empresa, id_rep_vinculado, telefono))
            
            conn.commit()
            conn.close() 
            flash("Usuario creado con éxito.", "success")
            return redirect(url_for('gestion_usuarios'))
            
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Error: El email ya está registrado.", "danger")
        except Exception as e:
            conn.rollback()
            flash(f"Error al guardar: {e}", "danger")

    # --- LÓGICA PARA CARGAR EL FORMULARIO (GET o re-intento) ---
    try:
        # Filtrar Roles
        if current_user.has_role('super_admin'):
            cursor.execute("SELECT * FROM roles")
        else:
            # Un admin de empresa no puede crear un Super Admin
            cursor.execute("SELECT * FROM roles WHERE nombre_rol != 'super_admin'")
        roles_db = cursor.fetchall()
        
        # Filtrar Empresas
        empresas_db = []
        if current_user.has_role('super_admin'):
            cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1")
            empresas_db = cursor.fetchall()
        
        # Filtrar Repartidores
        if current_user.has_role('super_admin'):
            cursor.execute("SELECT id_repartidor, nombre, apellido FROM repartidores WHERE activo = 1")
        else:
            cursor.execute("SELECT id_repartidor, nombre, apellido FROM repartidores WHERE activo = 1 AND id_empresa = ?", (current_user.id_empresa,))
        repartidores_db = cursor.fetchall()
        
    except sqlite3.ProgrammingError:
        # Re-apertura de conexión por seguridad
        conn = conectar_db(); cursor = conn.cursor()
        if current_user.has_role('super_admin'):
            cursor.execute("SELECT * FROM roles")
            roles_db = cursor.fetchall()
            cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1")
            empresas_db = cursor.fetchall()
            cursor.execute("SELECT id_repartidor, nombre, apellido FROM repartidores WHERE activo = 1")
            repartidores_db = cursor.fetchall()
        else:
            cursor.execute("SELECT * FROM roles WHERE nombre_rol != 'super_admin'")
            roles_db = cursor.fetchall()
            empresas_db = []
            cursor.execute("SELECT id_repartidor, nombre, apellido FROM repartidores WHERE activo = 1 AND id_empresa = ?", (current_user.id_empresa,))
            repartidores_db = cursor.fetchall()

    # --- NUEVO: Obtener nombre de la empresa para mostrar al Admin de Sucursal ---
    nombre_emp_aux = ""
    if not current_user.has_role('super_admin'):
        cursor.execute("SELECT nombre FROM empresas WHERE id_empresa = ?", (current_user.id_empresa,))
        res_e = cursor.fetchone()
        nombre_emp_aux = res_e['nombre'] if res_e else "Empresa Asignada"
    
    current_user.empresa_nombre_aux = nombre_emp_aux # Inyectamos el nombre para el HTML

    conn.close() 

    return render_template('agregar_usuario.html', 
                           roles=roles_db, 
                           empresas=empresas_db, 
                           repartidores=repartidores_db, 
                           request_form=request_form)
    
    
    
    
@app.route('/gestion/empresas')
@login_required
def gestion_empresas():
    conn = conectar_db(); cursor = conn.cursor(); cursor.execute("SELECT * FROM empresas"); emps = cursor.fetchall(); conn.close()
    return render_template('gestion_empresas.html', empresas=emps)

 #--- RUTA EDITAR EMPRESA (Actualizada para recibir múltiples turnos) ---
@app.route('/gestion/empresas/editar/<int:id_empresa>', methods=['GET', 'POST'])
@login_required
def edita_empresa(id_empresa):
    if not current_user.has_role('super_admin'): abort(403)
    conn = conectar_db(); cursor = conn.cursor()
    request_form = {} # <-- Se inicializa vacío aquí
    
    if request.method == 'POST':
        request_form = request.form
        # ... (tus capturas de nombre, calle, altura, etc. se mantienen igual) ...
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        # Captura de dirección... (omito el código repetitivo por brevedad, mantenlo igual)
        activo = 1 if 'activo' in request.form else 0

        # NUEVA LÓGICA: Procesar múltiples turnos por día
        nuevos_horarios = {}
        for i in range(7):
            esta_abierto_dia = request.form.get(f'abierto_{i}') == 'on'
            # Capturamos las listas de inicios y fines para ese día
            inicios = request.form.getlist(f'inicio_{i}[]')
            fines = request.form.getlist(f'fin_{i}[]')
            
            turnos_dia = []
            for h_in, h_fi in zip(inicios, fines):
                if h_in and h_fi:
                    turnos_dia.append({'inicio': h_in, 'fin': h_fi})
            
            nuevos_horarios[str(i)] = {
                'abierto': esta_abierto_dia,
                'turnos': turnos_dia
            }
        
        horarios_json = json.dumps(nuevos_horarios)

        cursor.execute("UPDATE empresas SET nombre=?, telefono=?, activo=?, horarios_json=? WHERE id_empresa=?", 
                       (nombre, telefono, activo, horarios_json, id_empresa))
        conn.commit(); conn.close()
        flash("Empresa y horarios actualizados.", "success")
        return redirect(url_for('gestion_empresas'))

    cursor.execute("SELECT * FROM empresas WHERE id_empresa = ?", (id_empresa,))
    empresa = cursor.fetchone()
    
    # Normalizar formato para la vista (por si hay datos viejos)
    try:
        h_data = json.loads(empresa['horarios_json']) if empresa['horarios_json'] else {}
    except: h_data = {}
    
    # Aseguramos que cada día tenga al menos la estructura de 'turnos'
    for i in range(7):
        if str(i) not in h_data: h_data[str(i)] = {'abierto': False, 'turnos': []}
        if 'turnos' not in h_data[str(i)]:
            # Migración al vuelo: si tenía el formato anterior, lo metemos en la lista de turnos
            if 'inicio' in h_data[str(i)]:
                h_data[str(i)]['turnos'] = [{'inicio': h_data[str(i)]['inicio'], 'fin': h_data[str(i)]['fin']}]
    
    conn.close()
    return render_template('editar_empresa.html', 
                           empresa=empresa, 
                           horarios=h_data, 
                           dias=DIAS_SEMANA,
                           request_form=request_form) # <--- AGREGA ESTA LÍNEA AQUÍ
    

@app.route('/gestion/empresas/eliminar/<int:id_empresa>', methods=['POST'])
@login_required
def eliminar_empresa(id_empresa):
    # Seguridad: Solo el super_admin puede inactivar empresas
    if not current_user.has_role('super_admin'):
        flash("No tienes permiso para realizar esta acción.", "danger")
        return redirect(url_for('index'))

    try:
        conn = conectar_db()
        cursor = conn.cursor()
        
        # Realizamos un "borrado lógico" (ponemos activo = 0)
        # Esto es mejor que borrar el registro para no perder el historial de pedidos
        cursor.execute("UPDATE empresas SET activo = 0 WHERE id_empresa = ?", (id_empresa,))
        
        # También inactivamos a los usuarios que pertenecen a esa empresa
        cursor.execute("UPDATE usuarios SET activo = 0 WHERE id_empresa = ?", (id_empresa,))
        
        conn.commit()
        conn.close()
        
        flash("Empresa y usuarios asociados han sido inactivados correctamente.", "success")
    except Exception as e:
        flash(f"Error al intentar inactivar la empresa: {e}", "danger")

    return redirect(url_for('gestion_empresas'))


@app.route('/gestion/empresas/agregar', methods=['GET', 'POST'])
@login_required
def agregar_empresa():
    if not current_user.has_role('super_admin'):
        abort(403)

    request_form = {}
    if request.method == 'POST':
        request_form = request.form
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        calle = request.form.get('calle')
        altura = request.form.get('altura')
        localidad = request.form.get('localidad')
        provincia = request.form.get('provincia')

        # Concatenamos para el campo 'direccion' general
        direccion_completa = f"{calle} {altura}, {localidad}, {provincia}"

        try:
            conn = conectar_db(); cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO empresas (nombre, telefono, direccion, calle, altura, localidad, provincia, activo) 
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (nombre, telefono, direccion_completa, calle, altura, localidad, provincia))
            conn.commit(); conn.close()
            flash("Empresa agregada con éxito.", "success")
            return redirect(url_for('gestion_empresas'))
        except Exception as e:
            flash(f"Error: {e}", "danger")

    return render_template('agregar_empresa.html', request_form=request_form)


@app.route('/gestion/usuarios/editar/<int:id_usuario>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id_usuario):
    # Seguridad: Solo super_admin o admin_empresa
    if not current_user.has_role('super_admin', 'admin_empresa'):
        flash("No tienes permiso para editar usuarios.", "danger")
        return redirect(url_for('index'))

    # Abrimos la conexión al inicio
    conn = conectar_db()
    cursor = conn.cursor()

    # --- VALIDACIÓN DE SEGURIDAD PREVIA ---
    # Necesitamos saber quién es el usuario a editar antes de procesar nada
    cursor.execute("""
        SELECT u.*, r.nombre_rol 
        FROM usuarios u 
        LEFT JOIN roles r ON u.id_rol = r.id_rol 
        WHERE u.id_usuario = ?
    """, (id_usuario,))
    usuario_db = cursor.fetchone()

    if not usuario_db:
        conn.close()
        flash("Usuario no encontrado.", "warning")
        return redirect(url_for('gestion_usuarios'))

    # Si es Admin de Empresa, verificamos que el editado sea de su sucursal y no sea un super_admin
    if current_user.has_role('admin_empresa'):
        if usuario_db['id_empresa'] != current_user.id_empresa:
            conn.close()
            flash("No tienes permiso para editar usuarios de otra sucursal.", "danger")
            return redirect(url_for('gestion_usuarios'))
        
        if usuario_db['nombre_rol'] == 'super_admin':
            conn.close()
            flash("No puedes editar a un Super Administrador.", "danger")
            return redirect(url_for('gestion_usuarios'))

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        email = request.form.get('email')
        id_rol = request.form.get('id_rol')
        telefono = request.form.get('telefono')
        id_rep_vinculado = request.form.get('id_repartidor_vinculado')
        
        # Lógica de Empresa (Protección)
        if current_user.has_role('super_admin'):
            id_empresa = request.form.get('id_empresa')
            if not id_empresa or id_empresa == "": id_empresa = None
        else:
            # El Admin de Empresa no puede cambiar a nadie de sucursal
            id_empresa = usuario_db['id_empresa']

        # Limpiar el valor si no se seleccionó ninguno
        if not id_rep_vinculado or id_rep_vinculado == "":
            id_rep_vinculado = None
            
        activo = 1 if 'activo' in request.form else 0
        nueva_password = request.form.get('password')

        try:
            cursor.execute("""
                UPDATE usuarios 
                SET nombre=?, apellido=?, email=?, id_rol=?, id_empresa=?, activo=?, id_repartidor_vinculado=?, telefono=?
                WHERE id_usuario=?
            """, (nombre, apellido, email, id_rol, id_empresa, activo, id_rep_vinculado, telefono, id_usuario))

            if nueva_password and nueva_password.strip() != "":
                hp = generate_password_hash(nueva_password, method='pbkdf2:sha256')
                cursor.execute("UPDATE usuarios SET password=? WHERE id_usuario=?", (hp, id_usuario))

            conn.commit()
            conn.close() # Cerramos solo si el proceso fue exitoso antes del redirect
            flash("Usuario actualizado con éxito.", "success")
            return redirect(url_for('gestion_usuarios'))
            
        except Exception as e:
            conn.rollback() # Si hay error, volvemos atrás
            flash(f"Error al actualizar: {e}", "danger")

    # --- LÓGICA PARA CARGAR EL FORMULARIO (GET o si el POST falló) ---
    try:
        # 1. Recargar datos del usuario por si hubo cambios o errores
        cursor.execute("SELECT * FROM usuarios WHERE id_usuario = ?", (id_usuario,))
        usuario = cursor.fetchone()
        
        # 2. Filtrar Roles
        if current_user.has_role('super_admin'):
            cursor.execute("SELECT * FROM roles")
        else:
            cursor.execute("SELECT * FROM roles WHERE nombre_rol != 'super_admin'")
        roles = cursor.fetchall()
        
        # 3. Filtrar Empresas (Solo para Super Admin)
        cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1")
        empresas = cursor.fetchall()

        # 4. Filtrar Repartidores
        if current_user.has_role('super_admin'):
            cursor.execute("SELECT id_repartidor, nombre, apellido FROM repartidores WHERE activo = 1")
        else:
            cursor.execute("SELECT id_repartidor, nombre, apellido FROM repartidores WHERE activo = 1 AND id_empresa = ?", (current_user.id_empresa,))
        repartidores_lista = cursor.fetchall()

    except sqlite3.ProgrammingError:
        # Reconexión de seguridad
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE id_usuario = ?", (id_usuario,))
        usuario = cursor.fetchone()
        if current_user.has_role('super_admin'):
            cursor.execute("SELECT * FROM roles"); roles = cursor.fetchall()
            cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1"); empresas = cursor.fetchall()
            cursor.execute("SELECT id_repartidor, nombre, apellido FROM repartidores WHERE activo = 1"); repartidores_lista = cursor.fetchall()
        else:
            cursor.execute("SELECT * FROM roles WHERE nombre_rol != 'super_admin'"); roles = cursor.fetchall()
            cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1"); empresas = cursor.fetchall()
            cursor.execute("SELECT id_repartidor, nombre, apellido FROM repartidores WHERE activo = 1 AND id_empresa = ?", (current_user.id_empresa,))
            repartidores_lista = cursor.fetchall()

    # Auxiliar para mostrar el nombre de la empresa
    nombre_emp_aux = ""
    if not current_user.has_role('super_admin'):
        cursor.execute("SELECT nombre FROM empresas WHERE id_empresa = ?", (current_user.id_empresa,))
        res_e = cursor.fetchone()
        nombre_emp_aux = res_e['nombre'] if res_e else "Sucursal"
    
    current_user.empresa_nombre_aux = nombre_emp_aux

    conn.close() 
    
    return render_template('editar_usuario.html', 
                           usuario=usuario, 
                           roles=roles, 
                           empresas=empresas, 
                           repartidores=repartidores_lista)
    
    
    
    
#@app.route('/gestion/usuarios/eliminar/<int:id_usuario>', methods=['POST'])
#@login_required
#def eliminar_usuario(id_usuario):
#    if not current_user.has_role('super_admin', 'admin_empresa'):
#        flash("No autorizado.", "danger")
#        return redirect(url_for('index'))
#
#    conn = conectar_db(); cursor = conn.cursor()
#    # Inactivación en lugar de borrado físico
#    cursor.execute("UPDATE usuarios SET activo = 0 WHERE id_usuario = ?", (id_usuario,))
#    conn.commit(); conn.close()
#    flash("Usuario inactivado.", "info")
#    return redirect(url_for('gestion_usuarios'))    

@app.route('/gestion/usuarios/eliminar/<int:id_usuario>', methods=['POST'])
@login_required
def eliminar_usuario(id_usuario):
    # SEGURIDAD: Permitir a Super Admin y Admin de Empresa
    if not current_user.has_role('super_admin', 'admin_empresa'):
        flash("No tienes permisos para realizar esta acción.", "danger")
        return redirect(url_for('index'))

    conn = conectar_db()
    cursor = conn.cursor()

    # 1. Buscamos al usuario que se quiere inactivar para verificar su empresa y rol
    cursor.execute("""
        SELECT u.id_empresa, r.nombre_rol 
        FROM usuarios u 
        JOIN roles r ON u.id_rol = r.id_rol 
        WHERE u.id_usuario = ?
    """, (id_usuario,))
    target_user = cursor.fetchone()

    if not target_user:
        conn.close()
        flash("Usuario no encontrado.", "warning")
        return redirect(url_for('gestion_usuarios'))

    # 2. VALIDACIONES PARA EL ADMIN DE EMPRESA
    if current_user.has_role('admin_empresa'):
        # No puede inactivar usuarios de otras empresas
        if target_user['id_empresa'] != current_user.id_empresa:
            conn.close()
            flash("No puedes inactivar usuarios que no pertenecen a tu sucursal.", "danger")
            return redirect(url_for('gestion_usuarios'))
        
        # No puede inactivar a un Super Admin (por seguridad extra)
        if target_user['nombre_rol'] == 'super_admin':
            conn.close()
            flash("No tienes permisos para inactivar a un Super Administrador.", "danger")
            return redirect(url_for('gestion_usuarios'))

    # 3. Proceder con la inactivación (Borrado Lógico)
    try:
        cursor.execute("UPDATE usuarios SET activo = 0 WHERE id_usuario = ?", (id_usuario,))
        conn.commit()
        flash("Usuario inactivado correctamente.", "info")
    except Exception as e:
        conn.rollback()
        flash(f"Error al inactivar usuario: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('gestion_usuarios'))




@app.route('/gestion/catalogo/agregar', methods=['GET', 'POST'])
@login_required
def agregar_plato():
    # 1. Inicializamos request_form vacío para que el HTML no de error en el GET
    request_form = {}
    
    if request.method == 'POST':
        # 2. Si es POST, capturamos los datos del formulario
        request_form = request.form
        
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        rubro = request.form.get('rubro')
        
        # Determinar la empresa
        if current_user.has_role('super_admin'):
            id_empresa = request.form.get('id_empresa')
        else:
            id_empresa = current_user.id_empresa

        if not nombre or not precio:
            flash("Nombre y Precio son obligatorios.", "danger")
        else:
            # --- NUEVO: LÓGICA DE PROCESAMIENTO DE IMAGEN ---
            nombre_imagen = None
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Añadimos un timestamp para que el nombre sea único y no se sobrescriba
                    #timestamp = datetime.now().strftime('%Y%m%d%H%M= ?')
                    timestamp = get_now_arg().strftime('%Y%m%d%H%M= ?')
                    filename = f"{timestamp}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    nombre_imagen = filename
            # ------------------------------------------------

            try:
                conn = conectar_db()
                cursor = conn.cursor()
                # Se agregó 'imagen' y un '?' extra a la consulta
                cursor.execute("""
                    INSERT INTO platos (nombre, descripcion, precio, activo, id_empresa, rubro, imagen) 
                    VALUES (?, ?, ?, 1, ?, ?, ?)
                """, (nombre, descripcion, precio, id_empresa, rubro, nombre_imagen))
                conn.commit()
                conn.close()
                flash("Plato agregado con éxito.", "success")
                return redirect(url_for('gestion_catalogo'))
            except Exception as e:
                flash(f"Error al guardar el plato: {e}", "danger")

    # 3. Lógica para mostrar el formulario (GET o POST fallido)
    empresas = []
    if current_user.has_role('super_admin'):
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT id_empresa, nombre FROM empresas WHERE activo = 1")
        empresas = cursor.fetchall(); conn.close()
    
    return render_template('agregar_plato.html', 
                           empresas_disponibles=empresas, 
                           request_form=request_form)  
    
@app.route('/gestion/catalogo/editar/<int:id_plato>', methods=['GET', 'POST'])
@login_required
def editar_plato(id_plato):
    conn = conectar_db()
    cursor = conn.cursor()
    
    # 1. Buscamos el plato actual en la base de datos
    cursor.execute("SELECT * FROM platos WHERE id_plato = ?", (id_plato,))
    plato = cursor.fetchone()
    
    if not plato:
        conn.close()
        flash("Plato no encontrado.", "danger")
        return redirect(url_for('gestion_catalogo'))

    # Inicializamos request_form vacío para evitar errores en el GET
    request_form = {}

    if request.method == 'POST':
        request_form = request.form
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        rubro = request.form.get('rubro')
        activo = 1 if 'activo' in request.form else 0
        
        # Mantenemos el nombre de la imagen actual por defecto
        nombre_imagen_final = plato['imagen']

        # 2. Lógica de actualización de imagen
        if 'imagen' in request.files:
            file = request.files['imagen']
            
            # Si el usuario seleccionó un archivo nuevo
            if file and file.filename != '' and allowed_file(file.filename):
                # A. Borrar la imagen anterior del servidor si existía
                if plato['imagen']:
                    ruta_vieja = os.path.join(app.config['UPLOAD_FOLDER'], plato['imagen'])
                    if os.path.exists(ruta_vieja):
                        try:
                            os.remove(ruta_vieja)
                        except Exception as e:
                            print(f"No se pudo borrar la imagen vieja: {e}")

                # B. Guardar la nueva imagen
                filename = secure_filename(file.filename)
                #timestamp = datetime.now().strftime('%Y%m%d%H%M= ?')
                timestamp = get_now_arg().strftime('%Y%m%d%H%M= ?')
                filename = f"{timestamp}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                # C. Actualizamos el nombre que irá a la base de datos
                nombre_imagen_final = filename

        # 3. Guardar los cambios en la base de datos
        try:
            cursor.execute("""
                UPDATE platos 
                SET nombre=?, descripcion=?, precio=?, rubro=?, activo=?, imagen=? 
                WHERE id_plato=?
            """, (nombre, descripcion, precio, rubro, activo, nombre_imagen_final, id_plato))
            conn.commit()
            conn.close()
            flash("Plato actualizado con éxito.", "success")
            return redirect(url_for('gestion_catalogo'))
        except Exception as e:
            flash(f"Error al actualizar el plato: {e}", "danger")

    conn.close()
    # Enviamos plato (datos DB) y request_form (datos intento fallido) al template
    return render_template('editar_plato.html', plato=plato, request_form=request_form)



@app.route('/gestion/catalogo/eliminar/<int:id_plato>', methods=['POST'])
@login_required
def eliminar_plato(id_plato):
    conn = conectar_db(); cursor = conn.cursor()
    # En lugar de borrarlo físicamente, lo desactivamos para no romper pedidos viejos
    cursor.execute("UPDATE platos SET activo = 0 WHERE id_plato = ?", (id_plato,))
    conn.commit(); conn.close()
    flash("Plato desactivado del catálogo.", "info")
    return redirect(url_for('gestion_catalogo'))

# --- API Carrito ---
@app.route('/api/update_cart_complex', methods=['POST'])
def update_cart_complex():
    data = request.json
    plato_id = data.get('plato_id') # Puede ser None si es promo
    id_promocion = data.get('id_promocion') # Nuevo campo
    cantidad = int(data.get('cantidad', 1))
    opciones_elegidas = data.get('opciones', [])
    notas = data.get('notas', "").strip()

    if 'carrito' not in session: session['carrito'] = {}

    # --- 1. GENERACIÓN DE LA CLAVE ÚNICA DEL CARRITO ---
    if id_promocion:
        # Clave única para la promo + la elección que hizo el cliente (guardada en notas)
        cart_key = f"promo_{id_promocion}_{notas}" 
    else:
        # Clave normal para platos con sus modificadores
        opciones_key = "_".join(map(str, sorted(opciones_elegidas)))
        cart_key = f"{plato_id}_{opciones_key}_{notas}"

    # --- 2. LÓGICA DE ELIMINACIÓN ---
    if cantidad <= 0:
        if cart_key in session['carrito']: del session['carrito'][cart_key]
    else:
        conn = conectar_db(); cursor = conn.cursor()
        
        if id_promocion:
            # --- 3. LÓGICA DE PROMO: Buscamos precio y nombre de la PROMO ---
            cursor.execute("SELECT nombre, precio_total FROM promociones WHERE id_promocion = ?", (id_promocion,))
            p = cursor.fetchone()
            
            if p:
                nombre_item = f"PROMO: {p['nombre']}"
                precio_final = p['precio_total']
                # En la promo, 'detalles_texto' muestra el plato que el cliente eligió
                detalles_texto = notas 
            else:
                conn.close()
                return jsonify({"success": False, "message": "Promoción no encontrada"}), 404
        else:
            # --- 4. LÓGICA NORMAL (ACTUALIZADA CON PUNTO 5: PRECIO OFERTA) ---
            # Agregamos precio_oferta a la consulta SQL
            cursor.execute("SELECT nombre, precio, precio_oferta FROM platos WHERE id_plato = ?", (plato_id,))
            p = cursor.fetchone()
            
            if p:
                nombre_item = p['nombre']
                
                # DETERMINAR EL PRECIO BASE REAL (Si hay oferta válida, la usamos)
                if p['precio_oferta'] is not None and p['precio_oferta'] > 0:
                    precio_base_a_usar = p['precio_oferta']
                else:
                    precio_base_a_usar = p['precio']

                total_extra = 0
                detalles_opciones = []
                
                # Procesar modificadores/extras del plato (se suman al precio base de oferta o normal)
                if opciones_elegidas:
                    placeholders = ','.join(['?' for _ in opciones_elegidas])
                    cursor.execute(f"SELECT nombre, precio_extra FROM plato_opciones WHERE id_opcion IN ({placeholders})", opciones_elegidas)
                    for opt in cursor.fetchall():
                        total_extra += opt['precio_extra']
                        detalles_opciones.append(opt['nombre'])
                
                # El precio final es la base (que puede ser oferta) + los extras seleccionados
                precio_final = precio_base_a_usar + total_extra
                detalles_texto = ", ".join(detalles_opciones)
            else:
                conn.close()
                return jsonify({"success": False, "message": "Plato no encontrado"}), 404
        
        conn.close()

        # --- 5. GUARDADO EN SESIÓN ---
        session['carrito'][cart_key] = {
            'id_plato': plato_id,
            'id_promocion': id_promocion,
            'nombre': nombre_item,
            'precio_total_unitario': float(precio_final),
            'cantidad': cantidad,
            'opciones_texto': detalles_texto,
            'notas': notas if not id_promocion else "" # Limpiamos notas en promo para no duplicar el texto de elección
        }
    
    session.modified = True
    return jsonify({"success": True})




# --- LISTADO DE PROMOCIONES ---
@app.route('/gestion/promociones')
@login_required
def gestion_promociones():
    if not (current_user.has_role('super_admin') or current_user.has_role('admin_empresa')):
        abort(403)
    
    conn = conectar_db(); cursor = conn.cursor()
    # Filtro por empresa
    cond, params = get_company_filter_conditions_and_params()
    query = "SELECT * FROM promociones"
    if cond: query += " WHERE " + " AND ".join(cond)
    
    cursor.execute(query, params)
    promos = cursor.fetchall()
    conn.close()
    return render_template('gestion_promociones.html', promociones=promos)

# --- ELIMINAR O INACTIVAR PROMO ---
@app.route('/gestion/promociones/eliminar/<int:id_promo>', methods=['POST'])
@login_required
def eliminar_promocion(id_promo):
    conn = conectar_db(); cursor = conn.cursor()
    # Borrado físico (puedes cambiarlo a lógico con activo=0 si prefieres)
    try:
        cursor.execute("DELETE FROM promocion_platos WHERE id_promocion = ?", (id_promo,))
        cursor.execute("DELETE FROM promociones WHERE id_promocion = ?", (id_promo,))
        conn.commit()
        flash("Promoción eliminada correctamente.", "info")
    except Exception as e:
        conn.rollback()
        flash(f"Error al eliminar: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('gestion_promociones'))

# --- EDITAR PROMOCIÓN ---
@app.route('/gestion/promociones/editar/<int:id_promo>', methods=['GET', 'POST'])
@login_required
def editar_promocion(id_promo):
    conn = conectar_db(); cursor = conn.cursor()
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        desc = request.form.get('descripcion')
        precio = request.form.get('precio')
        platos_ids = request.form.getlist('platos_seleccionados')
        activo = 1 if 'activo' in request.form else 0

        # --- NUEVOS CAMPOS PUNTO 1 (Captura del Switch y Límites) ---
        # Detectamos si el switch está encendido ('on') para guardarlo como 1 o 0
        es_combo_fijo = 1 if request.form.get('es_combo_fijo') == 'on' else 0
        min_items = int(request.form.get('min_items', 1))
        max_items = int(request.form.get('max_items', 1))
        # ------------------------------------------------------------

        # Lógica de imagen: mantenemos la actual o subimos una nueva
        cursor.execute("SELECT imagen FROM promociones WHERE id_promocion = ?", (id_promo,))
        res_img = cursor.fetchone()
        nombre_imagen = res_img['imagen'] if res_img else None
        
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                nombre_imagen = f"promo_{get_now_arg().strftime('%Y%m%d%H%M= ?')}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_imagen))

        try:
            # 1. Actualizar datos de la promoción incluyendo los nuevos campos de modo combo
            cursor.execute("""
                UPDATE promociones 
                SET nombre=?, descripcion=?, precio_total=?, activo=?, imagen=?, 
                    es_combo_fijo=?, min_items=?, max_items=?
                WHERE id_promocion=?
            """, (nombre, desc, precio, activo, nombre_imagen, es_combo_fijo, min_items, max_items, id_promo))
            
            # 2. Actualizar platos vinculados (Sincronización de la relación)
            cursor.execute("DELETE FROM promocion_platos WHERE id_promocion = ?", (id_promo,))
            for p_id in platos_ids:
                cursor.execute("INSERT INTO promocion_platos (id_promocion, id_plato) VALUES (?, ?)", (id_promo, p_id))
            
            conn.commit()
            flash("Promoción actualizada con éxito.", "success")
            return redirect(url_for('gestion_promociones'))
        except Exception as e:
            conn.rollback()
            flash(f"Error al actualizar la promoción: {e}", "danger")
        finally:
            conn.close()

    # --- LÓGICA GET: Carga de datos para el formulario ---
    cursor.execute("SELECT * FROM promociones WHERE id_promocion = ?", (id_promo,))
    promo = cursor.fetchone()
    
    if not promo:
        conn.close()
        abort(404)
    
    # Traer todos los platos de la empresa para el selector (Solo platos activos)
    cursor.execute("SELECT id_plato, nombre, precio FROM platos WHERE id_empresa = ? AND activo = 1", (promo['id_empresa'],))
    platos_disponibles = cursor.fetchall()
    
    # Traer IDs de platos que YA están en la promo para que aparezcan marcados (checked)
    cursor.execute("SELECT id_plato FROM promocion_platos WHERE id_promocion = ?", (id_promo,))
    platos_actuales = [r['id_plato'] for r in cursor.fetchall()]
    
    conn.close()
    return render_template('editar_promocion.html', promo=promo, platos=platos_disponibles, platos_actuales=platos_actuales)



@app.route('/api/get_cart_status')
def get_cart_status():
    carrito = session.get('carrito', {})
    
    # Calculamos la cantidad total
    total_items = sum(i['cantidad'] for i in carrito.values())
    
    # Calculamos el precio total usando 'precio_total_unitario' que es la clave que existe
    total_precio = sum(i['precio_total_unitario'] * i['cantidad'] for i in carrito.values())
    
    return jsonify({
        "success": True, 
        "total_items": total_items, 
        "total_precio": total_precio
    })
    
    
@app.route('/api/clear_cart', methods=['POST'])
def clear_cart(): session.pop('carrito', None); return jsonify({"success": True})

@app.route('/gestion/catalogo')
@login_required
def gestion_catalogo():
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Si no es super_admin, solo mostramos los platos de su empresa
    if not current_user.has_role('super_admin'):
        cursor.execute("SELECT * FROM platos WHERE id_empresa = ?", (current_user.id_empresa,))
    else:
        # El super_admin ve todo
        cursor.execute("SELECT * FROM platos")
        
    p = cursor.fetchall()
    conn.close()
    return render_template('gestion_catalogo.html', platos=p)

# --- Funciones Internas ---
def _agregar_super_admin_inicial():
    conn = conectar_db(); cursor = conn.cursor(); cursor.execute("SELECT COUNT(*) FROM usuarios WHERE id_rol = 1")
    if cursor.fetchone()[0] == 0:
        hp = generate_password_hash("admin_password_inicial_segura", method='pbkdf2:sha256')
        cursor.execute("INSERT INTO usuarios (email, password, nombre, apellido, id_rol, id_empresa, activo, primer_login_requerido) VALUES (?,?,?,?,1,NULL,1,0)", ("admin@tudominio.com", hp, "Super", "Admin"))
        conn.commit(); conn.close()


# --- RUTAS PARA ADMINISTRACIÓN DE MODIFICADORES ---

@app.route('/api/plato/<int:id_plato>/modificadores')
#@login_required
def api_get_modificadores(id_plato):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM plato_modificadores WHERE id_plato = ?", (id_plato,))
    modificadores = [dict(m) for m in cursor.fetchall()]
    
    for mod in modificadores:
        cursor.execute("SELECT * FROM plato_opciones WHERE id_modificador = ?", (mod['id_modificador'],))
        mod['opciones'] = [dict(o) for o in cursor.fetchall()]
    
    conn.close()
    return jsonify(modificadores)

@app.route('/api/plato/modificador/guardar', methods=['POST'])
@login_required
def api_guardar_modificador():
    data = request.json
    id_plato = data.get('id_plato')
    nombre = data.get('nombre')
    tipo = data.get('tipo', 'radio') # 'radio' o 'checkbox'
    obligatorio = 1 if data.get('obligatorio') else 0

    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO plato_modificadores (id_plato, nombre, tipo, obligatorio) 
        VALUES (?, ?, ?, ?)
    """, (id_plato, nombre, tipo, obligatorio))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/plato/opcion/guardar', methods=['POST'])
@login_required
def api_guardar_opcion():
    data = request.json
    id_modificador = data.get('id_modificador')
    nombre = data.get('nombre')
    precio = float(data.get('precio', 0))

    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO plato_opciones (id_modificador, nombre, precio_extra) 
        VALUES (?, ?, ?)
    """, (id_modificador, nombre, precio))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/plato/modificador/eliminar/<int:id_mod>', methods=['POST'])
@login_required
def api_eliminar_modificador(id_mod):
    conn = conectar_db(); cursor = conn.cursor()
    # Al borrar un modificador, borramos también sus opciones (cascada manual)
    cursor.execute("DELETE FROM plato_opciones WHERE id_modificador = ?", (id_mod,))
    cursor.execute("DELETE FROM plato_modificadores WHERE id_modificador = ?", (id_mod,))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/plato/opcion/eliminar/<int:id_opcion>', methods=['POST'])
@login_required
def api_eliminar_opcion(id_opcion):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("DELETE FROM plato_opciones WHERE id_opcion = ?", (id_opcion,))
    conn.commit(); conn.close()
    return jsonify({"success": True})



# --- RUTAS PARA EL DASHBOARD DE COCINA ---


@app.route('/gestion/cocina')
@login_required
def dashboard_cocina():
    # El repartidor NO debe entrar a cocina
    if current_user.has_role('repartidor'):
        flash("No tienes acceso a la pantalla de cocina.", "danger")
        return redirect(url_for('panel_repartidor'))
    # Solo permitimos a empleados o admins de la empresa
    return render_template('gestion_cocina.html')

@app.route('/api/pedidos_pendientes_cocina')
@login_required
def api_pedidos_pendientes_cocina():
    conn = conectar_db()
    cursor = conn.cursor()
    
    # 1. Filtro de seguridad por empresa o Super Admin
    if current_user.has_role('super_admin'):
        query_base = "SELECT * FROM pedidos WHERE estado_envio IN ('Recibido', 'En Preparación', 'Pendiente de WhatsApp')"
        params = []
    else:
        query_base = "SELECT * FROM pedidos WHERE id_empresa = ? AND estado_envio IN ('Recibido', 'En Preparación', 'Pendiente de WhatsApp')"
        params = [current_user.id_empresa]

    cursor.execute(query_base + " ORDER BY horario_entrega ASC", params)
    pedidos_rows = cursor.fetchall()
    
    pedidos_final = []
    for row in pedidos_rows:
        p = dict(row)
        
        # 2. Manejo de formato de hora
        try:
            fecha_str = p['horario_entrega']
            hora_corta = fecha_str.split(' ')[1][:5] 
        except:
            hora_corta = "--:--"
        
        p['hora_corta'] = hora_corta

        # 3. Buscar productos de ESTE pedido (BLOQUE CORREGIDO E INDENTADO)
        cursor.execute("""
            SELECT ip.id, ip.cantidad, pl.nombre 
            FROM items_pedido ip
            JOIN platos pl ON ip.id_plato = pl.id_plato
            WHERE ip.id_pedido = ?
        """, (p['id_pedido'],))

        items_lista = []
        rows_items = cursor.fetchall()
        
        for item in rows_items:
            # Buscamos modificadores/variantes para cada producto del pedido
            cursor.execute("""
                SELECT nombre_opcion 
                FROM items_pedido_modificadores 
                WHERE id_item_pedido = ?
            """, (item['id'],))
            
            mods = [m['nombre_opcion'] for m in cursor.fetchall()]
            
            item_dict = dict(item)
            item_dict['detalle'] = " | ".join(mods) # Unimos variantes: "Punto Cocido | Extra Bacon"
            items_lista.append(item_dict)

        # Guardamos la lista de productos dentro del pedido
        p['items'] = items_lista
        
        # Agregamos el pedido completo a la lista final
        pedidos_final.append(p)
        
    conn.close()
    return jsonify(pedidos_final)



def _fetch_report_data(sd, ed, cid):
    f1, f2 = sd + " 00:00:00", ed + " 23:59:59"
    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Obtener lista detallada de pedidos (NUEVO)
    query_pedidos = "SELECT * FROM pedidos WHERE fecha_creacion BETWEEN ? AND ?"
    params = [f1, f2]
    if cid and cid != 'all':
        query_pedidos += " AND id_empresa = ?"
        params.append(cid)
    
    cursor.execute(query_pedidos + " ORDER BY fecha_creacion DESC", params)
    pedidos_detallados = [dict(row) for row in cursor.fetchall()]
    
    # 2. Total de ingresos
    ingresos_totales = sum(p['costo_total'] for p in pedidos_detallados)

    # 3. Top productos (tu lógica actual)
    cursor.execute("""
        SELECT pl.nombre, pl.rubro, SUM(ip.cantidad) as total_cantidad_vendida 
        FROM items_pedido ip 
        JOIN platos pl ON ip.id_plato = pl.id_plato 
        JOIN pedidos p ON ip.id_pedido = p.id_pedido 
        WHERE p.fecha_creacion BETWEEN ? AND ? 
        GROUP BY pl.id_plato 
        ORDER BY total_cantidad_vendida DESC
    """, [f1, f2])
    top_selling = [dict(row) for row in cursor.fetchall()]

    # 4. Medios de pago
    cursor.execute("""
        SELECT forma_pago, COUNT(*) as total_usos, SUM(costo_total) as total_monto 
        FROM pedidos WHERE fecha_creacion BETWEEN ? AND ? 
        GROUP BY forma_pago
    """, [f1, f2])
    pagos = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {
        'pedidos_detallados': pedidos_detallados,
        'ingresos_totales': ingresos_totales,
        'top_selling_overall': top_selling,
        'most_used_payment_methods': pagos
    }

def _obtener_pedido_por_token(token):
    """Busca el ID de un pedido usando su token único y luego carga el pedido completo."""
    conn = conectar_db()
    cursor = conn.cursor()
    # Buscamos el ID del pedido asociado a ese token secreto
    cursor.execute("SELECT id_pedido FROM pedidos WHERE token = ?", (token,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        # Si el token existe, cargamos los datos y los items del pedido.
        # Usamos bypass_security=True porque el token ya es la prueba de acceso.
        return _obtener_pedido_completo_por_id(res['id_pedido'], bypass_security=True)
    return None


def _obtener_pedido_completo_por_id(id_pedido, bypass_security=False):
    conn = conectar_db(); cursor = conn.cursor()
    
    # Lógica de seguridad (se mantiene igual)
    if bypass_security:
        cursor.execute("SELECT * FROM pedidos WHERE id_pedido = ?", (id_pedido,))
    elif current_user.is_authenticated:
        if current_user.has_role('super_admin'):
            cursor.execute("SELECT * FROM pedidos WHERE id_pedido = ?", (id_pedido,))
        else:
            cursor.execute("SELECT * FROM pedidos WHERE id_pedido = ? AND id_empresa = ?", (id_pedido, current_user.id_empresa))
    else:
        conn.close(); return None
        
    p = cursor.fetchone()
    if not p: conn.close(); return None
    
    # Construcción del objeto Pedido con todos los campos CRM
    ped = Pedido(
        id_pedido=p['id_pedido'], cliente_nombre=p['cliente_nombre'], cliente_apellido=p['cliente_apellido'], 
        direccion_entrega=p['direccion_entrega'], es_envio=p['es_envio'], horario_entrega=p['horario_entrega'], 
        costo_envio=p['costo_envio'], costo_total=p['costo_total'], forma_pago=p['forma_pago'], 
        estado_pago=p['estado_pago'], fecha_creacion=p['fecha_creacion'], lat_cliente=p['lat_cliente'], 
        lon_cliente=p['lon_cliente'], estado_envio=p['estado_envio'], id_empresa=p['id_empresa'], 
        token=p['token'], id_cliente=p['id_cliente'], telefono_cliente=p['telefono_cliente']
    )
    
    # --- CARGA UNIFICADA DE PLATOS Y PROMOCIONES (FIX TICKETS) ---
    # Buscamos en ambas tablas para obtener el nombre correspondiente
    cursor.execute("""
        SELECT 
            ip.id, 
            ip.id_plato, 
            ip.id_promocion,
            ip.cantidad, 
            ip.precio_unitario, 
            pl.nombre as nombre_plato,
            pr.nombre as nombre_promo
        FROM items_pedido ip 
        LEFT JOIN platos pl ON ip.id_plato = pl.id_plato 
        LEFT JOIN promociones pr ON ip.id_promocion = pr.id_promocion
        WHERE ip.id_pedido = ?
    """, (id_pedido,))
    
    for i in cursor.fetchall(): 
        # Determinamos el nombre final: si no hay nombre de plato, usamos el de promo
        nombre_item = i['nombre_plato'] if i['nombre_plato'] else i['nombre_promo']
        
        # Si por alguna razón ambos son NULL (no debería pasar), ponemos un texto genérico
        if not nombre_item:
            nombre_item = "Producto no identificado"

        # Buscamos los detalles (elección del combo o extras del plato)
        cursor.execute("SELECT nombre_opcion FROM items_pedido_modificadores WHERE id_item_pedido = ?", (i['id'],))
        mods = cursor.fetchall()
        detalle_texto = " / ".join([m['nombre_opcion'] for m in mods])
        
        # Agregamos el ítem al pedido pasando el nombre resuelto
        ped.agregar_item(nombre_item, i['cantidad'], i['precio_unitario'], detalle_texto)
    
    conn.close()
    return ped


def init_app():
    crear_tablas()
    _agregar_super_admin_inicial()

if __name__ == '__main__':
    init_app()
    app.run(debug=True, host='0.0.0.0', port=5000)