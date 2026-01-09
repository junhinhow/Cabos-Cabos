import json
import requests
import os
import time
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse
import dns.resolver  # pip install dnspython
from tqdm import tqdm # pip install tqdm

# --- CONFIGURAÇÕES ---
ARQUIVO_JSON = "fontes.json"
PASTA_DESTINO = "Listas-Downloaded"
ARQUIVO_ERROS = "erros_download.txt"

TIMEOUT = 15  # Aumentei um pouco para dar tempo da conexão iniciar
DELAY_RETRY = 2
MAX_RETRIES_POR_DNS = 3 # Reduzi para não demorar uma eternidade se o link estiver morto

# Lista de estratégias de DNS
DNS_SERVERS = [
    {"nome": "Padrão do Sistema", "ip": None}, 
    {"nome": "Cloudflare", "ip": "1.1.1.1"},
    {"nome": "Google", "ip": "8.8.8.8"}
]

def limpar_nome_arquivo(nome):
    return re.sub(r'[<>:"/\\|?*]', '', nome).strip().replace(" ", "_")

def obter_nome_servidor(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.split('.')[0]
    except:
        return "Servidor_Desconhecido"

def resolver_dns_customizado(hostname, dns_ip):
    resolver = dns.resolver.Resolver()
    resolver.nameservers = [dns_ip]
    try:
        answers = resolver.resolve(hostname, 'A')
        return answers[0].to_text() 
    except Exception:
        return None

def registrar_erro(nome, url, motivo):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mensagem = f"[{timestamp}] NOME: {nome} | URL: {url} | ERRO: {motivo}\n"
    with open(ARQUIVO_ERROS, 'a', encoding='utf-8') as f:
        f.write(mensagem)

def precisa_atualizar(caminho_arquivo):
    if not os.path.exists(caminho_arquivo):
        return True 

    stats = os.stat(caminho_arquivo)
    ultima_modificacao = datetime.fromtimestamp(stats.st_mtime)
    agora = datetime.now()
    diferenca = agora - ultima_modificacao

    if diferenca > timedelta(hours=1):
        print(f"   ⚠️  Arquivo antigo ({str(diferenca).split('.')[0]}). Atualizando...")
        return True
    
    print(f"   ⏳ Recente ({str(diferenca).split('.')[0]} atrás). Pulando.")
    return False

def baixar_com_estrategia(url, caminho_saida, nome_exibicao):
    parsed_url = urlparse(url)
    hostname = parsed_url.netloc
    esquema = parsed_url.scheme 
    path_restante = parsed_url.path
    if parsed_url.query:
        path_restante += "?" + parsed_url.query

    erro_recente = "Desconhecido"

    for dns_provider in DNS_SERVERS:
        nome_dns = dns_provider["nome"]
        ip_dns = dns_provider["ip"]
        
        # print(f"   🌐 DNS: {nome_dns}...") 

        for tentativa in range(1, MAX_RETRIES_POR_DNS + 1):
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                target_url = url 

                # Lógica DNS Custom
                if ip_dns:
                    ip_alvo = resolver_dns_customizado(hostname, ip_dns)
                    if not ip_alvo:
                        raise Exception(f"Falha DNS {ip_dns}")
                    target_url = f"{esquema}://{ip_alvo}{path_restante}"
                    headers["Host"] = hostname
                
                # INICIO DO DOWNLOAD COM BARRA DE PROGRESSO
                # stream=True é essencial para baixar aos poucos
                response = requests.get(target_url, headers=headers, timeout=TIMEOUT, verify=False, stream=True)
                response.raise_for_status()

                # Tenta pegar o tamanho total do arquivo (alguns servidores não enviam)
                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024 # 1KB por pedaço

                # Configuração da Barra Visual
                tqdm_bar = tqdm(total=total_size, unit='iB', unit_scale=True, desc=f"   ⬇️  {nome_exibicao}", ncols=100)

                with open(caminho_saida, 'wb') as f:
                    for data in response.iter_content(block_size):
                        tqdm_bar.update(len(data))
                        f.write(data)
                
                tqdm_bar.close()
                
                if total_size != 0 and os.path.getsize(caminho_saida) < 100:
                     # Se o arquivo baixou mas tem menos de 100 bytes, provavelmente é erro do site
                     raise Exception("Arquivo baixado corrompido ou vazio")

                return True, None

            except Exception as e:
                erro_recente = f"{type(e).__name__}"
                # Se a barra de progresso foi aberta, fecha ela para não bugar o terminal
                if 'tqdm_bar' in locals():
                    tqdm_bar.close()
                
                # Só mostra mensagem se for a última tentativa do DNS atual, para não poluir
                if tentativa == MAX_RETRIES_POR_DNS:
                     print(f"      ❌ Falha no {nome_dns}: {erro_recente}")
                
                time.sleep(DELAY_RETRY) 
        
    return False, erro_recente

def main():
    if not os.path.exists(PASTA_DESTINO):
        os.makedirs(PASTA_DESTINO)

    if os.path.exists(ARQUIVO_ERROS):
        os.remove(ARQUIVO_ERROS)

    requests.packages.urllib3.disable_warnings()

    try:
        with open(ARQUIVO_JSON, 'r', encoding='utf-8') as f:
            lista_links = json.load(f)
    except Exception as e:
        print(f"❌ Erro crítico no JSON: {e}")
        return

    print(f"\n🚀 DOWNLOADER INICIADO ({len(lista_links)} listas)\n")

    erros_contagem = 0
    sucesso_contagem = 0

    for item in lista_links:
        url = item.get("url")
        nome_custom = item.get("nome", "").strip()

        if not url: continue

        nome_servidor = nome_custom if nome_custom else obter_nome_servidor(url)
        nome_limpo = limpar_nome_arquivo(nome_servidor)
        
        nome_arquivo = f"{nome_limpo}.m3u"
        caminho_completo = os.path.join(PASTA_DESTINO, nome_arquivo)

        print(f"📺 {nome_limpo}")

        if precisa_atualizar(caminho_completo):
            sucesso, motivo_erro = baixar_com_estrategia(url, caminho_completo, nome_limpo)
            
            if sucesso:
                sucesso_contagem += 1
                # print(f"   ✅ Sucesso!") 
            else:
                print(f"   ⛔ FALHA TOTAL. Verifique log.")
                registrar_erro(nome_limpo, url, motivo_erro)
                erros_contagem += 1
        
        print("-" * 50)

    print(f"\n🏁 RESUMO FINAL:")
    print(f"✅ Atualizados: {sucesso_contagem}")
    print(f"⚠️  Falhas: {erros_contagem}")
    if erros_contagem > 0:
        print(f"📄 Detalhes das falhas salvos em '{ARQUIVO_ERROS}'")

if __name__ == "__main__":
    main()