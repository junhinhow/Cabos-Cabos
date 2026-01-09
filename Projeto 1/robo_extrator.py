import pyautogui
import pytesseract
import cv2
import numpy as np
import re
import time
import json
import os
import shutil
import base64
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# --- CONFIGURAÇÃO ---
ARQUIVO_CONFIG = 'config_coordenadas.json'
PASTA_PRINTS_CAMPOS = 'prints_campos'
PASTA_PRINTS_WEB = 'prints_web'
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

os.makedirs(PASTA_PRINTS_CAMPOS, exist_ok=True)
os.makedirs(PASTA_PRINTS_WEB, exist_ok=True)

def carregar_coordenadas():
    if not os.path.exists(ARQUIVO_CONFIG):
        print(f"❌ ERRO: '{ARQUIVO_CONFIG}' não encontrado.")
        return None
    with open(ARQUIVO_CONFIG, 'r') as f:
        return json.load(f)

def limpar_digitos(texto):
    return re.sub(r'\D', '', texto)

def tratar_moeda(texto):
    if not texto or texto == "[Vazio]": return "0,00"
    limpo = re.sub(r'[^\d,.]', '', texto)
    if not re.search(r'\d', limpo): return "0,00"
    while ',,' in limpo: limpo = limpo.replace(',,', ',')
    while '..' in limpo: limpo = limpo.replace('..', '.')
    return limpo.strip(',').strip('.')

def formatar_inscricao(texto):
    if not texto or texto == "[Vazio]": return "[Vazio]"
    return texto.replace(',', '.')

def corrigir_texto_comum(texto):
    if not texto: return ""
    texto_upper = texto.upper()
    if "Mª" in texto_upper or 'M"AS' in texto_upper or "MANªUS" in texto_upper:
        return "MANAUS"
    return texto

def ler_campo(nome, coords, modo_numerico=False):
    if coords[2] <= 0 or coords[3] <= 0: return ""
    screenshot = pyautogui.screenshot(region=tuple(coords))
    img = np.array(screenshot)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    fator = 3
    scaled = cv2.resize(gray, None, fx=fator, fy=fator, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(scaled, 160, 255, cv2.THRESH_BINARY)
    config = r'--psm 7 -c tessedit_char_whitelist=0123456789.,' if modo_numerico else r'--psm 7'
    try: texto = pytesseract.image_to_string(thresh, lang='por', config=config)
    except: texto = pytesseract.image_to_string(thresh, lang='eng', config=config)
    return texto.strip()

def extrair_sistema(mapa_campos):
    print("📸 Lendo campos do sistema...")
    pyautogui.screenshot("ultima_captura.png")
    shutil.copy("ultima_captura.png", os.path.join(PASTA_PRINTS_CAMPOS, "sistema_full.png"))
    
    dados = {}
    campos_moeda = ['LIMITE', 'SALDO_DEVEDOR']
    for campo, coords in mapa_campos.items():
        eh_moeda = campo in campos_moeda
        eh_cnpj = campo == 'CNPJ'
        valor = ler_campo(campo, coords, modo_numerico=(eh_moeda or eh_cnpj))
        
        if eh_moeda: valor = tratar_moeda(valor)
        elif campo == 'INSC_ESTADUAL': valor = formatar_inscricao(valor)
        elif campo == 'CIDADE' or campo == 'BAIRRO': valor = corrigir_texto_comum(valor)
            
        dados[campo] = valor if valor else "[Vazio]"
        print(f"   ↳ {campo}: {dados[campo]}")
    return dados

def get_text_safe(driver, xpath):
    try: return driver.find_element(By.XPATH, xpath).text.strip()
    except: return ""

def print_nuclear_cdp(driver, nome_arquivo):
    total_height = driver.execute_script("return document.body.scrollHeight")
    total_width = driver.execute_script("return document.body.scrollWidth")
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': total_width, 'height': total_height, 'deviceScaleFactor': 1, 'mobile': False,
    })
    res = driver.execute_cdp_cmd('Page.captureScreenshot', {
        'format': 'png', 'fromSurface': True, 'captureBeyondViewport': True
    })
    with open(nome_arquivo, "wb") as f:
        f.write(base64.b64decode(res['data']))
    driver.execute_cdp_cmd('Emulation.clearDeviceMetricsOverride', {})

def buscar_web(cnpj):
    print(f"🌍 Consultando Web: {cnpj}...")
    options = Options()
    options.add_argument("--start-maximized")
    prefs = {"profile.default_content_setting_values.notifications": 2}
    options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=options)
    web_data = {'razao': '---', 'endereco': '---', 'telefone': '---', 'email': '---', 'capital': '---'}
    
    try:
        driver.execute_cdp_cmd('Network.enable', {})
        driver.execute_cdp_cmd('Network.setBlockedURLs', {
            'urls': ["*googlesyndication*", "*doubleclick*", "*google-analytics*", "*criteo*", "*outbrain*", "*pubmatic*"]
        })
        driver.get(f"https://cnpj.biz/{cnpj}")
        time.sleep(3)
        
        driver.execute_script("""
            var style = document.createElement('style');
            style.innerHTML = `header, nav, footer, .ad_slot, .adsbygoogle, .banner-mobile, #cookie-bar, .cookie-consent, .modal, .popup, .overlay, #slot1, #slot2, #slot3, .infeed, .menu-mobile-transition, .btn-close, .nav, .breadcrumb { display: none !important; } body { overflow: visible !important; background: white !important; }`;
            document.head.appendChild(style);
        """)
        
        try: driver.execute_script("revealAllContacts();")
        except: pass
        time.sleep(2)
        
        caminho_print = os.path.join(PASTA_PRINTS_WEB, f"cnpj_{cnpj}.png")
        print_nuclear_cdp(driver, caminho_print)
        print(f"   📸 Print salvo: {caminho_print}")

        razao = get_text_safe(driver, "//p[contains(., 'Razão Social')]//b")
        if razao: web_data['razao'] = razao

        # --- CAPITAL SOCIAL ---
        capital = get_text_safe(driver, "//p[contains(., 'Capital Social')]//b")
        if capital: web_data['capital'] = capital

        parts = []
        l = get_text_safe(driver, "//p[contains(., 'Logradouro')]//b")
        n = get_text_safe(driver, "//p[contains(., 'Número')]//b")
        b = get_text_safe(driver, "//p[contains(., 'Bairro')]//b")
        m = get_text_safe(driver, "//p[contains(., 'Município')]//a")
        u = get_text_safe(driver, "//p[contains(., 'Estado')]//a")
        c = get_text_safe(driver, "//p[contains(., 'CEP')]//b")

        if l: parts.append(l)
        if n: parts.append(n)
        if b: parts.append(f"- {b}")
        if m and u: parts.append(f"- {m}/{u}")
        if c: parts.append(f"CEP: {c}")
        if parts: web_data['endereco'] = ", ".join(parts)
        else: web_data['endereco'] = get_text_safe(driver, "//p[contains(text(), 'Para correspondência')]").replace("Para correspondência:", "").strip()

        try:
            tels = driver.find_elements(By.CLASS_NAME, "telefone-revealed")
            lista = sorted(list(set([t.text.strip() for t in tels if t.text.strip()])))
            if lista: web_data['telefone'] = " / ".join(lista)
            else:
                hidden = driver.find_elements(By.CLASS_NAME, "telefone-hidden")
                if hidden: web_data['telefone'] = hidden[0].text + " (Oculto - Script bloqueado?)"
        except: pass
        
        try:
            mails = driver.find_elements(By.CLASS_NAME, "email-revealed")
            lista = sorted(list(set([m.text.strip() for m in mails if m.text.strip()])))
            if lista: web_data['email'] = " / ".join(lista)
        except: pass
    except Exception as e:
        print(f"⚠️ Erro Web: {e}")
    finally:
        driver.quit()
    return web_data

def salvar_relatorio(sis, web):
    sep = "-" * 80
    bloco = f"\n{sep}\n"
    bloco += f"AUDITORIA DO CLIENTE: {sis.get('CLIENTE_ID', '')} - {sis.get('CLIENTE_NOME', '')}\n"
    bloco += f"{sep}\n"
    insc_est = formatar_inscricao(sis.get('INSC_ESTADUAL', ''))
    bloco += f"CNPJ SISTEMA: {sis.get('CNPJ', '')}  |  WEB RAZÃO: {web['razao']}\n"
    bloco += f"CAPITAL SOCIAL (WEB): {web['capital']}\n"
    bloco += f"INSC. EST.:   {insc_est}  |  INSC. MUN.: {sis.get('INSC_MUNICIPAL', '')}\n\n"
    bloco += f"ENDEREÇO SYS: {sis.get('ENDERECO', '')}, {sis.get('COMPLEMENTO', '')} - {sis.get('BAIRRO', '')} - {sis.get('CIDADE', '')}\n"
    bloco += f"ENDEREÇO WEB: {web['endereco']}\n\n"
    bloco += f"CONTATO SYS:  {sis.get('CONTATO', '')}\n"
    bloco += f"TELEFONE SYS: {sis.get('TELEFONE', '')}\n"
    bloco += f"TELEFONE WEB: {web['telefone']}\n"
    bloco += f"EMAILS WEB:   {web['email']}\n\n"
    bloco += f"LIMITE:       {sis.get('LIMITE', '')}  |  SALDO DEVEDOR: {sis.get('SALDO_DEVEDOR', '')}\n"
    bloco += f"{sep}\n"
    print(bloco)
    with open("auditoria_completa.txt", "a", encoding="utf-8") as f:
        f.write(bloco)
    print("✅ Dados salvos em 'auditoria_completa.txt'")