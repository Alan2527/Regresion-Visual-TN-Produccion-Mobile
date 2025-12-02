import os
import cv2
import numpy as np
import time
import datetime
import re
import io
import sys 
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json # <--- AGREGADO para guardar el resultado parcial

# === CONFIGURACIÓN GLOBAL ===
output_dir = "Reportes HTML - TN - MOBILE - PROD" 
os.makedirs(output_dir, exist_ok=True)

# Umbral de tolerancia en píxeles. (Ej: 2px de diferencia es aceptable, más es falla)
UMBRAL_PIXELES_TOLERANCIA = 0 

# Lista de IDs/Clases de contenedores de anuncios para neutralizar (OCULTAR).
AD_CONTAINER_IDS = [
    'ad-slot-header', 'parent-ad-slot-header', 'parent-ad-slot-caja', 
    'ad-slot-caja1', 'parent-ad-slot-caja2', 'ad-slot-caja3', 
    'google_ads_iframe_', 
    'dfp-ad', 
    'ad-slot-megalateral',
    'cont-sidebar-ad', 
    'aniBox', 
    'banner-container',
]

# MAPEO DE URLS A TESTEAR (Definición completa de las 18 URLs)
# Se definen aquí para que el script de paralelismo pueda dividirlas.
BASE_URLS_MAP = {
    "https://tn.com.ar/": "Homepage",
    "https://tn.com.ar/ultimas-noticias/": "Listado",
    "https://tn.com.ar/videos/": "Videos",
    "https://tn.com.ar/envivo/24hs/": "Vivo",
    "https://tn.com.ar/clima/": "Clima",
    "https://tn.com.ar/economia/divisas/dolar-oficial-hoy/": "Divisas",
    "https://tn.com.ar/podcasts/2025/05/14/soy-adoptada-una-identidad-dicha-con-orgullo/": "Podcast",
    "https://tn.com.ar/deportes/estadisticas/": "Estadisticas",
    "https://tn.com.ar/quinielas-loterias/": "Quinielas",
    "https://tn.com.ar/juegos/": "Juegos",
    "https://tn.com.ar/elecciones-2025/": "Elecciones",
    "https://tn.com.ar/deportes/automovilismo/2025/11/07/el-posteo-que-williams-le-dedico-a-colapinto-despues-de-ser-confirmado-en-alpine-para-la-temporada-2026-de-f1/": "Article",
    "https://tn.com.ar/economia/2025/11/11/el-secretario-del-tesoro-de-eeuu-confirmo-que-la-argentina-ya-utilizo-una-parte-del-swap-de-monedas/?outputType=amp": "AMP",
    "https://tn.com.ar/videos/2025/11/03/romina-giangreco-la-estilista-de-famosas-que-tiene-su-marca-de-trajes-sustentables/": "Video",
    "https://tn.com.ar/videos/policiales/2024/07/02/video-exclusivo-asi-llegaba-el-matrimonio-al-hospital-luego-de-que-la-mujer-sufriera-un-ataque-de-nervios/": "Video Dark",
    "https://tn.com.ar/economia/2025/11/09/vivir-a-credito-crece-el-endeudamiento-cotidiano-y-hasta-el-40-del-sueldo-se-destina-a-pagar-la-tarjeta/": "Longform c/fondo",
    "https://tn.com.ar/sociedad/2023/02/12/mapa-de-los-incendios-en-la-argentina-por-que-cada-verano-se-recrudece-el-fuego/": "Longform s/fondo",
    "https://tn.com.ar/deportes/futbol/2025/11/07/franco-colapinto-corre-la-primera-practica-y-la-clasificacion-sprint-del-gp-de-brasil/": "Liveblogging",
}

# ----------------------------------------------------
# --- Funciones de Utilidad (Tomadas del script original) ---
# ----------------------------------------------------

def format_time(seconds):
    """Convierte segundos totales a formato HH:MM:SS."""
    try:
        seconds = int(seconds)
        return str(datetime.timedelta(seconds=seconds))
    except (ValueError, TypeError):
        return "00:00:00"

def format_date(timestamp):
    """Convierte un timestamp (YYYYMMDD_HHMMSS) a formato DD/MM/AAAA."""
    try:
        dt_object = datetime.datetime.strptime(timestamp.split('_')[0], "%Y%m%d")
        return dt_object.strftime("%d/%m/%Y")
    except ValueError:
        return timestamp.split('_')[0]

def ejecutar_js_manipulacion(driver, script):
    """Ejecuta un script JavaScript, ignorando errores."""
    try:
        driver.execute_script(script)
    except Exception:
        pass

def limpiar_entorno_robusto(driver):
    """
    Realiza la ELIMINACIÓN de popups flotantes (cookies, notificaciones, suscripciones) 
    pero MANTIENE visible el contenido de ADS para medir su impacto estructural.
    """
    js_eliminar_popups = """
        var btn_close = document.querySelector('button.onetrust-close-btn-handler'); if (btn_close) { btn_close.click(); }
        var os_cancel = document.getElementById('onesignal-slidedown-cancel-button'); if (os_cancel) { os_cancel.click(); }
        var os_container = document.getElementById('onesignal-slidedown-container'); if (os_container) { os_container.remove(); }
        var alert_news = document.getElementById('alertNews'); if (alert_news) { alert_news.remove(); }
        var cookie_modal = document.getElementById('onetrust-consent-sdk'); if (cookie_modal) { cookie_modal.remove(); }
        var subscribe_modal_content = document.querySelector('.modal-content-subscribe'); 
        if (subscribe_modal_content) { subscribe_modal_content.remove(); }
        var modal_overlay = document.querySelector('.modal-backdrop');
        if (modal_overlay) { modal_overlay.remove(); }
        var high_z_index_items = document.querySelectorAll('*[style*="z-index"]:not(body):not(html)');
        high_z_index_items.forEach(function(el) {
            var style = window.getComputedStyle(el);
            var zIndex = style.zIndex;
            if (zIndex > 1000 || el.classList.contains('popup')) {
                el.style.display = 'none'; 
            }
        });
        document.body.style.overflowX = 'hidden'; 
        document.body.style.maxWidth = '100vw'; 
    """
    ejecutar_js_manipulacion(driver, js_eliminar_popups)
    
def forzar_carga_contenido(driver):
    """
    Ejecuta scrolls suaves para forzar la carga de lazy loading y estabilizar el DOM.
    """
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);") 
    time.sleep(8) 
    driver.execute_script("window.scrollTo(0, 0);") 
    time.sleep(8) 
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);") 
    time.sleep(8)
    driver.execute_script("window.scrollTo(0, 0);") 
    time.sleep(12) 

def obtener_estructura_dom(driver):
    js_script_css_selector = """
        function getCssSelector(el) {
            if (!(el instanceof Element)) return;
            var path = [];
            while (el.nodeType === Node.ELEMENT_NODE) {
                var selector = el.tagName.toLowerCase();
                if (el.id) {
                    selector += '#' + el.id;
                    path.unshift(selector);
                    break;
                } else {
                    var sib = el, nth = 1;
                    while (sib = sib.previousElementSibling) {
                        if (sib.tagName.toLowerCase() == selector) nth++;
                    }
                    if (nth != 1) selector += ":nth-child(" + nth + ")";
                }
                path.unshift(selector);
                el = el.parentNode;
            }
            return path.join(' > ');
        }

        var elements = document.querySelectorAll('div');
        var data = [];
        for (var i = 0; i < elements.length; i++) {
            var el = elements[i];
            var rect = el.getBoundingClientRect();
            
            if (rect.height < 5 || rect.width < 5 || rect.height === 0 || rect.width === 0) continue;
            
            if (el.classList && (
                el.classList.contains('fusion-app') ||
                el.classList.contains('common-layout') ||
                el.classList.contains('col-megalateral') ||
                el.classList.contains('default-article-color') ||
                el.classList.contains('col-content')
            )) continue;
            
            data.push({
                selector: getCssSelector(el),
                id_attr: el.id, 
                class_attr: el.className, 
                y: window.pageYOffset + rect.top,       
                height: rect.height,                     
                x: window.pageXOffset + rect.left,       
                width: rect.width                      
            });
        }
        return data;
    """
    
    data = []
    png = None
    
    try:
        driver.get(driver.current_url) 
        WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        
        limpiar_entorno_robusto(driver)
        time.sleep(10) 
        limpiar_entorno_robusto(driver) 
        forzar_carga_contenido(driver) 

        data = driver.execute_script(js_script_css_selector)
        
        total_height = driver.execute_script("return Math.max( document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight );")
        original_size = driver.get_window_size()
        driver.set_window_size(original_size['width'], total_height)
        png = driver.get_screenshot_as_png()
        driver.set_window_size(original_size['width'], original_size['height'])

    except Exception as e:
        print(f"     ❌ Error en la extracción/captura: {e}")
        data = [{'selector': 'FATAL ERROR', 'y': 0, 'height': 0, 'x': 0, 'width': 0}] 
        
    return data, png

def comparar_estructura_dom(data_v1, data_v2, umbral_pixeles):
    v2_map = {item['selector']: item for item in data_v2 if item['selector'] is not None}
    errores_agrupados = {}
    
    def add_falla(selector, tipo, diff, v1, v2, coords_v2):
        v1_val = v1 if isinstance(v1, (int, float)) else 0
        v2_val = v2 if isinstance(v2, (int, float)) else 0
        
        if selector not in errores_agrupados:
            errores_agrupados[selector] = {
                'selector': selector,
                'tipos': [],
                'coords_v2': coords_v2,
                'cambio_dimension': 0,
                'cambio_posicion': 0,
                'gravedad': 'menor' 
            }
        
        v1_display = f"{v1:.2f}" if isinstance(v1, (int, float)) else str(v1)
        v2_display = f"{v2:.2f}" if isinstance(v2, (int, float)) else str(v2)
        diff_display = f"{diff:.2f}px" if isinstance(diff, (int, float)) else str(diff)

        detalle = f"Tipo: <b>{tipo}</b> | V1: {v1_display} | V2: {v2_display} | Diff: {diff_display}"
        errores_agrupados[selector]['tipos'].append(detalle)
        
        if 'ALTURA (H)' in tipo or 'ANCHO (W)' in tipo:
             errores_agrupados[selector]['cambio_dimension'] += 1
        elif 'POSICIÓN (Y)' in tipo or 'POSICIÓN (X)' in tipo:
             errores_agrupados[selector]['cambio_posicion'] += 1
        
        if tipo in ['AUSENTE V2', 'NUEVO EN V2']:
            errores_agrupados[selector]['gravedad'] = 'grave'

    for item1 in data_v1:
        selector = item1['selector']
        if selector in v2_map and selector is not None:
            item2 = v2_map[selector]
            
            diff_height = abs(item1['height'] - item2['height'])
            if diff_height > umbral_pixeles:
                add_falla(selector, 'DIFERENCIA ALTURA (H)', diff_height, item1['height'], item2['height'], item2)

            diff_y = abs(item1['y'] - item2['y'])
            if diff_y > umbral_pixeles:
                 add_falla(selector, 'DIFERENCIA POSICIÓN (Y)', diff_y, item1['y'], item2['y'], item2)
            
            diff_width = abs(item1['width'] - item2['width'])
            if diff_width > umbral_pixeles:
                add_falla(selector, 'DIFERENCIA ANCHO (W)', diff_width, item1['width'], item2['width'], item2)
            
            diff_x = abs(item1['x'] - item2['x'])
            if diff_x > umbral_pixeles:
                 add_falla(selector, 'DIFERENCIA POSICIÓN (X)', diff_x, item1['x'], item2['x'], item2)
        
        elif selector not in ['ERROR', 'FATAL ERROR'] and selector is not None:
             coords_v1_for_mark = {'x': item1['x'], 'y': item1['y'], 'width': item1['width'], 'height': item1['height']} 
             add_falla(selector, 'AUSENTE V2', "N/A", "N/A", "N/A", coords_v1_for_mark)
            
    v1_selectors = set(item['selector'] for item in data_v1 if item['selector'] is not None)
    for item2 in data_v2:
        selector = item2['selector']
        if selector not in v1_selectors and selector not in ['ERROR', 'FATAL ERROR'] and selector is not None:
            coords_v2_for_mark = {'x': item2['x'], 'y': item2['y'], 'width': item2['width'], 'height': item2['height']} 
            add_falla(selector, 'NUEVO EN V2', "N/A", "N/A", "N/A", coords_v2_for_mark)

    fallas_final = []
    for selector, data in errores_agrupados.items():
        if data['gravedad'] == 'grave' or data['cambio_dimension'] > 0:
            data['gravedad'] = 'grave'
        elif data['cambio_posicion'] > 0:
            data['gravedad'] = 'menor'
        else:
             data['gravedad'] = 'menor'

        descripcion_consolidada = "<div style='margin-top: 5px; border-left: 2px solid #ccc; padding-left: 5px;'>"+ "<br>".join(data['tipos']) + "</div>"
        tipo_marcado = 'DIFERENCIA AGRUPADA GRAVE' if data['gravedad'] == 'grave' else 'DIFERENCIA AGRUPADA MENOR'
        
        fallas_final.append({
            'selector': selector,
            'tipo': tipo_marcado, 
            'diff': 1, 
            'v1': "Consolidado", 
            'v2': descripcion_consolidada, 
            'coords_v2': data['coords_v2']
        })
    return fallas_final, [f['selector'] for f in fallas_final]

def marcar_fallas_en_captura(png_data, fallas, data_v2): 
    if not png_data or not fallas:
        return None 
        
    img_np = np.frombuffer(png_data, np.uint8)
    img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
    
    selectores_ya_marcados = set()
    
    for f in fallas:
        selector = f.get('selector')
        tipo = f.get('tipo') 
        item_coords = f.get('coords_v2') 
        
        if selector in selectores_ya_marcados or item_coords is None:
            continue
            
        if 'GRAVE' in tipo:
            color_bgr = (0, 0, 255) # ROJO
            thickness = 5
        elif 'MENOR' in tipo:
            color_bgr = (255, 0, 0) # AZUL
            thickness = 3
        else:
            continue 

        x1 = int(item_coords['x'])
        y1 = int(item_coords['y'])
        x2 = int(item_coords['x'] + item_coords['width'])
        y2 = int(item_coords['y'] + item_coords['height'])
        
        height, width, _ = img.shape
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(width - 1, x2)
        y2 = min(height - 1, y2)
        
        if x2 > x1 and y2 > y1:
            cv2.rectangle(img, (x1, y1), (x2, y2), color_bgr, thickness) 
            selectores_ya_marcados.add(selector) 

    is_success, buffer = cv2.imencode(".png", img)
    if is_success:
        return buffer.tobytes()
    return None

def ejecutar_selenium_para_estructura(url):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") 
    options.add_argument("--window-size=412,892")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu") 
    options.add_argument("--log-level=3") 
    options.add_experimental_option('excludeSwitches', ['enable-logging']) 
    options.add_argument("--user-agent=Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
    
    driver = None
    data = []
    png = None
    
    try:
        os.environ['WDM_LOG_LEVEL'] = '0' 
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60) 
        driver.get(url)
        
        data, png = obtener_estructura_dom(driver)
        
    except Exception as e:
        print(f"❌ Error al inicializar/ejecutar Selenium en {url}: {e}")
        data = [{'selector': 'FATAL ERROR', 'y': 0, 'height': 0, 'x': 0, 'width': 0}]
    
    finally:
        if driver:
            driver.quit()
            
    return data, png

def _build_fallas_html_detail(fallas, data_v2, url_id):
    """
    Función helper para generar el HTML de la lista de fallas (se usará en ambos scripts).
    """
    fallas_html_detalle = "<ul>"
    for i, f in enumerate(fallas):
        coords = f.get('coords_v2', {'x':0, 'y':0, 'width':0, 'height':0})
        item_v2_original = next((item for item in data_v2 if item['selector'] == f['selector']), None)
        
        display_selector = f['selector'] 
        if item_v2_original:
            display_selector = ""
            if item_v2_original.get('class_attr'):
                display_selector += f"class={item_v2_original['class_attr'][:50]}"
            if item_v2_original.get('id_attr'):
                if display_selector:
                    display_selector += " / "
                display_selector += f"id={item_v2_original['id_attr']}"
            if not display_selector:
                display_selector = f['selector'].split(' > ')[-1]

        coords_str = f"{int(coords['x'])},{int(coords['y'])},{int(coords['width'])},{int(coords['height'])}"
        color = 'red' if 'GRAVE' in f['tipo'] else '#007bff' 
        detalle_consolidado = f['v2'] 
        tipo_resumen = f['tipo'].replace('AGRUPADA ', '')
        
        fallas_html_detalle += f"""
        <li class='diff-item' 
            style='color: {color}; border-bottom: 1px dotted #ccc; padding: 5px 0; cursor: pointer;'
            onclick="highlightElement('{url_id}', '{coords_str}', this)"
            data-coords="{coords_str}"
            data-selector="{f['selector']}"
            data-id="item-{url_id}-{i}"
            >
            <span style="font-weight: bold;">Elemento:</span> <code>{display_selector}</code> 
            <br><span style="font-weight: bold;">Resultado Agrupado:</span> <span style='color:{color};'>{tipo_resumen}</span>
            {detalle_consolidado}
        </li>
        """
    if not fallas:
         fallas_html_detalle += "<li>✅ No se encontraron diferencias.</li>"
    fallas_html_detalle += "</ul>"
    return fallas_html_detalle


# === SCRIPT PRINCIPAL MODIFICADO PARA PARALELISMO ===

if __name__ == "__main__":
    
    # 1. MANEJO DE ARGUMENTOS: [VERSION] y [NUMERO DE GRUPO]
    if len(sys.argv) < 3:
        print("\n❌ ERROR: Debe proporcionar la versión y el número de grupo como argumentos.")
        print("Uso: python regre_visual_tn_webmobile_prod.py [VERSION] [GRUPO]")
        print("Ejemplo: python regre_visual_tn_webmobile_prod.py 170 1")
        sys.exit(1)

    version_number = sys.argv[1]
    
    try:
        group_number = int(sys.argv[2]) # Número de grupo (1, 2, 3, 4, 5)
        if group_number < 1: raise ValueError
    except ValueError:
        print("❌ Error: El argumento de grupo debe ser un número entero positivo.")
        sys.exit(1)
        
    # 2. DIVISIÓN DE URLS EN GRUPOS
    url_list = list(BASE_URLS_MAP.items())
    urls_per_group = 4 
    
    start_index = (group_number - 1) * urls_per_group
    end_index = start_index + urls_per_group
    
    urls_to_test = url_list[start_index:end_index]

    if not urls_to_test:
        print(f"✅ Grupo {group_number} no contiene URLs. Saliendo.")
        sys.exit(0)
        
    urls_to_test_map = dict(urls_to_test)
    
    TIMESTAMP_EJECUCION = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    start_time_global = time.time()
    
    print(f"\n INICIANDO PROCESO DE REGRESIÓN MOBILE - PROD VERSIÓN {version_number} - GRUPO {group_number}")
    print(f" PROCESANDO {len(urls_to_test)} URLs en este runner.\n")
    
    # 3. EJECUCIÓN SECUENCIAL DENTRO DEL GRUPO
    all_comparisons_data = []
    
    for idx, (base_url, url_description) in enumerate(urls_to_test_map.items()):
        
        start_time_url = time.time()
        url_id = re.sub(r'[^a-zA-Z0-9]', '_', url_description).lower()

        url1 = base_url 
        if '?' in base_url:
            url2 = f"{base_url}&d={version_number}"
        else:
            url2 = f"{base_url}?d={version_number}"
        
        domain_name = re.sub(r'[^a-zA-Z0-9]', '_', url1.split('//')[-1]).strip('_')
        if not domain_name: domain_name = "home"
        domain_name = domain_name[:40]

        print(f"\n==================================================================================")
        print(f"[GRUPO {group_number} - URL {idx + 1}/{len(urls_to_test)}] | Página: {url_description}")

        # Obtener Datos DOM y Capturas
        print("  [V1] Obteniendo datos estructurales...")
        data_v1, png_v1 = ejecutar_selenium_para_estructura(url1)
        
        print("\n  [V2] Obteniendo datos estructurales...")
        data_v2, png_v2 = ejecutar_selenium_para_estructura(url2)

        # Comparar Estructuras
        if 'FATAL ERROR' in [d['selector'] for d in data_v1 + data_v2 if isinstance(d.get('selector'), str)]:
            fallas = [{'selector': 'FATAL ERROR (Revisar logs)', 'tipo': 'DIFERENCIA AGRUPADA GRAVE', 'diff': 'N/A', 'v1': 'N/A', 'v2': 'Error grave en la ejecución de Selenium.', 'coords_v2': {'x':0, 'y':0, 'width':0, 'height':0}}]
        else:
            print("\n  🔍 Comparando estructuras DOM (X, Y, W, H)...")
            fallas, _ = comparar_estructura_dom(data_v1, data_v2, UMBRAL_PIXELES_TOLERANCIA)

        # Filtrado y Marcado
        fallas_filtradas = [f for f in fallas if all(f.get('coords_v2', {}).get(coord) is not None and f.get('coords_v2', {}).get(coord) >= 0 for coord in ['x', 'y', 'width', 'height'])]
        fallas = fallas_filtradas 
        fallas_graves = [f for f in fallas if 'GRAVE' in f['tipo']] 
        
        png_v2_marcado = png_v2
        if fallas:
            print(f"  🔴🔵 Marcando visualmente las diferencias en la captura V2")
            png_v2_marcado = marcar_fallas_en_captura(png_v2, fallas, data_v2) 

        # Guardar capturas de pantalla 
        filename1 = f"{domain_name}_V{version_number}_base_G{group_number}_{TIMESTAMP_EJECUCION}.png"
        filename2_diff = f"{domain_name}_V{version_number}_diff_G{group_number}_{TIMESTAMP_EJECUCION}.png" 
        
        if png_v1: Image.open(io.BytesIO(png_v1)).save(os.path.join(output_dir, filename1))
        if png_v2_marcado: Image.open(io.BytesIO(png_v2_marcado)).save(os.path.join(output_dir, filename2_diff))

        # Generar HTML de las fallas detallado para el JSON
        fallas_html_detalle = _build_fallas_html_detail(fallas, data_v2, url_id)
        
        # Métrica y Resultado Final
        end_time_url = time.time()
        time_elapsed_url = end_time_url - start_time_url
        final_alert_color = "red" if fallas_graves else "green"
        
        comparison_data = {
            'base_url': base_url,
            'description': url_description, 
            'url1': url1,
            'url2': url2,
            'diff_count': len(fallas_graves), 
            'alert_color': final_alert_color, 
            'html_fallas_detalle': fallas_html_detalle,
            'filename1': filename1, 
            'filename2_diff': filename2_diff, 
            'time_elapsed': format_time(time_elapsed_url),
            'url_id': url_id 
        }
        all_comparisons_data.append(comparison_data)

        # Salida en Consola
        result_msg = f'❌ SE DETECTARON {len(fallas_graves)} DIFERENCIAS GRAVES' if final_alert_color == 'red' else '✅ PASÓ LA PRUEBA'
        result_color = '\033[91m' if final_alert_color == 'red' else '\033[92m' 
        
        print(f"\n  {result_color}RESULTADO: {result_msg}\033[0m")
        print(f"  Tiempo total para esta URL: {format_time(time_elapsed_url)}\n")

    # 4. Guardar los datos JSON de las comparaciones para la consolidación
    json_data_filename = f"data_G{group_number}_v{version_number}_{TIMESTAMP_EJECUCION}.json"
    with open(os.path.join(output_dir, json_data_filename), "w", encoding="utf-8") as f:
        json.dump(all_comparisons_data, f, indent=4)

    end_time_global = time.time()
    time_elapsed_global = end_time_global - start_time_global
    
    print(f"\n==================================================================================")
    print(f"✅ Proceso de regresión completado para GRUPO {group_number}.")
    print(f" Tiempo de ejecución del grupo: {format_time(time_elapsed_global)}")
    print(f"📄 Archivo de datos JSON creado: {json_data_filename}")
    print(f"==================================================================================")
