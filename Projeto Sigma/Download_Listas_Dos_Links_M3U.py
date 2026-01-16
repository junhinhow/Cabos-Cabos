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
from collections import defaultdict
import shutil

# --- CONFIGURAÇÕES ---
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_DESTINO = "Listas-Downloaded"
PASTA_PARCERIAS = "Parcerias"
PASTA_DOWNLOADS = "Downloads"
ARQUIVO_ERROS = "erros_download.txt"
ARQUIVO_ATUALIZACOES = "Atualizações.txt"
MAX_SIMULTANEOS = 5  # Slots de download
CACHE_VALIDADE_SEGUNDOS = 14400  # 4 Horas

# Dicionário de aplicativos de parceria
APPS_PARCERIA = {
    "Assist": "Assist_Plus_Play_Sim", "Play Sim": "Assist_Plus_Play_Sim",
    "Lazer": "Lazer_Play", "Vizzion": "Vizzion", "Unitv": "UniTV",
    "Xcloud": "XCloud_TV", "P2P": "Codigos_P2P_Geral", "Smarters": "IPTV_Smarters_DNS",
    "XCIPTV": "XCIPTV_Dados"
}

# Variável de controle
PARAR_EXECUCAO = False

HEADERS_FAKE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Upgrade-Insecure-Requests": "1",
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
    try:
        if not os.path.exists(caminho): 
            return False
            
        tamanho = os.path.getsize(caminho)
        if tamanho < 1000:  # Muito pequeno, deve ser erro
            return False
        
        timestamp_mod = os.path.getmtime(caminho)
        idade = time.time() - timestamp_mod
        
        return idade < CACHE_VALIDADE_SEGUNDOS
    except Exception as e:
        print(f"Erro ao verificar arquivo {caminho}: {str(e)}")
        return False

def normalizar_url(url):
    """
    Remove os parâmetros de autenticação da URL, mantendo apenas a parte relevante
    para comparação de conteúdo.
    """
    # Remove a parte do domínio e os parâmetros de autenticação
    # Mantém apenas o último segmento do caminho (ID do canal)
    match = re.search(r'/(\d+\.(ts|m3u8?))$', url)
    return match.group(1) if match else url

def parsear_m3u(caminho_arquivo):
    """
    Lê um arquivo M3U e retorna um dicionário categorizado por tipo de mídia
    """
    if not os.path.exists(caminho_arquivo):
        return {}
    
    conteudo = []
    with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
        linhas = f.readlines()
    
    current_group = "Geral"
    current_item = None
    
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        
        if not linha or linha.startswith('#EXTM3U') or linha.startswith('#EXT-X-SESSION-DATA'):
            i += 1
            continue
            
        if linha.startswith('#EXTGRP:'):
            current_group = linha.split(':', 1)[1].strip()
            i += 1
            continue
            
        if linha.startswith('#EXTINF'):
            # Extrai o nome do canal/filme/série
            name_match = re.search(r'tvg-name="([^"]+)"', linha) or re.search(r'tvg-name=([^\s]+)', linha)
            if name_match:
                name = name_match.group(1)
            else:
                # Se não encontrar tvg-name, pega o que está depois da última vírgula
                name = linha.split(',')[-1].strip()
            
            # Determina o tipo de mídia
            media_type = "Canais"
            if any(x in current_group.lower() for x in ['filme', 'filmes', 'movie', 'movies']):
                media_type = "Filmes"
            elif any(x in current_group.lower() for x in ['série', 'serie', 'series', 'shows']):
                media_type = "Séries"
            
            # Pega a próxima linha que deve ser a URL
            if i + 1 < len(linhas):
                url = linhas[i+1].strip()
                # Normaliza a URL removendo a parte de autenticação
                url_normalizada = normalizar_url(url)
                
                conteudo.append({
                    'nome': name,
                    'grupo': current_group,
                    'tipo': media_type,
                    'url_id': url_normalizada
                })
                i += 2  # Pula a linha da URL
            else:
                i += 1  # Se não tiver URL, só incrementa 1
    
    return conteudo

def comparar_listas_m3u(antigo, novo, nome_servidor):
    """
    Compara duas listas M3U e retorna as diferenças reais no conteúdo,
    ignorando mudanças apenas nos tokens de autenticação das URLs.
    """
    if not antigo:  # Se não há lista antiga, não há o que comparar
        return {}
    
    # Cria um dicionário de itens antigos usando url_id como chave
    antigo_por_url = {}
    for item in antigo:
        if 'url_id' in item:
            antigo_por_url[item['url_id']] = item
    
    # Agrupa por tipo e grupo
    atualizacoes = defaultdict(lambda: defaultdict(list))
    
    # Verifica cada item da nova lista
    for novo_item in novo:
        if 'url_id' not in novo_item:
            continue
            
        # Se o url_id não existia antes, é um item novo
        if novo_item['url_id'] not in antigo_por_url:
            atualizacoes[novo_item['tipo']][novo_item['grupo']].append(novo_item['nome'])
        else:
            # Se existia, verifica se o nome ou grupo mudaram
            antigo_item = antigo_por_url[novo_item['url_id']]
            if (antigo_item['nome'] != novo_item['nome'] or 
                antigo_item['grupo'] != novo_item['grupo'] or
                antigo_item['tipo'] != novo_item['tipo']):
                atualizacoes[novo_item['tipo']][novo_item['grupo']].append(
                    f"{antigo_item['nome']} → {novo_item['nome']}"
                )
    
    return dict(atualizacoes)

def registrar_atualizacao(nome_servidor, atualizacoes):
    """
    Registra as atualizações no arquivo de log
    """
    if not atualizacoes:
        return
    
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with open(ARQUIVO_ATUALIZACOES, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"SERVIDOR: {nome_servidor} | ATUALIZAÇÃO: {data_hora}\n")
        f.write(f"{'='*50}\n\n")
        
        for tipo, grupos in atualizacoes.items():
            f.write(f"{tipo.upper()}:\n")
            for grupo, itens in grupos.items():
                f.write(f"\n  • {grupo}:\n")
                for item in sorted(itens):
                    f.write(f"    - {item}\n")
            f.write("\n")

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

def requisicao_inteligente(url, timeout=15):
    """
    Tenta fazer uma requisição POST primeiro, depois GET se falhar.
    Retorna a resposta ou levanta uma exceção.
    """
    session = requests.Session()
    session.headers.update(HEADERS_FAKE)
    
    # Tenta POST primeiro
    try:
        resp = session.post(url, timeout=timeout, verify=False)
        if resp.status_code == 200: 
            return resp
    except Exception as e:
        pass
    
    # Tenta GET (Fallback)
    try:
        resp = session.get(url, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp
    except Exception as e:
        raise Exception(f"Falha na conexão ({str(e)})")

def extrair_parcerias_e_downloads(texto_resposta, nome_exibicao):
    """
    Extrai informações de parcerias e links de download do texto da resposta.
    """
    if not texto_resposta:
        return
        
    linhas = texto_resposta.split('\n') if isinstance(texto_resposta, str) else []
    
    # Extrai Downloads (APKs)
    urls = re.findall(r'(https?://[^\s<>\"]+)', str(texto_resposta))
    apks = []
    for url in urls:
        if ('.apk' in url.lower() or 'aftv.news' in url.lower() or 
            'dl.ntdev' in url.lower() or 'download' in url.lower()):
            if url not in apks: 
                apks.append(url)
    
    if apks:
        os.makedirs(PASTA_DOWNLOADS, exist_ok=True)
        with open(os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt"), 'a', encoding='utf-8') as f:
            f.write(f"\n--- {nome_exibicao} ---\n")
            for l in apks: 
                f.write(f"{l}\n")

    # Extrai Parcerias (Senhas)
    app_atual = None
    for linha in linhas:
        l = linha.strip()
        # Ignora linhas muito longas (provavelmente JSON ou lixo)
        if not l or len(l) > 300: 
            continue
            
        for k, v in APPS_PARCERIA.items():
            if k.upper() in l.upper():
                app_atual = v
                break
        
        if app_atual and any(x in l.upper() for x in ["CÓDIGO", "USUÁRIO", "SENHA", "PIN", "DNS", "URL"]):
            os.makedirs(PASTA_PARCERIAS, exist_ok=True)
            with open(os.path.join(PASTA_PARCERIAS, f"{app_atual}.txt"), 'a', encoding='utf-8') as f:
                f.write(f"[{nome_exibicao}] {l}\n")

def baixar_arquivo_com_progresso(url, caminho_saida, nome_exibicao, posicao_barra):
    try:
        # Usa a função de requisição inteligente
        resp = requisicao_inteligente(url)
        
        total_size = int(resp.headers.get('content-length', 0))
        if total_size > 0 and total_size < 150: 
            return False, "Arquivo suspeito (muito pequeno)"

        # Barra de progresso do slot
        desc = f"Slot {posicao_barra} | {nome_exibicao[:10]}..."
        
        with tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, 
                 desc=desc, position=posicao_barra, leave=False, ncols=100) as bar:
            
            with open(caminho_saida, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=32768):
                    if PARAR_EXECUCAO: 
                        break
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
        
        if PARAR_EXECUCAO:
            if os.path.exists(caminho_saida): 
                os.remove(caminho_saida)
            return False, "Interrompido"

        # Verifica se o arquivo baixado é válido
        if os.path.getsize(caminho_saida) < 100: 
            return False, "Arquivo vazio ou inválido"
            
        return True, "OK"
        
    except requests.exceptions.RequestException as e:
        return False, f"Erro na requisição: {str(e)}"
    except Exception as e:
        return False, f"Erro inesperado: {str(e)}"

def worker(arquivo_json, fila_posicoes):
    global PARAR_EXECUCAO
    if PARAR_EXECUCAO: 
        return "PARADO", None, None

    nome_base = os.path.splitext(arquivo_json)[0]
    caminho_json = os.path.join(PASTA_JSON_RAW, arquivo_json)
    caminho_m3u = os.path.join(PASTA_DESTINO, f"{nome_base}.m3u")
    temp_backup = None
    
    try:
        # 1. Verifica Cache (Regra 4h e Tamanho)
        if arquivo_eh_valido_e_recente(caminho_m3u):
            # Mesmo com cache válido, verifica se há atualizações
            with open(caminho_json, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            extrair_parcerias_e_downloads(json.dumps(dados), nome_base)
            return "PULADO", nome_base, "Cache válido (<4h)"
        
        # Se o arquivo M3U já existe, faz backup para comparação
        lista_antiga = {}
        if os.path.exists(caminho_m3u):
            lista_antiga = parsear_m3u(caminho_m3u)
            # Cria um backup temporário
            temp_backup = f"{caminho_m3u}.old"
            shutil.copy2(caminho_m3u, temp_backup)

        posicao = fila_posicoes.get()
        
        checar_tecla_z()
        if PARAR_EXECUCAO: 
            return "PARADO", None, None

        # Lê o arquivo JSON com tratamento de erros
        try:
            with open(caminho_json, 'r', encoding='utf-8') as f:
                dados = json.load(f)
        except json.JSONDecodeError:
            return "ERRO", nome_base, "Arquivo JSON inválido"
        
        # Extrai parcerias e downloads
        extrair_parcerias_e_downloads(json.dumps(dados), nome_base)
        
        # Tenta extrair o link M3U
        link_m3u = extrair_m3u_do_texto(json.dumps(dados))

        if link_m3u:
            sucesso, msg = baixar_arquivo_com_progresso(link_m3u, caminho_m3u, nome_base, posicao)
            
            if sucesso:
                # Se baixou com sucesso, verifica se houve atualizações
                if lista_antiga:  # Só verifica se havia uma lista antiga
                    nova_lista = parsear_m3u(caminho_m3u)
                    if nova_lista:  # Só compara se conseguiu parsear a nova lista
                        atualizacoes = comparar_listas_m3u(lista_antiga, nova_lista, nome_base)
                        if atualizacoes:
                            registrar_atualizacao(nome_base, atualizacoes)
                return "SUCESSO", nome_base, link_m3u
            else:
                # Se falhou o download, restaura o backup se existir
                if temp_backup and os.path.exists(temp_backup):
                    shutil.move(temp_backup, caminho_m3u)
                return "ERRO", nome_base, f"{msg} | Link: {link_m3u}"
        else:
            if any(x in nome_base.upper() for x in ["P2P", "APP", "PARCEIRO"]):
                return "IGNORADO", nome_base, "App/P2P"
            else:
                return "ERRO", nome_base, "Link M3U não encontrado"

    except Exception as e:
        error_msg = f"Erro inesperado: {str(e)}"
        print(f"Erro ao processar {nome_base}: {error_msg}")
        return "ERRO", nome_base, error_msg

    finally:
        # Remove o backup temporário se existir
        if temp_backup and os.path.exists(temp_backup):
            try:
                os.remove(temp_backup)
            except:
                pass
                
        # Garante que a posição seja devolvida à fila
        if 'posicao' in locals() and fila_posicoes is not None:
            fila_posicoes.put(posicao)

def main():
    # Configura o ambiente
    requests.packages.urllib3.disable_warnings()
    
    # Cria pastas necessárias
    for pasta in [PASTA_DESTINO, PASTA_PARCERIAS, PASTA_DOWNLOADS]:
        os.makedirs(pasta, exist_ok=True)
    
    # Inicializa o arquivo de erros com um cabeçalho
    if not os.path.exists(ARQUIVO_ERROS):
        with open(ARQUIVO_ERROS, 'w', encoding='utf-8') as f:
            f.write("= ERROS DE DOWNLOAD =\n")
            f.write(f"Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("="*50 + "\n\n")
    
    # Inicializa o arquivo de atualizações se não existir
    if not os.path.exists(ARQUIVO_ATUALIZACOES):
        with open(ARQUIVO_ATUALIZACOES, 'w', encoding='utf-8') as f:
            f.write("= ATUALIZAÇÕES DE LISTAS M3U =\n")
            f.write(f"Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("="*50 + "\n\n")

    # Verifica se a pasta de JSONs existe
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