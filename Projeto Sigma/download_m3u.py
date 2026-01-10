import json
import requests
import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse
import dns.resolver
from tqdm import tqdm

# --- CONFIGURAÇÕES ---
ARQUIVO_FONTES = "fontes.json"
PASTA_DESTINO = "Listas-Downloaded"
ARQUIVO_ERROS = "erros_download.txt"
ARQUIVO_BRUTA = "lista_bruta.txt"

# Só roda se a lista bruta estiver vazia (Opcional, conforme seu pedido)
VERIFICAR_BRUTA_VAZIA = True 

HEADERS_FAKE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Upgrade-Insecure-Requests": "1"
}

# --- FUNÇÕES ---

def limpar_nome_arquivo(nome):
    # Remove emojis e caracteres inválidos para Windows
    nome_sem_emoji = nome.encode('ascii', 'ignore').decode('ascii').strip()
    if not nome_sem_emoji: nome_sem_emoji = "Lista_Sem_Nome"
    return re.sub(r'[<>:"/\\|?*]', '', nome_sem_emoji).strip().replace(" ", "_")

def precisa_atualizar(caminho_arquivo):
    if not os.path.exists(caminho_arquivo): return True
    
    stats = os.stat(caminho_arquivo)
    ultima_mod = datetime.fromtimestamp(stats.st_mtime)
    # Se tem menos de 1 hora (3600s), não baixa de novo
    if (datetime.now() - ultima_mod).total_seconds() < 3600:
        return False
    return True

def extrair_link_m3u_da_api(api_url):
    """Acessa a API e pesca o link M3U válido dentro dela"""
    session = requests.Session()
    session.headers.update(HEADERS_FAKE)
    
    texto_resposta = ""
    try:
        # Tenta POST primeiro
        resp = session.post(api_url, timeout=15, verify=False)
        if resp.status_code != 200:
            resp = session.get(api_url, timeout=15, verify=False) # Fallback GET
        
        try:
            texto_resposta = json.dumps(resp.json()) # Se for JSON
        except:
            texto_resposta = resp.text # Se for Texto
            
    except Exception as e:
        return None, f"Erro conexão API: {e}"

    # Regex para achar M3U
    urls = re.findall(r'(https?://[^\s<>"]+)', texto_resposta)
    candidatos = []
    for url in urls:
        u = url.lower()
        # Filtra links que parecem ser a lista real
        if ('get.php' in u and 'username=' in u) or \
           ('.m3u' in u and 'aftv' not in u and 'e.jhysa' not in u) or \
           ('output=mpegts' in u):
            candidatos.append(url)
            
    if candidatos:
        return candidatos[0], None # Retorna o primeiro encontrado
    
    return None, "Nenhum link M3U encontrado na resposta da API"

def baixar_arquivo_com_progresso(url, caminho_saida, nome_exibicao):
    try:
        resp = requests.get(url, headers=HEADERS_FAKE, stream=True, timeout=20, verify=False)
        resp.raise_for_status()
        
        total_size = int(resp.headers.get('content-length', 0))
        
        # Se o arquivo for minúsculo (<100 bytes), provavelmente é erro
        if total_size > 0 and total_size < 100:
            return False, "Arquivo retornado é muito pequeno (provavelmente erro)"

        with tqdm(total=total_size, unit='B', unit_scale=True, desc=f"   ⬇️ {nome_exibicao[:20]}...", ncols=80) as bar:
            with open(caminho_saida, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    requests.packages.urllib3.disable_warnings()
    
    # 1. Verificação de Segurança (Inbox Vazia)
    if VERIFICAR_BRUTA_VAZIA and os.path.exists(ARQUIVO_BRUTA):
        with open(ARQUIVO_BRUTA, 'r', encoding='utf-8') as f:
            conteudo = f.read().strip()
        if conteudo:
            print(f"⚠️ ATENÇÃO: O arquivo '{ARQUIVO_BRUTA}' não está vazio.")
            print("   Por favor, rode o 'minerador_sigma.py' primeiro para processar os novos links.")
            return

    if not os.path.exists(ARQUIVO_FONTES):
        print(f"❌ '{ARQUIVO_FONTES}' não encontrado.")
        return

    with open(ARQUIVO_FONTES, 'r', encoding='utf-8') as f:
        fontes = json.load(f)

    if not os.path.exists(PASTA_DESTINO): os.makedirs(PASTA_DESTINO)
    
    # Limpa log de erros antigo
    if os.path.exists(ARQUIVO_ERROS): os.remove(ARQUIVO_ERROS)

    print(f"🚀 INICIANDO DOWNLOADER ({len(fontes)} listas mapeadas)\n")

    sucessos = 0
    erros = 0

    for item in fontes:
        nome_completo = item.get("nome", "Sem Nome")
        api_url = item.get("api_url")
        url_direta = item.get("url") # Caso tenhamos salvo direto (legado)

        nome_arquivo = f"{limpar_nome_arquivo(nome_completo)}.m3u"
        caminho_final = os.path.join(PASTA_DESTINO, nome_arquivo)

        print(f"📺 {nome_completo}")

        # Verifica Cache de Arquivo (1 hora)
        if not precisa_atualizar(caminho_final):
            print(f"   ⏳ Arquivo recente. Pulando download.")
            continue

        link_para_baixar = None

        # ESTRATÉGIA 1: Se tem API, extrai o link fresco
        if api_url:
            # print("   📡 Consultando API para link fresco...")
            link_extraido, erro_api = extrair_link_m3u_da_api(api_url)
            if link_extraido:
                link_para_baixar = link_extraido
                # print(f"   🔗 Link encontrado: {link_extraido[:40]}...")
            else:
                print(f"   ⚠️ Falha na API: {erro_api}")
        
        # ESTRATÉGIA 2: Se falhou API ou não tem, tenta URL direta se existir
        if not link_para_baixar and url_direta:
            link_para_baixar = url_direta
        
        # EXECUTA O DOWNLOAD
        if link_para_baixar:
            ok, msg = baixar_arquivo_com_progresso(link_para_baixar, caminho_final, nome_completo)
            if ok:
                sucessos += 1
                # print(f"   ✅ Download concluído!")
            else:
                erros += 1
                print(f"   ❌ Falha no download: {msg}")
                with open(ARQUIVO_ERROS, 'a', encoding='utf-8') as log:
                    log.write(f"{datetime.now()} | {nome_completo} | {msg}\n")
        else:
            erros += 1
            print("   ⛔ Nenhum link baixável encontrado.")
            with open(ARQUIVO_ERROS, 'a', encoding='utf-8') as log:
                log.write(f"{datetime.now()} | {nome_completo} | API não retornou link M3U válido\n")
        
        print("-" * 50)

    print(f"\n🏁 FIM DO PROCESSO")
    print(f"✅ Atualizados: {sucessos}")
    print(f"❌ Falhas: {erros}")
    if erros > 0: print(f"📄 Verifique '{ARQUIVO_ERROS}' para detalhes.")

if __name__ == "__main__":
    main()