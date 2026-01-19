import json
import os
import re
import queue
import sys
import time
import msvcrt
import shutil
import warnings
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- IMPORTAÇÕES OBRIGATÓRIAS ---
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

# Ignora avisos de SSL inseguro (comuns em IPTV)
warnings.filterwarnings("ignore")

# --- CONFIGURAÇÕES ---
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_DESTINO = "Listas-Downloaded"
PASTA_PARCERIAS = "Parcerias"
PASTA_DOWNLOADS = "Downloads"
ARQUIVO_ERROS = "erros_download.txt"
ARQUIVO_ATUALIZACOES = "Atualizações.txt"

MAX_SIMULTANEOS = 4      # Reduzi para 4 para evitar bloqueio por "flood"
CACHE_VALIDADE = 14400   # 4 Horas
TIMEOUT_PADRAO = 60      # Aumentado para servidores lentos

# Controle Global
PARAR_EXECUCAO = False

# --- MOTOR DE CONEXÃO (O TANQUE) ---
def criar_sessao_blindada():
    """Cria uma sessão que simula um navegador real e insiste na conexão"""
    # 1. Configura o CloudScraper (Anti-Bot)
    sessao = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False,
            'desktop': True,
        }
    )
    
    # 2. Configura Retentativas (Retry) para quedas de conexão
    retry_strategy = Retry(
        total=3,  # Tenta 3 vezes
        backoff_factor=1, # Espera 1s, 2s, 4s...
        status_forcelist=[500, 502, 503, 504, 520, 521, 522], # Erros de servidor que valem a pena tentar de novo
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    sessao.mount("https://", adapter)
    sessao.mount("http://", adapter)
    
    return sessao

# Instância global do navegador falso
Navegador = criar_sessao_blindada()

# Dicionário de Parcerias
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

def arquivo_cache_valido(caminho):
    """Verifica se o arquivo existe, é grande o suficiente e é recente"""
    if not os.path.exists(caminho): return False
    try:
        if os.path.getsize(caminho) < 5000: # Aumentei régua: menos de 5KB é suspeito para lista completa
            return False
        idade = time.time() - os.path.getmtime(caminho)
        return idade < CACHE_VALIDADE
    except:
        return False

def limpar_url(url):
    """Limpa URLs sujas vindas de JSONs mal formatados"""
    if not url: return None
    # Remove caracteres de escape comuns em JSON raw
    url = url.replace('\\/', '/').replace('%5C', '').strip()
    match = re.search(r'(https?://[^\s"\'<>]+)', url)
    return match.group(1) if match else None

def extrair_m3u_do_json(caminho_arquivo):
    """Lê o JSON e tenta achar o link M3U de qualquer jeito"""
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            conteudo = json.load(f)
        
        # 1. Busca direta se for dicionário
        if isinstance(conteudo, dict):
            # Lista de chaves possíveis
            chaves = ['link_m3u', 'url', 'link', 'endereco', 'source', 'm3u']
            for k in chaves:
                if k in conteudo:
                    limpo = limpar_url(conteudo[k])
                    if limpo: return limpo, conteudo
            
            # Se não achou, converte para texto e busca regex
            texto = json.dumps(conteudo)
        
        # 2. Busca se for lista
        elif isinstance(conteudo, list):
            # Tenta pegar o primeiro item se for string
            if conteudo and isinstance(conteudo[0], str) and conteudo[0].startswith('http'):
                return limpar_url(conteudo[0]), conteudo
            texto = json.dumps(conteudo)
        else:
            return None, conteudo

        # 3. Busca Regex (Último recurso)
        # Procura por padrões comuns de M3U
        urls = re.findall(r'(https?://[^"\'\s]+)', texto)
        for url in urls:
            u_lower = url.lower()
            if ('.m3u' in u_lower or 'get.php' in u_lower or 'mpegts' in u_lower):
                if 'aftv.news' not in u_lower: # Ignora links de apps
                    return limpar_url(url), conteudo
                    
        return None, conteudo
    except Exception:
        return None, None

def extrair_infos_extras(dados_json, nome_base):
    """Extrai APKs e Senhas para arquivos de texto"""
    if not dados_json: return
    texto = json.dumps(dados_json)
    
    # APKs
    urls = re.findall(r'(https?://[^"\'\s]+)', texto)
    apks = [u for u in urls if any(x in u.lower() for x in ['.apk', 'aftv', 'downloader'])]
    if apks:
        with open(os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt"), 'a', encoding='utf-8') as f:
            f.write(f"\n--- {nome_base} ---\n")
            for apk in set(apks): f.write(f"{apk}\n")

    # Parcerias (Senhas)
    linhas = texto.split('\\n') # Tenta quebrar por nova linha escapada
    if len(linhas) < 2: linhas = texto.split('\n')
    
    for linha in linhas:
        l = linha.strip()
        if len(l) > 300: continue # Ignora lixo
        
        for key, nome_arquivo in APPS_PARCERIA.items():
            if key.upper() in l.upper():
                if any(x in l.upper() for x in ['USER', 'PASS', 'SENHA', 'CODIGO', 'LOGIN']):
                    with open(os.path.join(PASTA_PARCERIAS, f"{nome_arquivo}.txt"), 'a', encoding='utf-8') as f:
                        f.write(f"[{nome_base}] {l}\n")

def baixar_arquivo(url, caminho_destino, desc_barra, posicao):
    """Baixa o arquivo com barra de progresso e validação rigorosa"""
    caminho_temp = caminho_destino + ".tmp"
    if os.path.exists(caminho_temp): os.remove(caminho_temp)

    try:
        # stream=True é essencial para arquivos grandes
        with Navegador.get(url, stream=True, timeout=TIMEOUT_PADRAO) as resposta:
            resposta.raise_for_status() # Lança erro se for 404, 500, etc
            
            # --- VALIDAÇÃO ANTI-BLOQUEIO ---
            # Lê os primeiros bytes para ver se é HTML (bloqueio) ou Texto (M3U)
            primeiro_pedaco = next(resposta.iter_content(chunk_size=512), b"")
            
            if b"<html" in primeiro_pedaco.lower() or b"<!doctype" in primeiro_pedaco.lower():
                return False, "Bloqueio Detectado (HTML)"
            
            # Pega tamanho total
            tamanho_total = int(resposta.headers.get('content-length', 0))
            
            # Configura barra de progresso
            with tqdm(total=tamanho_total, unit='B', unit_scale=True, desc=desc_barra, 
                      position=posicao, leave=False, ncols=90, 
                      bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}") as bar:
                
                with open(caminho_temp, 'wb') as f:
                    f.write(primeiro_pedaco) # Grava o pedaço de teste
                    bar.update(len(primeiro_pedaco))
                    
                    for pedaco in resposta.iter_content(chunk_size=8192):
                        if PARAR_EXECUCAO: break
                        if pedaco:
                            f.write(pedaco)
                            bar.update(len(pedaco))
        
        if PARAR_EXECUCAO:
            if os.path.exists(caminho_temp): os.remove(caminho_temp)
            return False, "Interrompido"

        # --- VALIDAÇÃO FINAL ---
        tamanho_final = os.path.getsize(caminho_temp)
        if tamanho_final < 2048: # Menor que 2KB
            os.remove(caminho_temp)
            return False, f"Arquivo suspeito ({tamanho_final} bytes)"

        # Sucesso!
        if os.path.exists(caminho_destino): os.remove(caminho_destino)
        os.rename(caminho_temp, caminho_destino)
        return True, "OK"

    except requests.exceptions.HTTPError as e:
        return False, f"Erro HTTP {e.response.status_code}"
    except Exception as e:
        return False, f"Erro: {str(e)[:40]}"

def worker(nome_arquivo_json, fila_slots):
    global PARAR_EXECUCAO
    if PARAR_EXECUCAO: return "PARADO", None, None

    slot = fila_slots.get()
    nome_base = nome_arquivo_json.replace('.json', '')
    caminho_json = os.path.join(PASTA_JSON_RAW, nome_arquivo_json)
    caminho_final = os.path.join(PASTA_DESTINO, f"{nome_base}.m3u")

    try:
        checar_tecla_z()
        
        # 1. Verifica Cache
        if arquivo_cache_valido(caminho_final):
            fila_slots.put(slot)
            return "CACHE", nome_base, "Válido"

        # 2. Extrai Link
        url_m3u, dados_brutos = extrair_m3u_do_json(caminho_json)
        
        # Extrai senhas/APKs mesmo se o download falhar
        extrair_infos_extras(dados_brutos, nome_base)

        if not url_m3u:
            fila_slots.put(slot)
            return "IGNORADO", nome_base, "Link não encontrado"

        # 3. Baixa
        desc = f"Slot {slot} | {nome_base[:15]}"
        sucesso, msg = baixar_arquivo(url_m3u, caminho_final, desc, slot)
        
        fila_slots.put(slot) # Libera slot

        if sucesso:
            return "SUCESSO", nome_base, url_m3u
        else:
            return "ERRO", nome_base, msg

    except Exception as e:
        fila_slots.put(slot)
        return "ERRO", nome_base, str(e)

def main():
    # Cria estrutura
    for p in [PASTA_DESTINO, PASTA_PARCERIAS, PASTA_DOWNLOADS]:
        os.makedirs(p, exist_ok=True)
    
    if not os.path.exists(PASTA_JSON_RAW):
        print("❌ Pasta Dados-Brutos não encontrada.")
        return

    arquivos = [f for f in os.listdir(PASTA_JSON_RAW) if f.endswith('.json')]
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"============================================================")
    print(f"🚀 SIGMA DOWNLOADER V10 (TANK EDITION)")
    print(f"📂 Arquivos: {len(arquivos)} | ⚡ Slots: {MAX_SIMULTANEOS}")
    print(f"============================================================\n")

    # Gerenciador de Slots para TQDM
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
                
                if status == "ERRO":
                    # Só loga erro se NÃO for 404 (porque 404 é normal de lista morta)
                    if "404" not in info:
                        tqdm.write(f"[{agora}] ❌ {nome} -> {info}")
                    with open(ARQUIVO_ERROS, 'a', encoding='utf-8') as log:
                        log.write(f"[{agora}] {nome} | {info}\n")
                
                # Atualiza rodapé
                pbar.set_postfix_str(f"✅{stats['SUCESSO']} ⏭️{stats['CACHE']} ❌{stats['ERRO']}")
                pbar.update(1)
                
                if PARAR_EXECUCAO:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

    print("\n" * (MAX_SIMULTANEOS + 1))
    print(f"🏁 Concluído! | ✅ Baixados: {stats['SUCESSO']} | ❌ Falhas: {stats['ERRO']}")

if __name__ == "__main__":
    main()