import json
import requests
import os
import re
import queue
import sys
import time
import msvcrt
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES ---
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_DESTINO = "Listas-Downloaded"
ARQUIVO_ERROS = "erros_download.txt"
MAX_SIMULTANEOS = 5  # Slots de download
CACHE_VALIDADE_SEGUNDOS = 14400 # 4 Horas

# Variável de controle
PARAR_EXECUCAO = False

HEADERS_FAKE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Connection": "keep-alive"
}

def checar_tecla_z():
    global PARAR_EXECUCAO
    if msvcrt.kbhit():
        tecla = msvcrt.getch().decode('utf-8').lower()
        if tecla == 'z':
            PARAR_EXECUCAO = True

def arquivo_eh_valido_e_recente(caminho):
    """
    Retorna True se o arquivo existe, tem tamanho decente (>1KB) 
    E foi modificado a menos de 4 horas.
    """
    if not os.path.exists(caminho): return False
    if os.path.getsize(caminho) < 1000: return False # Muito pequeno, deve ser erro
    
    timestamp_mod = os.path.getmtime(caminho)
    idade = time.time() - timestamp_mod
    
    return idade < CACHE_VALIDADE_SEGUNDOS

def limpar_url_suja(url):
    try: url = url.encode().decode('unicode_escape')
    except: pass
    chars = ['\\', '\n', '\r', '"', "'", '<', '>', ' ', '\t']
    for c in chars: 
        if c in url: url = url.split(c)[0]
    return url.replace('%5Cn', '').replace('%5C', '').strip()

def extrair_m3u_do_texto(texto):
    urls = re.findall(r'(https?://[^"\'\s\\]+)', texto)
    candidatos = []
    for url in urls:
        u = url.lower()
        if ('get.php' in u and 'username=' in u) or \
           ('.m3u' in u and 'aftv' not in u and 'e.jhysa' not in u) or \
           ('output=mpegts' in u):
            clean = limpar_url_suja(url)
            if clean.startswith("http") and len(clean) > 15: candidatos.append(clean)
    return candidatos[0] if candidatos else None

def baixar_arquivo_com_progresso(url, caminho_saida, nome_exibicao, posicao_barra):
    try:
        resp = requests.get(url, headers=HEADERS_FAKE, stream=True, timeout=(10, 60), verify=False)
        resp.raise_for_status()
        
        total_size = int(resp.headers.get('content-length', 0))
        if total_size > 0 and total_size < 150: return False, "Arquivo suspeito"

        # Barra de progresso do slot
        desc = f"Slot {posicao_barra} | {nome_exibicao[:10]}..."
        
        with tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, 
                  desc=desc, position=posicao_barra, leave=False, ncols=100) as bar:
            
            with open(caminho_saida, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=32768):
                    if PARAR_EXECUCAO: break
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
        
        if PARAR_EXECUCAO:
            if os.path.exists(caminho_saida): os.remove(caminho_saida)
            return False, "Interrompido"

        if os.path.getsize(caminho_saida) < 100: return False, "Vazio"

        return True, "OK"
    except Exception as e:
        return False, str(e)

def worker(arquivo_json, fila_posicoes):
    global PARAR_EXECUCAO
    if PARAR_EXECUCAO: return "PARADO", None, None

    nome_base = os.path.splitext(arquivo_json)[0]
    caminho_json = os.path.join(PASTA_JSON_RAW, arquivo_json)
    caminho_m3u = os.path.join(PASTA_DESTINO, f"{nome_base}.m3u")
    
    # 1. Verifica Cache (Regra 4h e Tamanho)
    if arquivo_eh_valido_e_recente(caminho_m3u):
        return "PULADO", nome_base, "Cache válido (<4h)"

    posicao = fila_posicoes.get()
    
    try:
        checar_tecla_z()
        if PARAR_EXECUCAO: return "PARADO", None, None

        with open(caminho_json, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        link_m3u = extrair_m3u_do_texto(json.dumps(dados))

        if link_m3u:
            sucesso, msg = baixar_arquivo_com_progresso(link_m3u, caminho_m3u, nome_base, posicao)
            if sucesso: 
                return "SUCESSO", nome_base, link_m3u
            else:
                return "ERRO", nome_base, f"{msg} | Link: {link_m3u}"
        else:
            if any(x in nome_base.upper() for x in ["P2P", "APP", "PARCEIRO"]):
                return "IGNORADO", nome_base, "App/P2P"
            else:
                return "ERRO", nome_base, "Link não encontrado"

    except Exception as e:
        return "ERRO", nome_base, str(e)
    
    finally:
        fila_posicoes.put(posicao)

def main():
    requests.packages.urllib3.disable_warnings()
    if not os.path.exists(PASTA_DESTINO): os.makedirs(PASTA_DESTINO)
    
    # Não apagamos o arquivo de erros antigo para manter histórico se quiser
    # Se preferir apagar sempre que roda, descomente a linha abaixo:
    # if os.path.exists(ARQUIVO_ERROS): os.remove(ARQUIVO_ERROS)

    if not os.path.exists(PASTA_JSON_RAW):
        print("❌ Pasta de dados não encontrada.")
        return

    arquivos = [f for f in os.listdir(PASTA_JSON_RAW) if f.endswith('.json')]
    
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print(f"🚀 DOWNLOADER DASHBOARD V5.1 (Com Logs Timestamp)")
    print(f"📂 Arquivos: {len(arquivos)} | ⚡ Threads: {MAX_SIMULTANEOS}")
    print("⌨️  Pressione 'Z' para encerrar.\n")

    fila_posicoes = queue.Queue()
    for i in range(1, MAX_SIMULTANEOS + 1): fila_posicoes.put(i)

    stats = {'SUCESSO': 0, 'ERRO': 0, 'IGNORADO': 0, 'PULADO': 0, 'PARADO': 0}

    with ThreadPoolExecutor(max_workers=MAX_SIMULTANEOS) as executor:
        futures = [executor.submit(worker, arq, fila_posicoes) for arq in arquivos]
        
        with tqdm(total=len(arquivos), unit="arq", position=0, leave=True, 
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}] {postfix}") as pbar:
            
            pbar.set_postfix_str("Iniciando...")
            
            for f in as_completed(futures):
                status, nome, info = f.result()
                
                if status:
                    stats[status] += 1
                    
                    if status == "ERRO":
                        # --- GERA TIMESTAMP ---
                        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        with open(ARQUIVO_ERROS, 'a', encoding='utf-8') as log:
                            # Formato: [Data] Nome | Erro | Link
                            log.write(f"[{agora}] {nome} | {info}\n")

                resumo = f"✅{stats['SUCESSO']} ⏭️{stats['PULADO']} ℹ️{stats['IGNORADO']} ❌{stats['ERRO']}"
                if PARAR_EXECUCAO: resumo += " 🛑 PARANDO..."
                
                pbar.set_postfix_str(resumo)
                pbar.update(1)

                if PARAR_EXECUCAO:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

    print("\n" * (MAX_SIMULTANEOS + 1))
    print("="*50)
    
    if PARAR_EXECUCAO:
        print("🛑 Execução interrompida pelo usuário.")
    else:
        print("🏁 CICLO CONCLUÍDO!")
    
    print(f"✅ Baixados: {stats['SUCESSO']}")
    print(f"⏭️  Cache (<4h): {stats['PULADO']}")
    print(f"ℹ️  Apps/P2P: {stats['IGNORADO']}")
    print(f"❌ Falhas:   {stats['ERRO']}")
    
    if stats['ERRO'] > 0:
        print(f"📄 Erros detalhados em: '{ARQUIVO_ERROS}'")

if __name__ == "__main__":
    main()