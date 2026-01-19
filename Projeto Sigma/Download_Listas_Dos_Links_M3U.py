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

# --- IMPORTAÇÕES ---
try:
    from tqdm import tqdm
    import cloudscraper
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("❌ ERRO: Faltam bibliotecas.")
    print("Instale: pip install tqdm cloudscraper requests")
    sys.exit()

warnings.filterwarnings("ignore")

# --- CONFIGURAÇÕES ---
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_DESTINO = "Listas-Downloaded"
PASTA_PARCERIAS = "Parcerias"
PASTA_DOWNLOADS = "Downloads"
ARQUIVO_ERROS = "erros_download.txt"

MAX_SIMULTANEOS = 4      
CACHE_VALIDADE = 14400   # 4 Horas
TIMEOUT_PADRAO = 60      

PARAR_EXECUCAO = False

# --- MOTOR DE CONEXÃO ---
def criar_sessao_blindada():
    sessao = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False, 'desktop': True}
    )
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504, 520, 521, 522])
    adapter = HTTPAdapter(max_retries=retry)
    sessao.mount("https://", adapter)
    sessao.mount("http://", adapter)
    return sessao

Navegador = criar_sessao_blindada()

APPS_PARCERIA = {
    "Assist": "Assist_Plus_Play_Sim", "Play Sim": "Assist_Plus_Play_Sim",
    "Lazer": "Lazer_Play", "Vizzion": "Vizzion", "Unitv": "UniTV",
    "Xcloud": "XCloud_TV", "P2P": "Codigos_P2P_Geral", "Smarters": "IPTV_Smarters_DNS",
    "XCIPTV": "XCIPTV_Dados"
}

def checar_tecla_z():
    global PARAR_EXECUCAO
    if msvcrt.kbhit():
        if msvcrt.getch().decode('utf-8').lower() == 'z':
            PARAR_EXECUCAO = True

def limpar_url(url):
    if not url: return None
    url = url.replace('\\/', '/').replace('%5C', '').strip()
    match = re.search(r'(https?://[^\s"\'<>]+)', url)
    return match.group(1) if match else None

# --- FUNÇÃO DE ESCRITA INTELIGENTE (NOVIDADE) ---
def salvar_linha_unica(caminho_arquivo, nova_linha):
    """
    Lê o arquivo, verifica se a linha já existe.
    Se não existir, adiciona no final (Append).
    """
    linhas_existentes = set()
    
    # 1. Lê o que já tem no arquivo (se ele existir)
    if os.path.exists(caminho_arquivo):
        try:
            with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
                # Carrega tudo na memória removendo espaços extras
                linhas_existentes = set(linha.strip() for linha in f)
        except:
            pass

    # 2. Verifica se a nova linha é repetida
    linha_limpa = nova_linha.strip()
    if linha_limpa and linha_limpa not in linhas_existentes:
        try:
            with open(caminho_arquivo, 'a', encoding='utf-8') as f:
                f.write(f"{linha_limpa}\n")
        except Exception as e:
            # Em caso de erro de acesso (arquivo em uso), espera um pouco e tenta de novo
            time.sleep(0.1)
            try:
                with open(caminho_arquivo, 'a', encoding='utf-8') as f:
                    f.write(f"{linha_limpa}\n")
            except: pass

def extrair_m3u_do_json(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            conteudo = json.load(f)
        
        if isinstance(conteudo, dict):
            chaves = ['link_m3u', 'url', 'link', 'endereco', 'source', 'm3u']
            for k in chaves:
                if k in conteudo:
                    limpo = limpar_url(conteudo[k])
                    if limpo: return limpo, conteudo
            texto = json.dumps(conteudo)
        
        elif isinstance(conteudo, list):
            if conteudo and isinstance(conteudo[0], str) and conteudo[0].startswith('http'):
                return limpar_url(conteudo[0]), conteudo
            texto = json.dumps(conteudo)
        else:
            return None, conteudo

        urls = re.findall(r'(https?://[^"\'\s]+)', texto)
        for url in urls:
            u_lower = url.lower()
            if ('.m3u' in u_lower or 'get.php' in u_lower or 'mpegts' in u_lower):
                if 'aftv.news' not in u_lower:
                    return limpar_url(url), conteudo
        return None, conteudo
    except:
        return None, None

def extrair_infos_extras(dados_json, nome_base):
    if not dados_json: return
    texto = json.dumps(dados_json)
    
    # APKs
    urls = re.findall(r'(https?://[^"\'\s]+)', texto)
    apks = [u for u in urls if any(x in u.lower() for x in ['.apk', 'aftv', 'downloader'])]
    if apks:
        caminho_apk = os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt")
        cabecalho = f"--- {nome_base} ---"
        # Só escreve o cabeçalho se formos escrever algum link novo (lógica simplificada: escreve sempre)
        # Para ficar perfeito, teria que checar cada link antes.
        # Vamos usar a função inteligente para cada link.
        
        for apk in set(apks): 
            linha = f"[{nome_base}] {apk}"
            salvar_linha_unica(caminho_apk, linha)

    # Parcerias
    linhas = texto.split('\\n') 
    if len(linhas) < 2: linhas = texto.split('\n')
    
    for linha in linhas:
        l = linha.strip()
        if len(l) > 300: continue
        for key, nome_arquivo in APPS_PARCERIA.items():
            if key.upper() in l.upper():
                if any(x in l.upper() for x in ['USER', 'PASS', 'SENHA', 'CODIGO', 'LOGIN']):
                    caminho_txt = os.path.join(PASTA_PARCERIAS, f"{nome_arquivo}.txt")
                    conteudo = f"[{nome_base}] {l}"
                    salvar_linha_unica(caminho_txt, conteudo)

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
    if os.path.exists(caminho_temp): os.remove(caminho_temp)

    try:
        with Navegador.get(url, stream=True, timeout=TIMEOUT_PADRAO) as resposta:
            resposta.raise_for_status()
            
            primeiro_pedaco = next(resposta.iter_content(chunk_size=512), b"")
            if b"<html" in primeiro_pedaco.lower() or b"<!doctype" in primeiro_pedaco.lower():
                return False, "Bloqueio HTML Detectado"
            
            tamanho_total = int(resposta.headers.get('content-length', 0))
            
            with tqdm(total=tamanho_total, unit='B', unit_scale=True, desc=desc_barra, 
                      position=posicao, leave=False, ncols=90, 
                      bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}") as bar:
                
                with open(caminho_temp, 'wb') as f:
                    f.write(primeiro_pedaco)
                    bar.update(len(primeiro_pedaco))
                    for pedaco in resposta.iter_content(chunk_size=8192):
                        if PARAR_EXECUCAO: break
                        if pedaco:
                            f.write(pedaco)
                            bar.update(len(pedaco))
        
        if PARAR_EXECUCAO:
            if os.path.exists(caminho_temp): os.remove(caminho_temp)
            return False, "Interrompido"

        if os.path.getsize(caminho_temp) < 2048:
            os.remove(caminho_temp)
            return False, "Arquivo muito pequeno (Erro)"

        if os.path.exists(caminho_destino): os.remove(caminho_destino)
        os.rename(caminho_temp, caminho_destino)
        return True, "OK"

    except Exception as e:
        return False, f"Erro: {str(e)[:40]}"

def worker(nome_arquivo_json, fila_slots):
    global PARAR_EXECUCAO
    if PARAR_EXECUCAO: return "PARADO", None, None

    slot = fila_slots.get()
    nome_base = nome_arquivo_json.replace('.json', '')
    caminho_json = os.path.join(PASTA_JSON_RAW, nome_arquivo_json)
    
    try:
        checar_tecla_z()
        
        # Extrai infos PRIMEIRO (Para garantir parcerias mesmo se o download falhar ou for cache)
        url_m3u, dados_brutos = extrair_m3u_do_json(caminho_json)
        extrair_infos_extras(dados_brutos, nome_base)

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
            return "ERRO", nome_base, msg

    except Exception as e:
        fila_slots.put(slot)
        return "ERRO", nome_base, str(e)

def main():
    for p in [PASTA_DESTINO, PASTA_PARCERIAS, PASTA_DOWNLOADS]:
        os.makedirs(p, exist_ok=True)
    
    if not os.path.exists(PASTA_JSON_RAW):
        print("❌ Pasta Dados-Brutos não encontrada.")
        return

    arquivos = [f for f in os.listdir(PASTA_JSON_RAW) if f.endswith('.json')]
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"============================================================")
    print(f"🚀 SIGMA DOWNLOADER V12 (SMART APPEND) | Arq: {len(arquivos)}")
    print(f"============================================================\n")

    fila_slots = queue.Queue()
    for i in range(1, MAX_SIMULTANEOS + 1): fila_slots.put(i)

    stats = defaultdict(int)

    with ThreadPoolExecutor(max_workers=MAX_SIMULTANEOS) as executor:
        futures = [executor.submit(worker, arq, fila_slots) for arq in arquivos]
        
        with tqdm(total=len(arquivos), unit="arq", position=0, leave=True, 
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}] {postfix}") as pbar:
            
            for f in as_completed(futures):
                status, nome, info = f.result()
                stats[status] += 1
                agora = datetime.now().strftime("%H:%M:%S")
                
                if status == "ERRO" and "404" not in info:
                    tqdm.write(f"[{agora}] ❌ {nome} -> {info}")
                    with open(ARQUIVO_ERROS, 'a', encoding='utf-8') as log:
                        log.write(f"[{agora}] {nome} | {info}\n")
                
                pbar.set_postfix_str(f"✅{stats['SUCESSO']} ⏭️{stats['CACHE']} ❌{stats['ERRO']}")
                pbar.update(1)
                
                if PARAR_EXECUCAO:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

    print("\n" * (MAX_SIMULTANEOS + 1))
    print(f"🏁 Concluído! Parcerias salvas em modo incremental.")

if __name__ == "__main__":
    main()