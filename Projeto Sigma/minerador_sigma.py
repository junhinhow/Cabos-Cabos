import json
import requests
import os
import re
import time
from urllib.parse import urlparse
from datetime import datetime

# --- CONFIGURAÇÕES DE NOMES ---
ALIASES_SERVIDORES = {
    "socialmaster": "🦁 Social Master",
    "servidorx": "❌ Servidor X",
    "maniagp": "🍿 CineMania",
    "problack": "⚫ Pro Black",
    "topztv": "🔝 TopZ",
    "netturbo": "🚀 NetTurbo",
    "p2box": "📦 P2Box",
}

# --- CABEÇALHOS (Anti-Bloqueio) ---
HEADERS_FAKE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Upgrade-Insecure-Requests": "1"
}

# --- ARQUIVOS E PASTAS ---
ARQUIVO_ENTRADA = "lista_bruta.txt"
ARQUIVO_FONTES_M3U = "fontes.json"
ARQUIVO_MASTER_JSON = "master_db_sigma.json"
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_PARCERIAS = "Parcerias"
PASTA_DOWNLOADS = "Downloads"

APPS_PARCERIA = {
    "Assist": "Assist_Plus_Play_Sim", "Play Sim": "Assist_Plus_Play_Sim",
    "Lazer": "Lazer_Play", "Vizzion": "Vizzion", "Unitv": "UniTV",
    "Xcloud": "XCloud_TV", "P2P": "Codigos_P2P_Geral", "Smarters": "IPTV_Smarters_DNS",
    "XCIPTV": "XCIPTV_Dados"
}

def limpar_nome(nome):
    return re.sub(r'[<>:"/\\|?*]', '', nome).strip().replace(" ", "_")

def arquivo_eh_recente(caminho_arquivo):
    """Retorna True se o arquivo existe e tem menos de 1 hora."""
    if not os.path.exists(caminho_arquivo): return False
    
    timestamp_mod = os.path.getmtime(caminho_arquivo)
    idade_segundos = time.time() - timestamp_mod
    
    return idade_segundos < 3600 # 3600s = 1 hora

def detectar_servidor(url):
    try:
        parsed = urlparse(url)
        subdominio = parsed.netloc.split('.')[0].lower()
        nome_bonito = ALIASES_SERVIDORES.get(subdominio, subdominio.upper())
        return nome_bonito, subdominio
    except:
        return "Desconhecido", "desc"

def requisicao_inteligente(url):
    session = requests.Session()
    session.headers.update(HEADERS_FAKE)
    try:
        resp = session.post(url, timeout=15, verify=False)
        if resp.status_code == 200: return resp
    except: pass
    
    try:
        resp = session.get(url, timeout=15, verify=False)
        resp.raise_for_status()
        return resp
    except Exception as e:
        raise Exception(f"Falha na conexão: {e}")

def analisar_conteudo(texto_resposta, nome_servidor):
    resultados = {"m3u": [], "parcerias": {}, "downloads": []}
    linhas = texto_resposta.split('\n')
    
    # Busca M3U
    urls_encontradas = re.findall(r'(https?://[^\s<>"]+)', texto_resposta)
    for url in urls_encontradas:
        u = url.lower()
        if ('get.php' in u and 'username=' in u) or ('.m3u' in u and 'aftv' not in u) or ('output=mpegts' in u):
            if url not in resultados["m3u"]:
                resultados["m3u"].append(url)
    
    # Busca Downloads
    for url in urls_encontradas:
        if '.apk' in url.lower() or 'aftv.news' in url.lower() or 'dl.ntdev' in url.lower():
             if url not in resultados["downloads"]:
                resultados["downloads"].append(url)

    # Busca Parcerias
    app_atual = None
    for linha in linhas:
        linha_limpa = linha.strip()
        if not linha_limpa: continue
        
        # --- FILTRO DE LIMPEZA VISUAL ---
        # Se a linha for gigantesca (json bruto), ignora
        if len(linha_limpa) > 300: continue 

        for chave, nome_arquivo in APPS_PARCERIA.items():
            if chave.upper() in linha_limpa.upper():
                app_atual = nome_arquivo
                if app_atual not in resultados["parcerias"]:
                    resultados["parcerias"][app_atual] = []
                break
        
        if app_atual:
            if any(x in linha_limpa.upper() for x in ["CÓDIGO", "USUÁRIO", "SENHA", "PIN", "DNS", "URL"]):
                dado_formatado = f"[{nome_servidor}] {linha_limpa}"
                if dado_formatado not in resultados["parcerias"][app_atual]:
                     resultados["parcerias"][app_atual].append(dado_formatado)
    
    return resultados

def main():
    # Setup de Pastas
    for pasta in [PASTA_JSON_RAW, PASTA_PARCERIAS, PASTA_DOWNLOADS]:
        if not os.path.exists(pasta): os.makedirs(pasta)
    
    # Limpa parcerias antigas
    for f in os.listdir(PASTA_PARCERIAS):
        try: os.remove(os.path.join(PASTA_PARCERIAS, f))
        except: pass

    if not os.path.exists(ARQUIVO_ENTRADA):
        print(f"❌ '{ARQUIVO_ENTRADA}' não encontrado.")
        return

    with open(ARQUIVO_ENTRADA, 'r', encoding='utf-8') as f:
        linhas_brutas = [l.strip() for l in f.readlines() if l.strip()]

    master_db = []
    lista_m3u_final = []
    
    print(f"🚀 Iniciando Mineração com CACHE ({len(linhas_brutas)//2} fontes)...\n")

    for i in range(0, len(linhas_brutas), 2):
        try:
            nome_original = linhas_brutas[i]
            url_api = linhas_brutas[i+1]
            if not url_api.startswith("http"): continue

            nome_servidor, subdominio = detectar_servidor(url_api)
            
            tag = ""
            if "SEM ADULTO" in nome_original.upper() or "S/ADULTO" in nome_original.upper(): tag = " [SAFE]"
            elif "COM ADULTO" in nome_original.upper() or "C/ADULTO" in nome_original.upper(): tag = " [+18]"
            
            nome_completo = f"{nome_servidor} - {subdominio.upper()}{tag}"
            nome_arquivo_json = f"{limpar_nome(nome_completo)}.json"
            caminho_json = os.path.join(PASTA_JSON_RAW, nome_arquivo_json)
            
            print(f"📡 {nome_completo}")

            dados_json = None
            origem_dados = ""

            # 1. VERIFICA CACHE LOCAL
            if arquivo_eh_recente(caminho_json):
                try:
                    with open(caminho_json, 'r', encoding='utf-8') as f:
                        dados_json = json.load(f)
                    origem_dados = "💾 Cache Local"
                    texto_resposta = json.dumps(dados_json, ensure_ascii=False)
                except:
                    origem_dados = "⚠️ Cache Corrompido"
            
            # 2. SE NÃO TIVER CACHE, BAIXA DA INTERNET
            if not dados_json:
                origem_dados = "🌐 Download Online"
                try:
                    resp = requisicao_inteligente(url_api)
                    try:
                        dados_json = resp.json()
                        texto_resposta = json.dumps(dados_json, ensure_ascii=False)
                    except:
                        dados_json = {"raw_text": resp.text}
                        texto_resposta = resp.text
                    
                    # Salva no Cache
                    with open(caminho_json, 'w', encoding='utf-8') as f:
                        json.dump(dados_json, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    print(f"   ❌ Falha ao baixar: {e}")
                    print("-" * 50)
                    continue

            # 3. PROCESSAMENTO
            print(f"   ℹ️  Origem: {origem_dados}")
            
            master_db.append({"servidor": nome_servidor, "dados": dados_json})
            analise = analisar_conteudo(texto_resposta, nome_servidor)

            # Exibição M3U
            if analise['m3u']:
                for m3u in analise['m3u']:
                    print(f"   📺 M3U: {m3u[:60]}...") 
                    lista_m3u_final.append({"nome": nome_completo, "api_url": url_api})
            else:
                print("   ⚠️  Nenhuma lista M3U encontrada.")
                # Adiciona para o baixador tentar extrair via regex depois se necessário
                lista_m3u_final.append({"nome": nome_completo, "api_url": url_api})

            # Exibição Parcerias
            if analise['parcerias']:
                for app, dados in analise['parcerias'].items():
                    print(f"   🤝 {app}:")
                    for d in dados:
                        # Limpa o nome do servidor para exibir só o dado
                        dado_limpo = d.split("] ")[-1]
                        print(f"      └─ {dado_limpo}") 
                    
                    # Salva TXT
                    caminho_txt = os.path.join(PASTA_PARCERIAS, f"{app}.txt")
                    with open(caminho_txt, 'a', encoding='utf-8') as f:
                        f.write(f"\n--- {nome_completo} ---\n")
                        f.write(f"Fonte: {url_api}\n")
                        for l in dados: f.write(f"{l}\n")

            if analise['downloads']:
                print(f"   📥 {len(analise['downloads'])} Downloads encontrados.")
                with open(os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt"), 'a', encoding='utf-8') as f:
                    f.write(f"\n--- {nome_completo} ---\n")
                    for l in analise["downloads"]: f.write(f"{l}\n")
            
            print("-" * 50)

        except Exception as e:
            print(f"❌ Erro grave no loop: {e}")

    # Salva Finais
    with open(ARQUIVO_FONTES_M3U, 'w', encoding='utf-8') as f:
        json.dump(lista_m3u_final, f, indent=4, ensure_ascii=False)
    
    with open(ARQUIVO_MASTER_JSON, 'w', encoding='utf-8') as f:
        json.dump(master_db, f, indent=4, ensure_ascii=False)

    print(f"\n✅ CONCLUÍDO! Fontes M3U: {len(lista_m3u_final)}")

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    main()