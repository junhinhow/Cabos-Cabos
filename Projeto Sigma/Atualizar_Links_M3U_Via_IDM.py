import json
import os
import re
import time
import subprocess
from datetime import datetime

# --- CONFIGURAÇÕES ---
ARQUIVO_FONTES = "fontes.json"
ARQUIVO_LOG_ERROS = "erros_mineracao.txt"

PASTA_JSON_RAW = "Dados-Brutos"
PASTA_PARCERIAS = "Parcerias"
PASTA_DOWNLOADS = "Downloads"

# ✅ SEU CAMINHO DO IDM (DISCO D:)
CAMINHO_IDM = r"D:\Program Files (x86)\Internet Download Manager\IDMan.exe"

# Regra de validade do cache: 4 Horas
TEMPO_VALIDADE_CACHE = 14400 

# Tempo máximo que o Python espera o IDM baixar o JSON (em segundos)
TIMEOUT_DOWNLOAD_IDM = 60 

APPS_PARCERIA = {
    "Assist": "Assist_Plus_Play_Sim", "Play Sim": "Assist_Plus_Play_Sim",
    "Lazer": "Lazer_Play", "Vizzion": "Vizzion", "Unitv": "UniTV",
    "Xcloud": "XCloud_TV", "P2P": "Codigos_P2P_Geral", "Smarters": "IPTV_Smarters_DNS",
    "XCIPTV": "XCIPTV_Dados"
}

def limpar_nome_arquivo(nome):
    try:
        nome_ascii = nome.encode('ascii', 'ignore').decode('ascii')
    except:
        nome_ascii = "Nome_Desconhecido"
    return re.sub(r'[<>:"/\\|?*]', '', nome_ascii).strip().replace(" ", "_")

def registrar_erro_log(nome, url, erro):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    msg = f"[{timestamp}] {nome} | {erro}\nLink: {url}\n{'-'*30}\n"
    try:
        with open(ARQUIVO_LOG_ERROS, 'a', encoding='utf-8') as f:
            f.write(msg)
    except: pass

def arquivo_eh_recente(caminho_arquivo):
    if not os.path.exists(caminho_arquivo): return False
    timestamp_mod = os.path.getmtime(caminho_arquivo)
    idade_do_arquivo = time.time() - timestamp_mod
    return idade_do_arquivo < TEMPO_VALIDADE_CACHE

def baixar_json_via_idm(url, caminho_completo):
    """Envia o comando para o IDM baixar o JSON"""
    if not os.path.exists(CAMINHO_IDM):
        return False, "IDM não encontrado"

    # Se já existir um arquivo antigo, deletamos para garantir que o IDM baixe um novo
    if os.path.exists(caminho_completo):
        try: os.remove(caminho_completo)
        except: pass

    pasta_absoluta = os.path.abspath(os.path.dirname(caminho_completo))
    nome_arquivo = os.path.basename(caminho_completo)

    try:
        # /n = Silent, /a = Fila, /d = URL, /p = Pasta, /f = Nome
        cmd = [
            CAMINHO_IDM,
            '/d', url,
            '/p', pasta_absoluta,
            '/f', nome_arquivo,
            '/n',
            '/a'
        ]
        subprocess.run(cmd, check=True)
        
        # Força inicio da fila
        subprocess.run([CAMINHO_IDM, '/s'], check=False)
        return True, "Enviado ao IDM"
    except Exception as e:
        return False, str(e)

def esperar_download_concluir(caminho_arquivo):
    """Loop que espera o arquivo aparecer na pasta (Download concluído)"""
    inicio = time.time()
    while True:
        # Se o arquivo existe e tem tamanho > 0
        if os.path.exists(caminho_arquivo) and os.path.getsize(caminho_arquivo) > 0:
            # Espera um tiquinho extra para garantir que o IDM soltou o arquivo
            time.sleep(0.5)
            return True
        
        # Verifica timeout
        if time.time() - inicio > TIMEOUT_DOWNLOAD_IDM:
            return False
        
        time.sleep(1) # Checa a cada 1 segundo

def extrair_parcerias_e_downloads(texto_resposta, nome_exibicao):
    linhas = texto_resposta.split('\n')
    
    # Extrai Downloads (APKs)
    urls = re.findall(r'(https?://[^\s<>"]+)', texto_resposta)
    apks = []
    for url in urls:
        if '.apk' in url.lower() or 'aftv.news' in url.lower() or 'dl.ntdev' in url.lower():
             if url not in apks: apks.append(url)
    
    if apks:
        with open(os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt"), 'a', encoding='utf-8') as f:
            f.write(f"\n--- {nome_exibicao} ---\n")
            for l in apks: f.write(f"{l}\n")

    # Extrai Parcerias (Senhas)
    app_atual = None
    for linha in linhas:
        l = linha.strip()
        if not l or len(l) > 300: continue
        
        for k, v in APPS_PARCERIA.items():
            if k.upper() in l.upper():
                app_atual = v
                break
        
        if app_atual and any(x in l.upper() for x in ["CÓDIGO", "USUÁRIO", "SENHA", "PIN", "DNS", "URL"]):
            with open(os.path.join(PASTA_PARCERIAS, f"{app_atual}.txt"), 'a', encoding='utf-8') as f:
                f.write(f"[{nome_exibicao}] {l}\n")

def main():
    # Cria pastas necessárias
    for p in [PASTA_JSON_RAW, PASTA_PARCERIAS, PASTA_DOWNLOADS]:
        os.makedirs(p, exist_ok=True)

    # Limpa log de erros anterior
    if os.path.exists(ARQUIVO_LOG_ERROS):
        try: os.remove(ARQUIVO_LOG_ERROS)
        except: pass

    # Limpa parcerias antigas
    for f in os.listdir(PASTA_PARCERIAS):
        try: os.remove(os.path.join(PASTA_PARCERIAS, f))
        except: pass

    if not os.path.exists(ARQUIVO_FONTES):
        print(f"❌ '{ARQUIVO_FONTES}' não encontrado.")
        return

    with open(ARQUIVO_FONTES, 'r', encoding='utf-8') as f:
        fontes = json.load(f)

    print(f"🚀 MINERADOR V9 (IDM EDITION) | Fontes: {len(fontes)}")
    print(f"📥 Modo: IDM Baixa -> Python Lê -> Extrai Dados\n")
    
    atualizados = 0
    cacheados = 0
    erros = 0

    for item in fontes:
        nome = item.get('nome')
        url = item.get('api_url')
        
        if not url: continue

        nome_arq = f"{limpar_nome_arquivo(nome)}.json"
        caminho_json = os.path.join(PASTA_JSON_RAW, nome_arq)

        print(f"📡 {nome}")

        conteudo_para_analise = ""
        sucesso_leitura = False

        # --- LÓGICA DE CACHE ---
        if arquivo_eh_recente(caminho_json):
            print("   ⏳ Cache válido. Usando arquivo local.")
            cacheados += 1
            sucesso_leitura = True
        else:
            print("   ⬇️ Enviando para o IDM...")
            
            status, msg = baixar_json_via_idm(url, caminho_json)
            
            if status:
                print("   🕒 Aguardando download concluir...")
                if esperar_download_concluir(caminho_json):
                    print("   ✅ Download concluído!")
                    atualizados += 1
                    sucesso_leitura = True
                else:
                    print("   ❌ Timeout: IDM demorou demais ou link quebrado.")
                    registrar_erro_log(nome, url, "Timeout esperando IDM")
                    erros += 1
            else:
                print(f"   ❌ Erro ao chamar IDM: {msg}")
                erros += 1

        # --- PROCESSAMENTO DO ARQUIVO (Seja do Cache ou do IDM) ---
        if sucesso_leitura and os.path.exists(caminho_json):
            try:
                with open(caminho_json, 'r', encoding='utf-8', errors='ignore') as f:
                    conteudo_para_analise = f.read()
                
                # Extrai as parcerias e APKs usando o texto que está no disco
                extrair_parcerias_e_downloads(conteudo_para_analise, nome)
                
            except Exception as e:
                print(f"   ⚠️ Erro ao ler JSON do disco: {e}")

        print("-" * 40)

    print(f"\n✅ FIM DA MINERAÇÃO.")
    print(f"🆕 Baixados (IDM): {atualizados}")
    print(f"💾 Cache Local: {cacheados}")
    print(f"❌ Falhas: {erros}")
    
    if erros > 0:
        print(f"📄 Log de erros: '{ARQUIVO_LOG_ERROS}'")

if __name__ == "__main__":
    main()