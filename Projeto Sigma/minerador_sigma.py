import json
import requests
import os
import re
import time
from datetime import datetime

# --- CONFIGURAÇÕES ---
ARQUIVO_FONTES = "fontes.json"
ARQUIVO_LOG_ERROS = "erros_mineracao.txt"
ARQUIVO_MASTER_JSON = "master_db_sigma.json"

PASTA_JSON_RAW = "Dados-Brutos"
PASTA_PARCERIAS = "Parcerias"
PASTA_DOWNLOADS = "Downloads"

# Regra de validade do cache: 4 Horas (4 * 60 * 60 = 14400 segundos)
TEMPO_VALIDADE_CACHE = 14400 

HEADERS_FAKE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Upgrade-Insecure-Requests": "1"
}

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
    """Salva o erro no arquivo de texto"""
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    msg = f"[{timestamp}] {nome} | {erro}\nLink: {url}\n{'-'*30}\n"
    try:
        with open(ARQUIVO_LOG_ERROS, 'a', encoding='utf-8') as f:
            f.write(msg)
    except: pass

def arquivo_eh_recente(caminho_arquivo):
    """Retorna True se o arquivo existe e tem menos de 4 horas"""
    if not os.path.exists(caminho_arquivo): return False
    
    timestamp_mod = os.path.getmtime(caminho_arquivo)
    idade_do_arquivo = time.time() - timestamp_mod
    
    return idade_do_arquivo < TEMPO_VALIDADE_CACHE

def requisicao_inteligente(url):
    session = requests.Session()
    session.headers.update(HEADERS_FAKE)
    
    # Tenta POST primeiro
    try:
        resp = session.post(url, timeout=15, verify=False)
        if resp.status_code == 200: return resp
    except: pass
    
    # Tenta GET (Fallback)
    try:
        resp = session.get(url, timeout=15, verify=False)
        resp.raise_for_status()
        return resp
    except Exception as e:
        raise Exception(f"Falha na conexão ({e})")

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
        # Ignora linhas gigantes (provavelmente JSON raw)
        if not l or len(l) > 300: continue
        
        for k, v in APPS_PARCERIA.items():
            if k.upper() in l.upper():
                app_atual = v
                break
        
        if app_atual and any(x in l.upper() for x in ["CÓDIGO", "USUÁRIO", "SENHA", "PIN", "DNS", "URL"]):
            with open(os.path.join(PASTA_PARCERIAS, f"{app_atual}.txt"), 'a', encoding='utf-8') as f:
                f.write(f"[{nome_exibicao}] {l}\n")

def main():
    requests.packages.urllib3.disable_warnings()
    
    # Cria pastas necessárias
    for p in [PASTA_JSON_RAW, PASTA_PARCERIAS, PASTA_DOWNLOADS]:
        os.makedirs(p, exist_ok=True)

    # Limpa log de erros anterior
    if os.path.exists(ARQUIVO_LOG_ERROS):
        try: os.remove(ARQUIVO_LOG_ERROS)
        except: pass

    # Limpa parcerias antigas para evitar duplicatas
    for f in os.listdir(PASTA_PARCERIAS):
        try: os.remove(os.path.join(PASTA_PARCERIAS, f))
        except: pass

    if not os.path.exists(ARQUIVO_FONTES):
        print(f"❌ '{ARQUIVO_FONTES}' não encontrado.")
        return

    with open(ARQUIVO_FONTES, 'r', encoding='utf-8') as f:
        fontes = json.load(f)

    print(f"🚀 MINERADOR V8 (Regra 4h): Auditando {len(fontes)} fontes...\n")
    
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

        # --- LÓGICA DE CACHE (4 HORAS) ---
        usar_cache = False
        
        if arquivo_eh_recente(caminho_json):
            print("   ⏳ Cache válido (< 4h). Usando arquivo local.")
            usar_cache = True
            cacheados += 1
        else:
            print("   🌐 Cache expirado ou ausente. Atualizando da API...")

        texto_completo = ""

        try:
            if usar_cache:
                with open(caminho_json, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                texto_completo = json.dumps(dados, ensure_ascii=False)
            else:
                # PAUSA ANTI-BLOQUEIO (Importante!)
                time.sleep(2) 
                
                resp = requisicao_inteligente(url)
                try:
                    dados = resp.json()
                    texto_completo = json.dumps(dados, ensure_ascii=False)
                except:
                    # Se não for JSON, salva como texto puro
                    dados = {"raw_text": resp.text}
                    texto_completo = resp.text
                
                with open(caminho_json, 'w', encoding='utf-8') as f:
                    json.dump(dados, f, indent=4, ensure_ascii=False)
                
                atualizados += 1
                print("   💾 Dados atualizados em 'Dados-Brutos'.")

            # Sempre processa as parcerias, mesmo vindo do cache
            extrair_parcerias_e_downloads(texto_completo, nome)

        except Exception as e:
            msg_erro = str(e)
            print(f"   ❌ Erro: {msg_erro}")
            registrar_erro_log(nome, url, msg_erro)
            erros += 1
        
        print("-" * 40)

    print(f"\n✅ FIM DA MINERAÇÃO.")
    print(f"🆕 Baixados da API: {atualizados}")
    print(f"💾 Lidos do Cache: {cacheados}")
    print(f"❌ Falhas: {erros}")
    
    if erros > 0:
        print(f"📄 Detalhes salvos em: '{ARQUIVO_LOG_ERROS}'")

if __name__ == "__main__":
    main()