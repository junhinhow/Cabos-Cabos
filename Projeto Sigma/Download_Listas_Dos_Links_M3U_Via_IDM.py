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
import subprocess 
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- IMPORTAÇÕES OPCIONAIS ---
try:
    from tqdm import tqdm
except ImportError:
    print("❌ ERRO: Biblioteca 'tqdm' faltando.")
    print("Execute no terminal: pip install tqdm --user")
    sys.exit()

warnings.filterwarnings("ignore")

# --- CONFIGURAÇÕES ---
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_DESTINO = "Listas-Downloaded"
PASTA_PARCERIAS = "Parcerias"
PASTA_DOWNLOADS = "Downloads"
ARQUIVO_ERROS = "erros_download.txt"
ARQUIVO_FALHAS_JSON = "falhas_download.json"

# ==============================================================================
# ✅ CAMINHO DO IDM (Seu caminho correto no disco D:)
# ==============================================================================
CAMINHO_IDM = r"D:\Program Files (x86)\Internet Download Manager\IDMan.exe"

# OBS: O limite real de velocidade é definido DENTRO do IDM (Agendador), não aqui.
# Aqui definimos quantos comandos enviamos por vez para não travar o PC.
MAX_SIMULTANEOS = 10      
CACHE_VALIDADE = 14400   
PARAR_EXECUCAO = False

APPS_PARCERIA = {
    "Assist": "Assist_Plus_Play_Sim", "Play Sim": "Assist_Plus_Play_Sim",
    "Lazer": "Lazer_Play", "Vizzion": "Vizzion", "Unitv": "UniTV",
    "Xcloud": "XCloud_TV", "P2P": "Codigos_P2P_Geral", "Smarters": "IPTV_Smarters_DNS",
    "XCIPTV": "XCIPTV_Dados"
}

def limpar_lixo_tmp():
    files = glob.glob(os.path.join(PASTA_DESTINO, "*.tmp"))
    if files:
        for f in files:
            try: os.remove(f)
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
        if 'output=mpegts' in url_limpa: return url_limpa.split('output=mpegts')[0] + 'output=mpegts'
        if '.m3u8' in url_limpa: return url_limpa.split('.m3u8')[0] + '.m3u8'
        if '.m3u' in url_limpa: return url_limpa.split('.m3u')[0] + '.m3u'
        return url_limpa
    return None

def salvar_falhas_json(novas_falhas):
    if not novas_falhas: return
    falhas_existentes = []
    if os.path.exists(ARQUIVO_FALHAS_JSON):
        try:
            with open(ARQUIVO_FALHAS_JSON, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content: falhas_existentes = json.loads(content)
        except: falhas_existentes = []
    mapa_falhas = {item['url']: item for item in falhas_existentes}
    for falha in novas_falhas: mapa_falhas[falha['url']] = falha
    try:
        with open(ARQUIVO_FALHAS_JSON, 'w', encoding='utf-8') as f:
            json.dump(list(mapa_falhas.values()), f, indent=4, ensure_ascii=False)
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
            for k in ['link_m3u', 'url', 'link', 'endereco', 'source', 'm3u']:
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
        else: return None, conteudo
        if not url_encontrada:
            urls = re.findall(r'(https?://[^"\'\s\\]+)', texto)
            for url in urls:
                if ('.m3u' in url.lower() or 'get.php' in url.lower()) and 'aftv' not in url.lower():
                    limpo = limpar_url(url)
                    if limpo:
                        url_encontrada = limpo
                        break
        return url_encontrada, conteudo
    except: return None, None

def extrair_infos_extras(dados_json, nome_base):
    if not dados_json: return
    texto = json.dumps(dados_json)
    urls = re.findall(r'(https?://[^"\'\s]+)', texto)
    apks = [u for u in urls if any(x in u.lower() for x in ['.apk', 'aftv', 'downloader'])]
    if apks:
        caminho_apk = os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt")
        for apk in set(apks): salvar_linha_unica(caminho_apk, f"[{nome_base}] {apk}")
    linhas = texto.split('\\n') if '\\n' in texto else texto.split('\n')
    for linha in linhas:
        l = linha.strip()
        if len(l) > 300: continue
        for key, nome_arquivo in APPS_PARCERIA.items():
            if key.upper() in l.upper() and any(x in l.upper() for x in ['USER', 'PASS', 'LOGIN']):
                caminho_txt = os.path.join(PASTA_PARCERIAS, f"{nome_arquivo}.txt")
                salvar_linha_unica(caminho_txt, f"[{nome_base}] {l}")

def gerenciar_cache_inteligente(nome_base):
    padrao = os.path.join(PASTA_DESTINO, f"{glob.escape(nome_base)}_[*.m3u")
    arquivos_existentes = glob.glob(padrao)
    
    if arquivos_existentes:
        arquivo_antigo = max(arquivos_existentes, key=os.path.getmtime)
        try:
            if os.path.getsize(arquivo_antigo) > 2048:
                if time.time() - os.path.getmtime(arquivo_antigo) < CACHE_VALIDADE:
                    return True, arquivo_antigo
        except: pass
    return False, None

def baixar_arquivo(url, caminho_destino, desc_barra, posicao):
    # O IDM precisa do caminho absoluto da pasta (ex: D:\Pasta...)
    pasta_absoluta = os.path.abspath(os.path.dirname(caminho_destino))
    nome_arquivo = os.path.basename(caminho_destino)
    
    if not os.path.exists(CAMINHO_IDM):
        return False, f"IDM não encontrado em: {CAMINHO_IDM}"

    try:
        # /d URL /p PASTA /f NOME /n (silencioso) /a (adicionar na fila)
        cmd = [
            CAMINHO_IDM,
            '/d', url,
            '/p', pasta_absoluta,
            '/f', nome_arquivo,
            '/n',
            '/a' 
        ]
        
        # Manda para a fila
        subprocess.run(cmd, check=True)
        # Força o IDM a começar a baixar a fila imediatamente
        subprocess.run([CAMINHO_IDM, '/s'], check=False)
        
        return True, "Enviado para fila do IDM"

    except subprocess.CalledProcessError:
        return False, "Erro ao enviar comando para IDM"
    except Exception as e:
        return False, f"Erro Script IDM: {str(e)}"

def worker(nome_arquivo_json, fila_slots):
    global PARAR_EXECUCAO
    if PARAR_EXECUCAO: return "PARADO", None, None
    slot = fila_slots.get()
    nome_base = nome_arquivo_json.replace('.json', '')
    caminho_json = os.path.join(PASTA_JSON_RAW, nome_arquivo_json)
    
    try:
        checar_tecla_z()
        try:
            url_m3u, dados_brutos = extrair_m3u_do_json(caminho_json)
            extrair_infos_extras(dados_brutos, nome_base)
        except:
            fila_slots.put(slot)
            return "ERRO", nome_base, ("Erro Leitura JSON", "N/A")

        cache_valido, arquivo_antigo = gerenciar_cache_inteligente(nome_base)
        if cache_valido:
            fila_slots.put(slot)
            return "CACHE", os.path.basename(arquivo_antigo), "Válido"

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
            return "SUCESSO", novo_nome_arquivo, url_m3u
        else:
            return "ERRO", nome_base, (msg, url_m3u)

    except Exception as e:
        fila_slots.put(slot)
        return "ERRO", nome_base, (f"CRASH: {str(e)}", "url_desconhecida")

def main():
    if not os.path.exists(CAMINHO_IDM):
        print(f"❌ ATENÇÃO CRÍTICA: IDM não encontrado em:")
        print(f"👉 {CAMINHO_IDM}")
        return

    limpar_lixo_tmp()
    for p in [PASTA_DESTINO, PASTA_PARCERIAS, PASTA_DOWNLOADS]: os.makedirs(p, exist_ok=True)
    
    if not os.path.exists(PASTA_JSON_RAW):
        print("❌ Pasta Dados-Brutos não encontrada."); return

    arquivos = [f for f in os.listdir(PASTA_JSON_RAW) if f.endswith('.json')]
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"============================================================")
    print(f"🚀 SIGMA DOWNLOADER V24 (IDM GOD MODE) | Arq: {len(arquivos)}")
    print(f"📥 Modo: IDM AUTOMÁTICO")
    print(f"⚠️ DICA: Configure o 'Agendador' do IDM para 20+ downloads!")
    print(f"============================================================\n")

    fila_slots = queue.Queue()
    for i in range(1, MAX_SIMULTANEOS + 1): fila_slots.put(i)
    stats = defaultdict(int)

    with ThreadPoolExecutor(max_workers=MAX_SIMULTANEOS) as executor:
        futures = [executor.submit(worker, arq, fila_slots) for arq in arquivos]
        with tqdm(total=len(arquivos), unit="links") as pbar:
            for f in as_completed(futures):
                try: status, nome, info = f.result()
                except: status, nome, info = "ERRO", "UNK", ("Fatal", "N/A")
                
                stats[status] += 1
                if status == "ERRO":
                    msg_erro, url_erro = info
                    tqdm.write(f"❌ {nome} -> {msg_erro}")
                    erro_obj = {"nome": nome, "url": url_erro, "erro": msg_erro, "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    salvar_falhas_json([erro_obj])
                
                pbar.set_postfix_str(f"✅IDM:{stats['SUCESSO']} ⏭️Skip:{stats['CACHE']} ❌Err:{stats['ERRO']}")
                pbar.update(1)
                if PARAR_EXECUCAO: executor.shutdown(wait=False, cancel_futures=True); break
    
    print("\n🏁 Links enviados! O IDM vai cuidar de tudo agora.")

if __name__ == "__main__":
    main()