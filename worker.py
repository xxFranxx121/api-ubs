import queue
import threading
import time
import os
import threading
import time
import os
import fitz  # PyMuPDF
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, JavascriptException
from selenium.webdriver.chrome.options import Options

class SeleniumWorker:
    def __init__(self, download_dir=None):
        self.driver = None
        self.download_dir = download_dir or os.path.join(os.path.expanduser('~'), 'Desktop', 'ImpresionesPDF')
        os.makedirs(self.download_dir, exist_ok=True)
        self.is_running = False

    def start_session(self, user, password, fecha_desde, fecha_hasta, headless=True):
        """Starts the browser session and logs in."""
        if self.driver:
            return # Already running

        # --- Chrome Options ---
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--safeBrowse-disable-download-protection")
        
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "safeBrowse.enabled": False,
            "safeBrowse.disable_download_protection": True,
            "profile.default_content_setting_values.mixed_script": 1,
            "profile.automatic_downloads.enabled": True,
        }
        chrome_options.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(options=chrome_options)
        
        try:
            # --- Login Sequence ---
            self.driver.get('http://optimionline.no-ip.info:8090/optimi/solutions/SisCoAs/index.html#Login1')
            sleep(0.5)

            WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, '98490ef0d11481b55a2933297f883110'))).send_keys(user)
            WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, '5a969b1e46bd8a70f0ce27a68693badf'))).send_keys(password)
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, 'e189bf9dddf22c3098adddb3601fda95'))).click()
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.LINK_TEXT, 'Auditoría interna'))).click()
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.LINK_TEXT, 'Consulta estado de recetas'))).click()

            fechadesde_el = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID,'bb6d890dc04ff77bde10058f661699d8')))
            fechadesde_el.clear()
            fechadesde_el.send_keys(fecha_desde)

            fechahasta_el = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID,'78a7d6bd9195f1f8d126104aae10b66f')))
            fechahasta_el.clear()
            fechahasta_el.send_keys(fecha_hasta)
            
            self.is_running = True
            return True
        except Exception as e:
            self.stop_session()
            raise e

    def stop_session(self):
        """Closes the browser."""
        if self.driver:
            self.driver.quit()
            self.driver = None
        self.is_running = False

    def process_nai(self, nai):
        """Processes a single NAI."""
        if not self.driver or not self.is_running:
            raise Exception("Session not started")

        result_data = {
            "nai": nai,
            "recetas": [],
            "status": "Procesando"
        }

        try:
             # --- Search NAI ---
            campo_nai = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, '716a692a2c896631221b2cb820be3a41')))
            campo_nai.clear()
            campo_nai.send_keys(nai)

            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, 'f1879864891d24c3d14af1b5678de37f'))).click()
            sleep(2)

            detalle_buttons = []
            try:
                detalle_buttons = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'td.c0.table_button_detail_fa_fa'))
                )
            except TimeoutException:
                 pass # No results

            num_recetas = len(detalle_buttons)
            if num_recetas == 0:
                result_data["status"] = "No encontrado"
                return result_data

            result_data["status"] = "Encontrado"
            
            for i in range(num_recetas):
                receta_info = {}
                
                # Re-fetch buttons to avoid staleness
                buttons_a_procesar = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'td.c0.table_button_detail_fa_fa'))
                )
                if not buttons_a_procesar: break
                
                buttons_a_procesar[0].click()
                
                try:
                    # Wait for modal
                    tipo_paciente_locator_1 = (By.XPATH, "//div[@id='a71111d9c4ab7743546616e0deae5a11']//span[contains(@class, 'ui-select-match-text')]")
                    WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located(tipo_paciente_locator_1))
                except Exception:
                    pass

                # Extract Data
                receta_info["paciente"] = self._get_text((By.XPATH, "//div[@id='a71111d9c4ab7743546616e0deae5a11']//span[contains(@class, 'ui-select-match-text')]")) or \
                                          self._get_text((By.XPATH, "//div[@id='6caea413dc57625240f3b9dc09e28520']//span[contains(@class, 'ui-select-match-text')]"))
                
                obra_social_texto = self._get_text((By.XPATH, "//div[@id='dbe9fe1acd3824e179975ce296c8353d']//span[contains(@class, 'ui-select-match-text')]")) or \
                                    self._get_text((By.XPATH, "//div[@id='34bd25b82edac42301679c0906cb469e']//span[contains(@class, 'ui-select-match-text')]"))
                
                receta_info["obra_social"] = obra_social_texto
                
                # Extraer ID de Obra Social
                # Formatos esperados: "25 - PAMI(PAMI)" o "2 - IOSEP"
                receta_info["obra_social_id"] = None
                if obra_social_texto:
                    parts = obra_social_texto.split('-', 1)
                    if len(parts) > 1:
                        possible_id = parts[0].strip()
                        if possible_id.isdigit():
                            receta_info["obra_social_id"] = possible_id

                receta_info["afiliado"] = self._get_text((By.ID, "47aec2aaca9cba21c23786a6c0095b27"), es_input=True) or \
                                          self._get_text((By.ID, "934cfaaf1adbd6ff0e0dab303db50d14"), es_input=True)

                # Extraer Total UB
                receta_info["total_ub"] = self._get_text((By.ID, "95e029301877137a02013d5ca4f78391"), es_input=True)

                # --- IOSEP Logic (ID 2) ---
                # Si es IOSEP, calculamos el Total UB sumando las prácticas autorizadas ("A")
                if receta_info.get("obra_social_id") == "2" or "IOSEP" in (receta_info.get("obra_social") or "").upper():
                    try:
                        # Buscar filas de la tabla de prácticas
                        # Ajustar el selector según la estructura real, asumiendo que están en una tabla visible
                        rows = self.driver.find_elements(By.CSS_SELECTOR, "tr") 
                        
                        calculated_ub = 0.0
                        found_rows = False
                        
                        for row in rows:
                            try:
                                # Buscamos celdas específicas por clase
                                status_cell = row.find_elements(By.CLASS_NAME, "c2")
                                ub_cell = row.find_elements(By.CLASS_NAME, "c4")
                                
                                if status_cell and ub_cell:
                                    status_text = status_cell[0].text.strip()
                                    ub_text = ub_cell[0].text.strip()
                                    
                                    if status_text == "A":
                                        val = float(ub_text.replace(",", ".")) # Asumir formato decimal
                                        calculated_ub += val
                                        found_rows = True
                            except (ValueError, IndexError):
                                continue
                        
                        if found_rows:
                            receta_info["total_ub"] = f"{calculated_ub:.2f}"
                            
                    except Exception as e:
                        # Log error but keep original extracted value if calculation fails
                        print(f"Error calculating IOSEP UB: {e}")

                # Estado
                id_del_padre = "b32a29dffef3410eb2da1e02e1e335e6"
                xpath_locator = f"//div[@id='{id_del_padre}']//span[@class='ng-binding']"
                elementos_estado = self.driver.find_elements(By.XPATH, xpath_locator)
                if elementos_estado:
                    receta_info["estado"] = elementos_estado[0].text.strip()
                else:
                    receta_info["estado"] = "Desconocido"

                result_data["recetas"].append(receta_info)
                
                # Close Modal
                try:
                    WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, '4545e5d56c6ecac03fc3f165c0cc6edf'))).click()
                except:
                     # If regular close fails, try the fallback "Cerrar" button for unknown states
                     try:
                         id_boton_cerrar = 'bfe6d74aa1ef34254188450ec6ed9be2'
                         WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.ID, id_boton_cerrar))).click()
                     except:
                         pass

            # Reset for next NAI logic is handled by the caller or by explicit resets, 
            # but to mimic the loop, we should ensure we are back at the search screen.
            # However, the previous code had complex recovery. 
            # Ideally, we return the result and the caller processes the next one.
            # To be safe, we reload the search page if needed, but 'process_nai' should be atomic.
            self._reset_page() 
            
            return result_data

        except Exception as e:
            self._reset_page()
            return {"status": "Error", "error": str(e), "nai": nai}

    def _get_text(self, locator, es_input=False, timeout=5):
        try:
            if es_input:
                wait_condition = EC.presence_of_element_located(locator)
            else:
                wait_condition = EC.visibility_of_element_located(locator)
            elemento = WebDriverWait(self.driver, timeout).until(wait_condition)
            return elemento.get_attribute("value").strip() if es_input else elemento.text.strip()
        except TimeoutException:
            return ""

    def _reset_page(self):
        """Intents to reset the page to the search state."""
        try:
             url_consulta = 'http://optimionline.no-ip.info:8090/optimi/solutions/SisCoAs/index.html#Login1/consultaEstadoRecetas'
             if self.driver:
                self.driver.get(url_consulta)
        except:
            pass
