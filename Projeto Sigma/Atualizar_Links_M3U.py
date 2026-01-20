import json
import os
import re
import time
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- IMPORTAÇÃO DO MOTOR POTENTE ---
try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("❌ ERRO: Biblioteca 'curl_cffi' faltando.")
    print("Instale: pip install curl_cffi --user")
    exit()

# --- CONFIGURAÇÕES ---
ARQUIVO_FONTES = "fontes.json"
MAX_WORKERS = 10  # Número de downloads simultâneos (ajuste conforme sua internet/CPU)

# Pastas
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_PARCERIAS = "Parcerias"
PASTA_TXTS = "TXTs"

# Arquivos de Texto
ARQUIVO_LOG_ERROS = os.path.join(PASTA_TXTS, "erros_mineracao.txt")
ARQUIVO_LINKS_APKS = os.path.join(PASTA_TXTS, "Links_APKs.txt")

# --- CONTROLE DE THREADS (LOCKS) ---
lock_arquivo = threading.Lock()  # Protege escrita em arquivos
lock_print = threading.Lock()    # Protege saídas no console
lock_stats = threading.Lock()    # Protege contadores

# --- ESTATÍSTICAS GLOBAIS ---
stats = {
    "atualizados": 0,
    "cacheados": 0,
    "erros": 0
}

APPS_PARCERIA = {
    "ASSIST": "Assist_Plus_Play_Sim", "PLAY SIM": "Assist_Plus_Play_Sim",
    "LAZER": "Lazer_Play", "VIZZION": "Vizzion", "UNITV": "UniTV",
    "UNI TV": "UniTV", "XCLOUD": "XCloud_TV", "P2P": "Codigos_P2P_Geral",
    "SMARTERS": "IPTV_Smarters_DNS", "XCIPTV": "XCIPTV_Dados",
    "SSIPTV": "SSIPTV_Playlist", "NETRANGE": "NetRange",
    "CLOUDDY": "Clouddy_App", "IBO": "IBO_Player", "DUPLEX": "Duplex_Play",
    "EAGLE": "Eagle_TV", "FLASH": "Flash_P2P", "TVE": "TV_Express",
    "TV EXPRESS": "TV_Express", "MY FAMILY": "MyFamily_Cinema",
    "MFC": "MyFamily_Cinema", "REDPLAY": "RedPlay", "BTV": "BTV_Codes",
    "HTV": "HTV_Codes", "YOUCINE": "YouCine", "BLUE": "Blue_TV",
    "UCAST": "UCast_App", "ALPHA": "Alpha_Master_App", "WAVE": "Wave_App",
    "TITÃ": "Tita_App", "ATENA": "Atena_App", "ANDRÔMEDA": "Andromeda_App",
    "SOLAR": "Solar_App", "FIRE": "Fire_App", "LUNAR": "Lunar_App",
    "GALAXY": "Galaxy_App", "OLYMPUS": "Olympus_App", "SPEED": "Speed_App",
    "SEVEN": "Seven_App", "SKY": "Sky_Alternative_App", "HADES": "Hades_App",
    "VÊNUS": "Venus_App", "URANO": "Urano_App", "K9": "K9_Play",
    "CINEMAX": "Cinemax_App", "GREEN": "Green_TV", "GTA": "GTA_Player"
}

def safe_print(msg):
    """Garante que prints não se misturem no console"""
    with lock_print:
        print(msg)

def limpar_nome_arquivo(nome):
    try:
        nome_ascii = nome.encode('ascii', 'ignore').decode('ascii')
    except:
        nome_ascii = "Nome_Desconhecido"
    return re.sub(r'[<>:"/\\|?*]', '', nome_ascii).strip().replace(" ", "_")

def registrar_erro_log(nome, url, erro):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    msg = f"[{timestamp}] {nome} | {erro}\nLink: {url}\n{'-'*30}\n"
    with lock_arquivo:
        try:
            with open(ARQUIVO_LOG_ERROS, 'a', encoding='utf-8') as f:
                f.write(msg)
        except: pass

def baixar_json_blindado(url, caminho_salvar):
    session = cffi_requests.Session()
    # 1. TENTATIVA POST
    try:
        resp = session.post(url, impersonate="chrome120", timeout=20)
        if resp.status_code >= 400:
             raise Exception(f"POST falhou com {resp.status_code}")
        
        # Escrita no arquivo não precisa de lock global aqui pois cada thread escreve em um arquivo diferente (JSON único)
        with open(caminho_salvar, 'wb') as f:
            f.write(resp.content)
        return True, "OK (via POST)"

    except Exception:
        # 2. TENTATIVA GET (FALLBACK)
        try:
            resp = session.get(url, impersonate="chrome120", timeout=20)
            if resp.status_code == 200:
                with open(caminho_salvar, 'wb') as f:
                    f.write(resp.content)
                return True, "OK (via GET Fallback)"
            else:
                return False, f"Erro Final: HTTP {resp.status_code}"
        except Exception as e_get:
            return False, f"Falha total: {str(e_get)}"

def extrair_parcerias_e_downloads(texto_resposta, nome_exibicao):
    try:
        linhas = texto_resposta.split('\n')
        urls = re.findall(r'(https?://[^\s<>"]+)', texto_resposta)
        apks = []
        for url in urls:
            url_lower = url.lower()
            if any(ext in url_lower for ext in ['.apk', 'aftv.news', 'dl.ntdev', 'mediafire']):
                 if url not in apks: apks.append(url)
        
        # Bloco de escrita APKs (Protegido)
        if apks:
            with lock_arquivo:
                with open(ARQUIVO_LINKS_APKS, 'a', encoding='utf-8') as f:
                    f.write(f"\n--- {nome_exibicao} ---\n")
                    for l in apks: f.write(f"{l}\n")

        # Bloco de processamento de linhas
        buffer_parcerias = {} # Buffer local para reduzir I/O dentro do lock
        
        for linha in linhas:
            l = linha.strip()
            if not l or len(l) > 300: continue
            
            app_detectado = None
            for k, v in APPS_PARCERIA.items():
                if k in l.upper():
                    app_detectado = v
                    break
            
            if app_detectado and any(x in l.upper() for x in ["CÓDIGO", "CODIGO", "USUÁRIO", "USER", "SENHA", "PASS", "PIN", "DNS", "URL"]):
                if app_detectado not in buffer_parcerias:
                    buffer_parcerias[app_detectado] = []
                buffer_parcerias[app_detectado].append(f"[{nome_exibicao}] {l}\n")
        
        # Escrita em lote das parcerias (Protegido)
        if buffer_parcerias:
            with lock_arquivo:
                for app_nome, conteudos in buffer_parcerias.items():
                    with open(os.path.join(PASTA_PARCERIAS, f"{app_nome}.txt"), 'a', encoding='utf-8') as f:
                        f.writelines(conteudos)

    except Exception as e:
        safe_print(f"Erro parser {nome_exibicao}: {e}")

def verificar_validade_pelo_json(caminho_arquivo):
    if not os.path.exists(caminho_arquivo):
        return False, "Arquivo inexistente"

    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            dados = json.load(f)
        
        expires_at_str = dados.get("expiresAt")
        if not expires_at_str: return False, "Sem campo expiresAt"

        try:
            data_vencimento = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try: data_vencimento = datetime.strptime(expires_at_str, "%Y-%m-%dT%H:%M:%S")
            except: return False, "Formato data inválido"

        if (data_vencimento - datetime.now()).total_seconds() > 60: 
            return True, data_vencimento.strftime("%d/%m/%Y %H:%M:%S")
        else:
            return False, "Vencido"
    except:
        return False, "Erro Leitura/JSON"

def processar_fonte(item):
    """Função executada por cada thread"""
    nome = item.get('nome')
    url = item.get('api_url')
    
    if not url: return

    nome_arq = f"{limpar_nome_arquivo(nome)}.json"
    caminho_json = os.path.join(PASTA_JSON_RAW, nome_arq)

    safe_print(f"📡 Iniciando: {nome}")

    esta_valido, msg_validade = verificar_validade_pelo_json(caminho_json)
    sucesso_leitura = False
    
    if esta_valido:
        safe_print(f"   ⏳ {nome} -> Cache válido! ({msg_validade})")
        with lock_stats: stats["cacheados"] += 1
        sucesso_leitura = True
    else:
        msg_status = "VENCIDO" if msg_validade == "Vencido" else "NOVO/INVÁLIDO"
        safe_print(f"   ⬇️ {nome} -> Baixando ({msg_status})...")
        
        status, msg = baixar_json_blindado(url, caminho_json)
        
        if status:
            safe_print(f"   ✅ {nome} -> Atualizado!")
            with lock_stats: stats["atualizados"] += 1
            sucesso_leitura = True
        else:
            safe_print(f"   ❌ {nome} -> Falha: {msg}")
            registrar_erro_log(nome, url, msg)
            with lock_stats: stats["erros"] += 1

    if sucesso_leitura and os.path.exists(caminho_json):
        try:
            with open(caminho_json, 'r', encoding='utf-8', errors='ignore') as f:
                conteudo = f.read()
            extrair_parcerias_e_downloads(conteudo, nome)
        except Exception as e:
            safe_print(f"   ⚠️ {nome} -> Erro processar JSON: {e}")

def main():
    # Criação de pastas
    for p in [PASTA_JSON_RAW, PASTA_PARCERIAS, PASTA_TXTS]:
        os.makedirs(p, exist_ok=True)

    # Limpeza inicial (Logs e Parcerias anteriores)
    if os.path.exists(ARQUIVO_LOG_ERROS):
        try: os.remove(ARQUIVO_LOG_ERROS)
        except: pass
    
    for f in os.listdir(PASTA_PARCERIAS):
        try: os.remove(os.path.join(PASTA_PARCERIAS, f))
        except: pass

    if not os.path.exists(ARQUIVO_FONTES):
        print(f"❌ '{ARQUIVO_FONTES}' não encontrado.")
        return

    with open(ARQUIVO_FONTES, 'r', encoding='utf-8') as f:
        fontes = json.load(f)

    print(f"🚀 MINERADOR V15 (MULTITHREAD) | Fontes: {len(fontes)} | Threads: {MAX_WORKERS}")
    print("-" * 50)
    
    start_time = time.time()

    # --- INÍCIO DO MULTITHREADING ---
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(processar_fonte, item) for item in fontes]
        
        # Aguarda todos terminarem (opcional, o 'with' já faz isso, mas aqui permite pegar exceptions se precisar)
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                safe_print(f"❌ Erro fatal em thread: {e}")

    tempo_total = time.time() - start_time
    
    print("-" * 50)
    print(f"✅ FIM DA MINERAÇÃO em {tempo_total:.2f} segundos.")
    print(f"🆕 Atualizados: {stats['atualizados']}")
    print(f"💾 Em Cache:    {stats['cacheados']}")
    print(f"❌ Falhas:      {stats['erros']}")
    print(f"📂 Pasta '{PASTA_TXTS}' atualizada.")

if __name__ == "__main__":
    main()