import os
import sys
import json
import datetime
import re

# === FUNCIONES DE AYUDA ===

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

def _generate_report_html_content(all_comparisons_data, version_number, timestamp_html, time_elapsed_global, umbral_pixeles):
    """Genera la cadena completa del HTML final."""
    
    total_urls = len(all_comparisons_data)
    sites_with_red_diff = sum(1 for data in all_comparisons_data if data['alert_color'] == 'red')
    
    all_details_html = ""
    for data in all_comparisons_data:
        
        display_name = data.get('description', data['base_url']) 
        
        if data['alert_color'] == 'red':
            result_summary_text = f"❌ Se detectaron {data['diff_count']} diferencias graves."
            result_color_style = "red"
        else:
            result_summary_text = "✅ No se encontraron diferencias graves."
            result_color_style = "green"
            
        result_summary = f"""
        <p><strong>URL Base (V1):</strong> <code>{data['url1']}</code></p>
        <p><strong>URL Comparada (V2):</strong> <code>{data['url2']}</code></p>
        <p>
            <strong>Resultado:</strong> 
            <span style="font-weight: bold; color: {result_color_style}">
            {result_summary_text}
            </span>
        </p>
        <p><strong>Tiempo de Ejecución:</strong> {data['time_elapsed']}</p> 
        """
        
        # El path al archivo PNG debe ser relativo a la carpeta 'artifacts', donde se guardará el HTML.
        all_details_html += f"""
        <div style="border: 2px solid #ddd; padding: 15px; margin-top: 20px; border-radius: 8px;">
            <h2>{display_name}</h2>
            {result_summary}
            
            <details>
                <summary style="cursor: pointer; font-weight: bold; color: #1e3a8a; display: flex; align-items: center;">
                    Detalle de diferencias (Rojo: Grave, Azul: Desplazamiento Menor)
                    <span class="arrow-icon" style="font-size: 1.2em; margin-left: 10px; transition: transform 0.2s; display: inline-block;">&#9660;</span>
                </summary>
                <div id="diff-list-{data['url_id']}" class="diff-container" style="margin-top: 10px; background: #fff; padding: 10px; border: 1px solid #eee;">
                    {data['html_fallas_detalle']}
                </div>
            </details>

            <details>
                <summary style="cursor: pointer; font-weight: bold; color: #1e3a8a; display: flex; align-items: center;">
                    Contexto Visual
                    <span class="arrow-icon" style="font-size: 1.2em; margin-left: 10px; transition: transform 0.2s; display: inline-block;">&#9660;</span>
                </summary>
            <div class='container' id='container-{data['url_id']}'>
                <div>
                    <h4>Versión Base (V1)</h4>
                    <img src='{data['filename1']}' alt='Versión 1'>
                </div>
                <div id="image-container-{data['url_id']}" style="position: relative;">
                    <h4>Versión Nueva (V2) - Diferencias graves (Rojo) o menores (Azul)</h4>
                    <img id="screenshot-{data['url_id']}" src='{data['filename2_diff']}' alt='Versión 2 (Diferencias)'>
                    <div id="highlight-box-{data['url_id']}" class="highlight-box" style="display: none;"></div>
                </div>
            </div>
            </details>

        </div>
        """
        
    global_result_color = 'red' if sites_with_red_diff > 0 else 'green'
    global_result_text = f'❌ Se encontraron diferencias graves en {sites_with_red_diff} de {total_urls} urls.' if sites_with_red_diff > 0 else '✅ Todas las URLs pasaron la prueba estructural (no se detectaron diferencias graves).'

    html_summary = f"""
    <p><strong>Versión Testeada:</strong> <code>{version_number}</code></p>
    <p><strong>Fecha y Hora de Consolidación:</strong> {format_date(timestamp_html)} {timestamp_html.split('_')[1][:2]}:{timestamp_html.split('_')[1][2:4]}:{timestamp_html.split('_')[1][4:6]}</p> 
    <p><strong>Tiempo Total de Proceso (Estimado):</strong> {format_time(time_elapsed_global)}</p> 
    <p>
        <strong>Umbral de Tolerancia:</strong> {umbral_pixeles} píxeles.
    </p>
    <p>
        <strong>Resumen global:</strong> 
        <span style="font-weight: bold; color: {global_result_color}">
        {global_result_text}
        </span>
    </p>
    """
    
    javascript_code = """
    <script>
        let lastHighlightedItem = null;
        const ARROW_HEIGHT = -5; // Ajuste para la flecha indicadora
        const ORIGINAL_MOBILE_WIDTH = 412; // Ancho configurado del driver de Selenium

        function highlightElement(urlId, coordsStr, clickedItem) {
            if (lastHighlightedItem) {
                lastHighlightedItem.style.backgroundColor = 'transparent';
            }

            clickedItem.style.backgroundColor = '#fffacd'; 
            lastHighlightedItem = clickedItem;

            const imageContainer = document.getElementById(`image-container-${urlId}`); 
            const screenshot = document.getElementById(`screenshot-${urlId}`);
            const highlightBox = document.getElementById(`highlight-box-${urlId}`);
            
            if (!screenshot || !highlightBox || !imageContainer) return;

            const coords = coordsStr.split(',').map(Number);
            const [origX, origY, origW, origH] = coords;
            
            const displayedWidth = screenshot.clientWidth;
            
            if (displayedWidth > 0 && ORIGINAL_MOBILE_WIDTH > 0) {
                const scaleFactor = displayedWidth / ORIGINAL_MOBILE_WIDTH; 

                const scaledX = origX * scaleFactor;
                const scaledY = origY * scaleFactor;
                
                // Posicionamiento de la flecha
                highlightBox.style.display = 'block';
                highlightBox.style.left = `${scaledX + (origW * scaleFactor / 2)}px`; 
                highlightBox.style.top = `${scaledY - ARROW_HEIGHT}px`; 
                
                // Scroll al elemento
                const imageContainerRect = imageContainer.getBoundingClientRect();
                const targetY = window.pageYOffset + imageContainerRect.top + scaledY; 

                window.scrollTo({
                    top: targetY - 100, 
                    behavior: 'smooth'
                });
                
            } else {
                highlightBox.style.display = 'none';
            }
        }
        
        window.addEventListener('resize', () => {
             if (lastHighlightedItem) {
                const coordsStr = lastHighlightedItem.getAttribute('data-coords');
                let listContainer = lastHighlightedItem.closest('.diff-container');
                if (listContainer) {
                    const urlId = listContainer.id.replace('diff-list-', '');
                    highlightElement(urlId, coordsStr, lastHighlightedItem); 
                }
            }
        });
        
        document.querySelectorAll('details').forEach(detail => {
            const arrow = detail.querySelector('.arrow-icon');
            if (detail.open && arrow) {
                 arrow.style.transform = 'rotate(180deg)';
            }
            detail.addEventListener('toggle', () => {
                if (arrow) {
                    arrow.style.transform = detail.open ? 'rotate(180deg)' : 'rotate(0deg)';
                }
            });
        });
        
        const scrollButton = document.getElementById('scrollToTopBtn');

        window.onscroll = function() {
            if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
                scrollButton.style.display = "block";
            } else {
                scrollButton.style.display = "none";
            }
        };

        scrollButton.onclick = function() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        };
    </script>
    """
    
    html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <title>Reporte CONSOLIDADO de Regresión Mobile - Prod Versión {version_number}</title>
    <style>
    body {{ font-family: Arial; background: #f7f7f7; margin: 20px; }}
    h1 {{ color: #1e3a8a; border-bottom: 3px solid #bfdbfe; padding-bottom: 10px; }}
    h2 {{ margin-top: 40px; color: #555; border-bottom: 2px solid #ccc; padding-bottom: 5px; }}
    h3, h4 {{ color: #000; margin-top: 10px; margin-bottom: 5px; font-size: 1em; }}
    code {{ background-color: #eee; padding: 2px 4px; border-radius: 3px; }}
    details > summary {{ list-style: none; }} 
    
    .container {{ 
        display: flex; 
        gap: 20px; 
        margin-bottom: 40px; 
        align-items: flex-start;
        border: 1px solid #eee;
        padding: 10px;
        background: #fafafa;
        border-radius: 4px;
        overflow-x: auto; 
        overflow-y: hidden; 
    }}
    .container > div {{ 
        flex: 1; 
        min-width: 412px; 
    }}
    div[id^="image-container-"] {{
        position: relative; 
        border: 1px solid #ddd;
    }}
    img {{ 
        width: 100%; 
        height: auto;
        border: 3px solid #ccc; 
        border-radius: 4px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        display: block;
    }}
    
    .highlight-box {{
        position: absolute;
        pointer-events: none; 
        z-index: 1000;
        opacity: 1; 
        border-left: 15px solid transparent; 
        border-right: 15px solid transparent; 
        border-top: 30px solid #ffcc00; 
        transform: translateX(-50%); 
        filter: drop-shadow(0px 0px 5px rgba(0, 0, 0, 0.5));
    }}
    
    #scrollToTopBtn {{
        display: none; 
        position: fixed;
        bottom: 20px;
        right: 30px;
        z-index: 99;
        border: none;
        outline: none;
        background-color: #1e3a8a; 
        color: white;
        cursor: pointer;
        padding: 15px;
        border-radius: 50%; 
        font-size: 18px;
        line-height: 0; 
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        transition: background-color 0.3s, opacity 0.3s;
    }}
    #scrollToTopBtn:hover {{
        background-color: #3b82f6; 
    }}
    </style>
    </head>
    <body>
    <h1>Reporte CONSOLIDADO de Regresión - Mobile Prod - Versión {version_number}</h1>
    {html_summary}
    <hr style="margin-top: 20px; margin-bottom: 20px;"/>
    
    <div id="report-details-container">
        {all_details_html}
    </div>
    
    <button id="scrollToTopBtn" title="Ir Arriba">↑</button> 
    
    {javascript_code}  
    
    </body>
    </html>
    """
    return html

def consolidate_and_generate_report(version_number):
    """
    Recorre los artefactos, carga los datos JSON y genera el HTML final.
    """
    
    print("Recopilando datos parciales de los grupos...")
    
    # La carpeta 'artifacts' contiene subcarpetas (una por cada grupo) descargada por la acción
    all_data = []
    
    # Usamos os.walk para buscar en todas las subcarpetas de 'artifacts'
    for root, _, files in os.walk("artifacts"):
        for file in files:
            # Buscamos los archivos JSON que contienen los resultados parciales de cada grupo
            if file.startswith("data_G") and file.endswith(".json"):
                json_path = os.path.join(root, file)
                print(f"  -> Procesando {json_path}")
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        partial_data = json.load(f)
                        all_data.extend(partial_data)
                except Exception as e:
                    print(f"Error al leer JSON {file}: {e}")

    if not all_data:
        print("❌ ERROR: No se encontraron datos para consolidar.")
        sys.exit(1)
        
    # 2. Generar el reporte HTML final
    current_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    time_elapsed_global = 0 # Valor ficticio, ya que el tiempo real es la suma del job más largo
    
    # Asumimos UMBRAL_PIXELES_TOLERANCIA fue 0
    html_content = _generate_report_html_content(all_data, version_number, current_timestamp, time_elapsed_global, umbral_pixeles=0)
    
    # 3. Guardar el archivo final en la carpeta 'artifacts'
    if not os.path.exists("artifacts"):
         os.makedirs("artifacts")
         
    html_file = os.path.join("artifacts", f"Reporte_FINAL_v{version_number}_{current_timestamp}.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n==================================================================================")
    print(f"✅ CONSOLIDACIÓN COMPLETA. Total de URLs procesadas: {len(all_data)}")
    print(f"📄 Reporte HTML FINAL generado: {html_file}")
    print(f"==================================================================================")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python consolidate_report.py [VERSION]")
        sys.exit(1)
        
    version_number = sys.argv[1]
    consolidate_and_generate_report(version_number)
