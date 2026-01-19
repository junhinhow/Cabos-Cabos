import json
import os
import re
import queue
import sys
import time
import msvcrt
import shutil
import warnings
import glob
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- IMPORTAÇÕES (Motor Novo) ---
try:
    from tqdm import tqdm
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("❌ ERRO: Bibliotecas faltando.")
    print("Execute no terminal: pip install tqdm curl_cffi --user")
    sys.exit()

warnings.filterwarnings("ignore")

# --- CONFIGURAÇÕES ---
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_DESTINO = "Listas-Downloaded"
PASTA_PARCERIAS = "Parcerias"
PASTA_DOWNLOADS = "Downloads"
ARQUIVO_ERROS = "erros_download.txt"
ARQUIVO_FALHAS_JSON = "falhas_download.json"

MAX_SIMULTANEOS = 3      # Reduzi para 3 para aumentar estabilidade
CACHE_VALIDADE = 14400   # 4 Horas
TIMEOUT_CONEXAO = 15     # Aumentei um pouco para evitar falso-positivo em net lenta

PARAR_EXECUCAO = False

APPS_PARCERIA = {
    "Assist": "Assist_Plus_Play_Sim", "Play Sim": "Assist_Plus_Play_Sim",
    "Lazer": "Lazer_Play", "Vizzion": "Vizzion", "Unitv": "UniTV",
    "Xcloud": "XCloud_TV", "P2P": "Codigos_P2P_Geral", "Smarters": "IPTV_Smarters_DNS",
    "XCIPTV": "XCIPTV_Dados"
}

def limpar_lixo_tmp():
    """Remove arquivos .tmp deixados por execuções anteriores"""
    files = glob.glob(os.path.join(PASTA_DESTINO, "*.tmp"))
    if files:
        try:
            for f in files:
                try: os.remove(f)
                except: pass
        except: pass

def checar_tecla_z():
    global PARAR_EXECUCAO
    if msvcrt.kbhit():
        if msvcrt.getch().decode('utf-8').lower() == 'z':
            PARAR_EXECUCAO = True

def limpar_url(url):
    if not url: return None
    try: url = url.encode().decode('unicode_escape')
    except: pass

    for lixo in ['\\n', '\n', '\r', '\t', ' ']:
        url = url.replace(lixo, '')

    match = re.search(r'(https?://[a-zA-Z0-9\.\-_:/?=&%@]+)', url)
    if match:
        url_limpa = match.group(1)
        if 'output=mpegts' in url_limpa:
            return url_limpa.split('output=mpegts')[0] + 'output=mpegts'
        if '.m3u8' in url_limpa:
            return url_limpa.split('.m3u8')[0] + '.m3u8'
        if '.m3u' in url_limpa:
            return url_limpa.split('.m3u')[0] + '.m3u'
        return url_limpa
    return None

def salvar_falhas_json(novas_falhas):
    if not novas_falhas: return
    falhas_existentes = []
    if os.path.exists(ARQUIVO_FALHAS_JSON):
        try:
            with open(ARQUIVO_FALHAS_JSON, 'r', encoding='utf-8') as f:
                falhas_existentes = json.load(f)
        except: falhas_existentes = []

    mapa_falhas = {item['url']: item for item in falhas_existentes}
    for falha in novas_falhas: mapa_falhas[falha['url']] = falha
    
    lista_final = list(mapa_falhas.values())
    try:
        with open(ARQUIVO_FALHAS_JSON, 'w', encoding='utf-8') as f:
            json.dump(lista_final, f, indent=4, ensure_ascii=False)
    except: pass

def salvar_linha_unica(caminho_arquivo, nova_linha):
    try:
        with open(caminho_arquivo, 'a', encoding='utf-8') as f:
            f.write(f"{nova_linha.strip()}\n")
    except: pass

def extrair_m3u_do_json(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            conteudo = json.load(f)
        
        url_encontrada = None
        if isinstance(conteudo, dict):
            chaves = ['link_m3u', 'url', 'link', 'endereco', 'source', 'm3u']
            for k in chaves:
                if k in conteudo:
                    limpo = limpar_url(conteudo[k])
                    if limpo: 
                        url_encontrada = limpo
                        break
            texto = json.dumps(conteudo)
        elif isinstance(conteudo, list):
            if conteudo and isinstance(conteudo[0], str) and conteudo[0].startswith('http'):
                url_encontrada = limpar_url(conteudo[0])
            texto = json.dumps(conteudo)
        else:
            return None, conteudo

        if not url_encontrada:
            urls = re.findall(r'(https?://[^"\'\s\\]+)', texto)
            for url in urls:
                u_lower = url.lower()
                if ('.m3u' in u_lower or 'get.php' in u_lower or 'mpegts' in u_lower):
                    if 'aftv.news' not in u_lower:
                        limpo = limpar_url(url)
                        if limpo:
                            url_encontrada = limpo
                            break
        return url_encontrada, conteudo
    except:
        return None, None

def extrair_infos_extras(dados_json, nome_base):
    if not dados_json: return
    texto = json.dumps(dados_json)
    
    urls = re.findall(r'(https?://[^"\'\s]+)', texto)
    apks = [u for u in urls if any(x in u.lower() for x in ['.apk', 'aftv', 'downloader'])]
    if apks:
        caminho_apk = os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt")
        for apk in set(apks): 
            salvar_linha_unica(caminho_apk, f"[{nome_base}] {apk}")

    linhas = texto.split('\\n') 
    if len(linhas) < 2: linhas = texto.split('\n')
    for linha in linhas:
        l = linha.strip()
        if len(l) > 300: continue
        for key, nome_arquivo in APPS_PARCERIA.items():
            if key.upper() in l.upper():
                if any(x in l.upper() for x in ['USER', 'PASS', 'SENHA', 'CODIGO', 'LOGIN']):
                    caminho_txt = os.path.join(PASTA_PARCERIAS, f"{nome_arquivo}.txt")
                    salvar_linha_unica(caminho_txt, f"[{nome_base}] {l}")

def gerenciar_cache_inteligente(nome_base):
    padrao = os.path.join(PASTA_DESTINO, f"{glob.escape(nome_base)}_[*.m3u")
    arquivos_existentes = glob.glob(padrao)
    
    arquivo_antigo = None
    cache_valido = False

    if arquivos_existentes:
        arquivo_antigo = max(arquivos_existentes, key=os.path.getmtime)
        try:
            if os.path.getsize(arquivo_antigo) > 2048:
                idade = time.time() - os.path.getmtime(arquivo_antigo)
                if idade < CACHE_VALIDADE:
                    cache_valido = True
        except: pass
            
    return cache_valido, arquivo_antigo

def baixar_arquivo(url, caminho_destino, desc_barra, posicao):
    caminho_temp = caminho_destino + ".tmp"
    
    if os.path.exists(caminho_temp): 
        try: os.remove(caminho_temp)
        except: pass

    # --- CRIAÇÃO DE NAVEGADOR LOCAL (ISOLADO POR THREAD) ---
    # Isso impede que uma thread quebre a outra
    local_session = cffi_requests.Session()
    
    try:
        response = local_session.get(
            url, 
            impersonate="chrome120", 
            stream=True, 
            timeout=TIMEOUT_CONEXAO, 
            allow_redirects=True
        )
        
        if response.status_code != 200:
            local_session.close()
            return False, f"Erro HTTP {response.status_code}"

        total_size = int(response.headers.get('content-length', 0))
        
        if total_size > 50 * 1024 * 1024:
            local_session.close()
            return False, "Arquivo muito grande (Provável Vídeo)"

        tamanho_baixado = 0

        try:
            iterator = response.iter_content(chunk_size=512)
            primeiro_chunk = next(iterator)
        except StopIteration:
            local_session.close()
            return False, "Arquivo vazio recebido"
        except Exception as e:
            local_session.close()
            if "time" in str(e).lower() or "out" in str(e).lower():
                return False, "TIMEOUT: Servidor não enviou dados"
            return False, f"Erro Conexão Inicial: {str(e)[:50]}"

        if b"<html" in primeiro_chunk.lower() or b"<!doctype" in primeiro_chunk.lower():
             local_session.close()
             return False, "Bloqueio (HTML Detectado)"
        
        if b"{" in primeiro_chunk and b"error" in primeiro_chunk.lower():
             local_session.close()
             return False, "Erro API (JSON Detectado)"

        with tqdm(total=total_size, unit='B', unit_scale=True, desc=desc_barra, 
                  position=posicao, leave=False, ncols=90, 
                  bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}") as bar:
            
            with open(caminho_temp, 'wb') as f:
                f.write(primeiro_chunk)
                bar.update(len(primeiro_chunk))
                tamanho_baixado += len(primeiro_chunk)
                
                for chunk in response.iter_content(chunk_size=64*1024):
                    if PARAR_EXECUCAO: break
                    if chunk:
                        f.write(chunk)
                        tam_chunk = len(chunk)
                        bar.update(tam_chunk)
                        tamanho_baixado += tam_chunk

                        if tamanho_baixado > 20 * 1024 * 1024:
                            local_session.close()
                            return False, "Abortado: Excedeu 20MB"

        local_session.close()

        if PARAR_EXECUCAO:
            return False, "Interrompido pelo usuário"

        if os.path.getsize(caminho_temp) < 100:
            return False, "Arquivo muito pequeno"

        if os.path.exists(caminho_destino): 
            try: os.remove(caminho_destino)
            except: pass
            
        os.rename(caminho_temp, caminho_destino)
        return True, "OK"

    except Exception as e:
        # Fecha sessão em caso de erro
        try: local_session.close()
        except: pass
        
        msg_erro = str(e).lower()
        if "could not resolve host" in msg_erro:
             return False, "DNS ERROR: Servidor não existe"
        if "time" in msg_erro or "out" in msg_erro or "deadline" in msg_erro:
            return False, "TIMEOUT: Conexão lenta/travada"
        return False, f"Erro: {str(e)[:60]}"
    
    finally:
        if os.path.exists(caminho_temp):
            try: os.remove(caminho_temp)
            except: pass
                    
def worker(nome_arquivo_json, fila_slots):
    global PARAR_EXECUCAO
    if PARAR_EXECUCAO: return "PARADO", None, None

    slot = fila_slots.get()
    nome_base = nome_arquivo_json.replace('.json', '')
    caminho_json = os.path.join(PASTA_JSON_RAW, nome_arquivo_json)
    
    try:
        checar_tecla_z()
        # Tratamento de erro na leitura do JSON para não travar
        try:
            url_m3u, dados_brutos = extrair_m3u_do_json(caminho_json)
            extrair_infos_extras(dados_brutos, nome_base)
        except Exception:
            fila_slots.put(slot)
            return "ERRO", nome_base, ("Erro Leitura JSON", "N/A")

        cache_valido, arquivo_antigo = gerenciar_cache_inteligente(nome_base)
        
        if cache_valido:
            fila_slots.put(slot)
            nome_exibicao = os.path.basename(arquivo_antigo)
            return "CACHE", nome_exibicao, "Válido"

        if not url_m3u:
            fila_slots.put(slot)
            return "IGNORADO", nome_base, "Link não encontrado"

        timestamp = datetime.now().strftime("[%d-%m-%Y_%Hh%M]")
        novo_nome_arquivo = f"{nome_base}_{timestamp}.m3u"
        caminho_final = os.path.join(PASTA_DESTINO, novo_nome_arquivo)

        desc = f"Slot {slot} | {nome_base[:15]}"
        sucesso, msg = baixar_arquivo(url_m3u, caminho_final, desc, slot)
        
        fila_slots.put(slot)

        if sucesso:
            if arquivo_antigo and os.path.exists(arquivo_antigo):
                try: os.remove(arquivo_antigo)
                except: pass
            return "SUCESSO", novo_nome_arquivo, url_m3u
        else:
            return "ERRO", nome_base, (msg, url_m3u)

    except Exception as e:
        fila_slots.put(slot)
        # Catch-all para impedir que o Worker morra silenciosamente
        return "ERRO", nome_base, (f"CRASH WORKER: {str(e)}", "url_desconhecida")

def main():
    limpar_lixo_tmp()

    for p in [PASTA_DESTINO, PASTA_PARCERIAS, PASTA_DOWNLOADS]:
        os.makedirs(p, exist_ok=True)
    
    if not os.path.exists(PASTA_JSON_RAW):
        print("❌ Pasta Dados-Brutos não encontrada.")
        return

    arquivos = [f for f in os.listdir(PASTA_JSON_RAW) if f.endswith('.json')]
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"============================================================")
    print(f"🚀 SIGMA DOWNLOADER V17 (STABLE-ISOLATED) | Arq: {len(arquivos)}")
    print(f"📁 Log de Erros: {os.path.abspath(ARQUIVO_ERROS)}")
    print(f"============================================================\n")

    fila_slots = queue.Queue()
    for i in range(1, MAX_SIMULTANEOS + 1): fila_slots.put(i)

    stats = defaultdict(int)
    lista_falhas_coletadas = []

    with ThreadPoolExecutor(max_workers=MAX_SIMULTANEOS) as executor:
        futures = [executor.submit(worker, arq, fila_slots) for arq in arquivos]
        
        with tqdm(total=len(arquivos), unit="arq", position=0, leave=True, 
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}] {postfix}") as pbar:
            
            for f in as_completed(futures):
                try:
                    status, nome, info = f.result()
                except Exception as e:
                    # Se o worker morrer mesmo com proteção, pegamos aqui
                    status, nome, info = "ERRO", "DESCONHECIDO", (f"FATAL ERROR: {e}", "N/A")

                stats[status] += 1
                agora = datetime.now().strftime("%H:%M:%S")
                
                if status == "ERRO":
                    msg_erro, url_erro = info 
                    
                    tqdm.write(f"[{agora}] ❌ {nome} -> {msg_erro}")
                    
                    try:
                        with open(ARQUIVO_ERROS, 'a', encoding='utf-8') as log:
                            log.write(f"[{agora}] {nome} | {msg_erro} | URL: {url_erro}\n")
                            log.flush()
                            os.fsync(log.fileno())
                    except: pass

                    lista_falhas_coletadas.append({
                        "nome": nome,
                        "url": url_erro,
                        "erro": msg_erro,
                        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                
                pbar.set_postfix_str(f"✅{stats['SUCESSO']} ⏭️{stats['CACHE']} ❌{stats['ERRO']}")
                pbar.update(1)
                
                if PARAR_EXECUCAO:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

    if lista_falhas_coletadas:
        salvar_falhas_json(lista_falhas_coletadas)
        
    limpar_lixo_tmp()
    print("\n" * (MAX_SIMULTANEOS + 1))
    print(f"🏁 Concluído!")

if __name__ == "__main__":
    main()