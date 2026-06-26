# casa_comida_web/models.py


from datetime import datetime
from flask_login import UserMixin

class Usuario(UserMixin):
    def __init__(self, id_usuario, email, password, nombre, apellido, id_rol, id_empresa, activo=1, primer_login_requerido=1, nombre_rol=None, id_repartidor_vinculado=None, telefono=None):
        self.id = id_usuario
        self.email = email
        self.password = password
        self.nombre = nombre
        self.apellido = apellido
        self.id_rol = id_rol
        self.id_empresa = id_empresa
        self.activo = activo
        self.primer_login_requerido = primer_login_requerido
        self.nombre_rol = nombre_rol
        self.id_repartidor_vinculado = id_repartidor_vinculado
        self.telefono = telefono # <--- NUEVO CAMPO

    # ... (tus métodos get_id, is_active, etc. se mantienen igual)

    def get_id(self): 
        return str(self.id)

    def is_active(self): 
        return bool(self.activo)

    def get_full_name(self): 
        return f"{self.nombre} {self.apellido}"

    # En models.py
    def has_role(self, *role_names):
        """Acepta uno o varios roles, ej: has_role('admin', 'empleado')"""
        if self.nombre_rol:
            # Comparamos el rol del usuario contra la lista de roles permitidos
            return self.nombre_rol.lower() in [r.lower() for r in role_names]
        return False
    #def has_role(self, role_name):
    #    # Punto 1: Comparación insensible a mayúsculas/minúsculas para evitar errores 403
    #    if self.nombre_rol:
    #        return self.nombre_rol.lower() == role_name.lower()
    #    return False
    
class Plato:
    def __init__(self, id_plato, nombre, descripcion, precio, activo=1, id_empresa=None, rubro=None, imagen=None):
        self.id_plato = id_plato
        self.nombre = nombre
        self.descripcion = descripcion
        self.precio = precio
        self.activo = activo
        self.id_empresa = id_empresa
        self.rubro = rubro
        self.imagen = imagen
        self.modificadores = [] # Nueva lista para guardar las opciones

    def cargar_modificadores(self, db_cursor):
        """Carga todos los modificadores y opciones de la base de datos"""
        db_cursor.execute("SELECT * FROM plato_modificadores WHERE id_plato = ?", (self.id_plato,))
        mods = db_cursor.fetchall()
        for m in mods:
            mod_dict = dict(m)
            db_cursor.execute("SELECT * FROM plato_opciones WHERE id_modificador = ?", (m['id_modificador'],))
            mod_dict['opciones'] = [dict(o) for o in db_cursor.fetchall()]
            self.modificadores.append(mod_dict)

# En models.py

class Pedido:
    def __init__(self, id_pedido, cliente_nombre, cliente_apellido, direccion_entrega, es_envio,
                 horario_entrega, costo_envio, costo_total, forma_pago, estado_pago, fecha_creacion,
                 lat_cliente=None, lon_cliente=None, estado_envio='Recibido', id_empresa=None, 
                 id_repartidor=None, fecha_pago=None, token=None, id_cliente=None, 
                 telefono_cliente=None): # <--- id_cliente añadido
        
        self.id_pedido = id_pedido
        self.token = token
        self.id_cliente = id_cliente # <--- Guardamos el ID del cliente para el CRM
        self.cliente_nombre = cliente_nombre
        self.cliente_apellido = cliente_apellido
        self.direccion_entrega = direccion_entrega
        self.telefono_cliente = telefono_cliente 
        self.es_envio = bool(es_envio)
        
        from datetime import datetime
        
        # --- PROCESAMIENTO ROBUSTO DE horario_entrega ---
        if isinstance(horario_entrega, str):
            try:
                # Intentamos el formato estándar con segundos
                self.horario_entrega = datetime.strptime(horario_entrega, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    # Intentamos el formato sin segundos
                    self.horario_entrega = datetime.strptime(horario_entrega, '%Y-%m-%d %H:%M')
                except ValueError:
                    # Si el dato es "Cerrado" o cualquier texto no válido, lo dejamos como string
                    # El HTML deberá manejar esto con un {% if %}
                    self.horario_entrega = horario_entrega
        else:
            self.horario_entrega = horario_entrega

        # --- PROCESAMIENTO ROBUSTO DE fecha_creacion ---
        if isinstance(fecha_creacion, str):
            try:
                self.fecha_creacion = datetime.strptime(fecha_creacion, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    self.fecha_creacion = datetime.strptime(fecha_creacion, '%Y-%m-%d %H:%M')
                except ValueError:
                    # Fallback a la hora actual si el formato de creación es totalmente inválido
                    self.fecha_creacion = datetime.now()
        else:
            self.fecha_creacion = fecha_creacion
        
        self.costo_envio = costo_envio
        self.costo_total = costo_total
        self.forma_pago = forma_pago
        self.estado_pago = estado_pago
        self.estado_envio = estado_envio
        self.lat_cliente = lat_cliente
        self.lon_cliente = lon_cliente
        self.id_empresa = id_empresa
        self.id_repartidor = id_repartidor
        self.fecha_pago = fecha_pago
        self.items = []

 
        
        
        
    def agregar_item(self, plato, cantidad, precio_unitario, detalles=""):
        nombre_plato = plato.nombre if hasattr(plato, 'nombre') else plato
        self.items.append({
            "plato_nombre": nombre_plato, 
            "cantidad": cantidad, 
            "precio_unitario": precio_unitario,
            "detalles": detalles
        })