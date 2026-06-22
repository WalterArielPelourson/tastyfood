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
        # Manejo flexible de fechas
        self.horario_entrega = datetime.strptime(horario_entrega, '%Y-%m-%d %H:%M:%S') if isinstance(horario_entrega, str) else horario_entrega
        self.fecha_creacion = datetime.strptime(fecha_creacion, '%Y-%m-%d %H:%M:%S') if isinstance(fecha_creacion, str) else fecha_creacion
        
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

    def agregar_item(self, plato, cantidad, precio_unitario, detalles=""):
        nombre_plato = plato.nombre if hasattr(plato, 'nombre') else plato
        self.items.append({
            "plato_nombre": nombre_plato, 
            "cantidad": cantidad, 
            "precio_unitario": precio_unitario,
            "detalles": detalles
        })
    
    #def generar_ticket(self, nombre_empresa="Restaurante"):
    #    items_html = ""
    #    for item in self.items:
    #        detalles_display = f"<br><small style='color: #444; font-style: italic;'>&nbsp;&nbsp;↳ {item['detalles']}</small>" if item['detalles'] else ""
    #        
    #        items_html += f"""
    #        <tr>
    #            <td style='padding: 5px 0; line-height: 1.2;'>
    #                <strong>{item['cantidad']} x {item['plato_nombre']}</strong>
    #                {detalles_display}
    #            </td>
    #            <td style='text-align: right; vertical-align: top;'>${item['precio_unitario'] * item['cantidad']:.2f}</td>
    #        </tr>"""

    #    ticket_html = f"""
    #    <div style="font-family: 'Courier New', Courier, monospace; width: 300px; padding: 10px; border: 1px solid #ccc; background-color: white;">
    #        <h3 style="text-align: center; margin: 0; text-transform: uppercase;">{nombre_empresa}</h3>
    #        <p style="text-align: center; margin: 5px 0; font-weight: bold;">PEDIDO #{self.id_pedido}</p>
    #        <hr style="border-top: 1px dashed #000;">
    #        <div style="font-size: 14px;">
    #            <p style="margin: 3px 0;"><strong>Cliente:</strong> {self.cliente_nombre} {self.cliente_apellido}</p>
    #            <p style="margin: 3px 0;"><strong>Dirección:</strong> {self.direccion_entrega}</p>
    #            <p style="margin: 3px 0;"><strong>Entrega:</strong> {self.horario_entrega.strftime('%H:%M')} hs</p>
    #        </div>
    #        <hr style="border-top: 1px dashed #000;">
    #        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
    #            <tbody>{items_html}</tbody>
    #        </table>
    #        <hr style="border-top: 1px dashed #000;">
    #        <p>Subtotal: <span style="float: right;">${(self.costo_total - self.costo_envio):.2f}</span></p>
    #        <p>Envío: <span style="float: right;">${self.costo_envio:.2f}</span></p>
    #        <h4 style="margin: 10px 0;">TOTAL: <span style="float: right;">${self.costo_total:.2f}</span></h4>
    #        <hr style="border-top: 1px dashed #000;">
    #        <p style="text-align: center;"><strong>PAGO: {self.forma_pago.upper()}</strong></p>
    #    </div>
    #    """
    #    return ticket_html