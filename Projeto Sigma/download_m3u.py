import json
import requests
import os
import re
from datetime import datetime
from urllib.parse import urlparse

# --- CONFIGURAÇÕES ---
ARQUIVO_JSON = "fontes.json"
PASTA_DESTINO = "Listas-Downloaded"
TIMEOUT_SEGUNDOS = 15  # Tempo máximo para esperar o download

def limpar_nome_arquivo(nome):
    """Remove caracteres inválidos para nome de arquivo"""
    return re.sub(r'[<>:"/\\|?*]', '', nome).strip().replace(" ", "_")

def obter_nome_servidor(url):
    """Extrai o domínio caso o JSON não tenha nome definido"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove www. e pega a primeira parte do domínio
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.split('.')[0]
    except:
        return "Servidor_Desconhecido"

def main():
    # 1. Cria a pasta se não existir
    if not os.path.exists(PASTA_DESTINO):
        os.makedirs(PASTA_DESTINO)
        print(f"📂 Pasta '{PASTA_DESTINO}' criada com sucesso.")

    # 2. Carrega o JSON
    if not os.path.exists(ARQUIVO_JSON):
        print(f"❌ Erro: Arquivo '{ARQUIVO_JSON}' não encontrado.")
        return

    with open(ARQUIVO_JSON, 'r', encoding='utf-8') as f:
        try:
            lista_links = json.load(f)
        except json.JSONDecodeError:
            print("❌ Erro: O arquivo JSON está mal formatado.")
            return

    print(f"🚀 Iniciando download de {len(lista_links)} listas...\n")

    # 3. Loop de Download
    for item in lista_links:
        url = item.get("url")
        nome_custom = item.get("nome", "").strip()

        if not url:
            print("⚠️ Link vazio encontrado no JSON. Pulando...")
            continue

        # Define o nome do servidor
        if nome_custom:
            nome_servidor = nome_custom
        else:
            nome_servidor = obter_nome_servidor(url)
        
        nome_servidor = limpar_nome_arquivo(nome_servidor)

        # Define Data e Hora
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nome_arquivo = f"{nome_servidor}_{timestamp}.m3u"
        caminho_completo = os.path.join(PASTA_DESTINO, nome_arquivo)

        print(f"⬇️ Baixando: {nome_servidor}...")
        
        try:
            response = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
            response.raise_for_status() # Levanta erro se for 404, 500, etc

            # Salva o arquivo
            with open(caminho_completo, 'w', encoding='utf-8') as arquivo_saida:
                arquivo_saida.write(response.text)
            
            print(f"   ✅ Salvo em: {nome_arquivo}")

        except requests.exceptions.Timeout:
            print(f"   ❌ Erro: Tempo limite excedido para {nome_servidor}")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Erro ao baixar: {e}")
        
        print("-" * 30)

    print("\n🏁 Processo finalizado.")

if __name__ == "__main__":
    main()
