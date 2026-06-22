# casa_comida_web/services.py

import requests
import math
from datetime import datetime, timedelta
from config import GOOGLE_MAPS_API_KEY, SUCURSAL_LAT, SUCURSAL_LON, NOMBRE_CASA_COMIDA

def obtener_info_restaurante_google_maps(nombre_restaurante, api_key):
    """
    Busca información de un restaurante en Google Maps (Place Search y Place Details).
    Retorna un diccionario con nombre, dirección, coordenadas y horarios.
    """
    if not api_key or api_key == "YOUR_GOOGLE_MAPS_API_KEY":
        print("Advertencia: API Key de Google Maps no configurada. No se obtendrá información real.")
        return {
            "nombre": nombre_restaurante,
            "direccion": "Dirección de ejemplo (API Key no configurada).",
            "lat": SUCURSAL_LAT,
            "lon": SUCURSAL_LON,
            "horario_atencion": ["Lunes a Viernes: 09:00 - 23:00", "Sábado y Domingo: 10:00 - 00:00"],
            "url_mapa": "https://maps.google.com/?q=Casa+de+Comida+Ejemplo"
        }

    # 1. Place Search para encontrar el Place ID
    search_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params_search = {
        "input": nombre_restaurante,
        "inputtype": "textquery",
        "fields": "place_id",
        "key": api_key
    }
    try:
        response_search = requests.get(search_url, params=params_search)
        response_search.raise_for_status()
        data_search = response_search.json()

        if data_search["status"] == "OK" and data_search["candidates"]:
            place_id = data_search["candidates"][0]["place_id"]
        else:
            print(f"No se encontró Place ID para '{nombre_restaurante}'. Status: {data_search.get('status')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con la API de Google Places (Search): {e}")
        return None

    # 2. Place Details para obtener la información completa
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params_details = {
        "place_id": place_id,
        "fields": "name,formatted_address,geometry,opening_hours,url",
        "key": api_key
    }
    try:
        response_details = requests.get(details_url, params=params_details)
        response_details.raise_for_status()
        data_details = response_details.json()

        if data_details["status"] == "OK" and data_details["result"]:
            result = data_details["result"]
            horario = result.get("opening_hours", {}).get("weekday_text", ["Horario no disponible"])
            
            return {
                "nombre": result.get("name"),
                "direccion": result.get("formatted_address"),
                "lat": result["geometry"]["location"]["lat"],
                "lon": result["geometry"]["location"]["lng"],
                "horario_atencion": horario,
                "url_mapa": result.get("url")
            }
        else:
            print(f"No se encontraron detalles para el Place ID {place_id}. Status: {data_details.get('status')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con la API de Google Places (Details): {e}")
        return None

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



def calcular_distancia_cuadras(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia Haversine entre dos puntos en la Tierra y la convierte
    aproximadamente a "cuadras".
    1 grado de latitud ~ 111 km.
    1 cuadra ~ 80 metros.
    """
    R = 6371  # Radio de la Tierra en kilómetros

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) * math.sin(dlat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distancia_km = R * c
    distancia_cuadras = distancia_km / 0.08  # 1 cuadra = 80 metros = 0.08 km
    return distancia_cuadras

def generar_franjas_horarias(inicio_str="10:00", fin_str="23:00", intervalo_minutos=15):
    """Genera una lista de objetos datetime para las franjas horarias."""
    franjas = []
    hoy = datetime.now().date()
    
    try:
        inicio_hora, inicio_min = map(int, inicio_str.split(':'))
        fin_hora, fin_min = map(int, fin_str.split(':'))
    except ValueError:
        print("Error: Formato de hora inválido para generar franjas.")
        return []

    hora_actual_dt = datetime.now()
    inicio_hoy = datetime.combine(hoy, datetime.min.time()).replace(hour=inicio_hora, minute=inicio_min)
    fin_hoy = datetime.combine(hoy, datetime.min.time()).replace(hour=fin_hora, minute=fin_min)

    # Si el inicio de la franja es antes de ahora, empezar 15 minutos después de ahora
    if inicio_hoy < hora_actual_dt:
        # Redondear al siguiente intervalo de 15 minutos
        inicio_hoy = hora_actual_dt + timedelta(minutes=(intervalo_minutos - hora_actual_dt.minute % intervalo_minutos) % intervalo_minutos)
        inicio_hoy = inicio_hoy.replace(second=0, microsecond=0)

    current_time = inicio_hoy
    while current_time <= fin_hoy:
        franjas.append(current_time)
        current_time += timedelta(minutes=intervalo_minutos)
    return franjas