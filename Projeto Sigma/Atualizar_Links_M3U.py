import json
import os
import re
import time
from datetime import datetime

# --- IMPORTAÇÃO DO MOTOR POTENTE ---
try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("❌ ERRO: Biblioteca 'curl_cffi' faltando.")
    print("Instale: pip install curl_cffi --user")
    exit()

# --- CONFIGURAÇÕES ---
ARQUIVO_FONTES = "fontes.json"
ARQUIVO_LOG_ERROS = "erros_mineracao.txt"

PASTA_JSON_RAW = "Dados-Brutos"
PASTA_PARCERIAS = "Parcerias"
PASTA_DOWNLOADS = "Downloads"

APPS_PARCERIA = {
    "ASSIST": "Assist_Plus_Play_Sim", "PLAY SIM": "Assist_Plus_Play_Sim",
    "LAZER": "Lazer_Play", "VIZZION": "Vizzion", "UNITV": "UniTV",
    "XCLOUD": "XCloud_TV", "P2P": "Codigos_P2P_Geral", "SMARTERS": "IPTV_Smarters_DNS",
    "XCIPTV": "XCIPTV_Dados", "EAGLE": "Eagle_TV", "FLASH": "Flash_P2P",
    "TVE": "TV_Express", "MY FAMILY": "MyFamily_Cinema", "REDPLAY": "RedPlay",
    "BTV": "BTV_Codes", "HTV": "HTV_Codes"
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

def baixar_json_blindado(url, caminho_salvar):
    """
    Usa curl_cffi para tentar POST e GET se passando por um navegador real.
    Substitui o IDM para arquivos JSON/API.
    """
    session = cffi_requests.Session()
    
    # 1. Tenta POST (Muitos servidores exigem isso)
    try:
        resp = session.post(url, impersonate="chrome120", timeout=15)
        
        # Se o servidor reclamar de Método Não Permitido (405), tentamos GET
        if resp.status_code == 405 or resp.status_code == 404:
             resp = session.get(url, impersonate="chrome120", timeout=15)
        
        if resp.status_code == 200:
            # Tenta decodificar para garantir que é JSON válido ou texto útil
            conteudo = resp.content
            
            # Salva no disco
            with open(caminho_salvar, 'wb') as f:
                f.write(conteudo)
            return True, "OK"
        else:
            return False, f"Erro HTTP {resp.status_code}"

    except Exception as e:
        # Tentativa final com GET caso o POST tenha explodido a conexão
        try:
            resp = session.get(url, impersonate="chrome120", timeout=15)
            if resp.status_code == 200:
                with open(caminho_salvar, 'wb') as f:
                    f.write(resp.content)
                return True, "OK (via GET Fallback)"
        except: pass
        
        return False, str(e)

def extrair_parcerias_e_downloads(texto_resposta, nome_exibicao):
    try:
        linhas = texto_resposta.split('\n')
        urls = re.findall(r'(https?://[^\s<>"]+)', texto_resposta)
        apks = []
        for url in urls:
            url_lower = url.lower()
            if '.apk' in url_lower or 'aftv.news' in url_lower or 'dl.ntdev' in url_lower or 'mediafire' in url_lower:
                 if url not in apks: apks.append(url)
        
        if apks:
            with open(os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt"), 'a', encoding='utf-8') as f:
                f.write(f"\n--- {nome_exibicao} ---\n")
                for l in apks: f.write(f"{l}\n")

        for linha in linhas:
            l = linha.strip()
            if not l or len(l) > 300: continue
            
            app_detectado = None
            for k, v in APPS_PARCERIA.items():
                if k in l.upper():
                    app_detectado = v
                    break
            
            if app_detectado and any(x in l.upper() for x in ["CÓDIGO", "CODIGO", "USUÁRIO", "USER", "SENHA", "PASS", "PIN", "DNS", "URL"]):
                with open(os.path.join(PASTA_PARCERIAS, f"{app_detectado}.txt"), 'a', encoding='utf-8') as f:
                    f.write(f"[{nome_exibicao}] {l}\n")
    except: pass

def verificar_validade_pelo_json(caminho_arquivo):
    if not os.path.exists(caminho_arquivo):
        return False, "Arquivo inexistente"

    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            dados = json.load(f)
        
        expires_at_str = dados.get("expiresAt")
        if not expires_at_str:
            return False, "Sem campo expiresAt"

        try:
            data_vencimento = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try: data_vencimento = datetime.strptime(expires_at_str, "%Y-%m-%dT%H:%M:%S")
            except: return False, "Formato data inválido"

        agora = datetime.now()
        if (data_vencimento - agora).total_seconds() > 60: 
            return True, str(data_vencimento - agora).split('.')[0]
        else:
            return False, "Vencido"

    except json.JSONDecodeError:
        return False, "JSON Corrompido"
    except Exception as e:
        return False, f"Erro Leitura: {str(e)}"

def main():
    for p in [PASTA_JSON_RAW, PASTA_PARCERIAS, PASTA_DOWNLOADS]:
        os.makedirs(p, exist_ok=True)

    if os.path.exists(ARQUIVO_LOG_ERROS):
        try: os.remove(ARQUIVO_LOG_ERROS)
        except: pass

    for f in os.listdir(PASTA_PARCERIAS):
        try: os.remove(os.path.join(PASTA_PARCERIAS, f))
        except: pass

    if not os.path.exists(ARQUIVO_FONTES):
        print(f"❌ '{ARQUIVO_FONTES}' não encontrado.")
        return

    with open(ARQUIVO_FONTES, 'r', encoding='utf-8') as f:
        fontes = json.load(f)

    print(f"🚀 MINERADOR V12 (CURL_CFFI POST/GET) | Fontes: {len(fontes)}")
    print(f"📥 Modo: Validação Inteligente + Download via Motor Chrome\n")
    
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

        # --- VALIDAÇÃO ---
        esta_valido, msg_validade = verificar_validade_pelo_json(caminho_json)
        
        if esta_valido:
            print(f"   ⏳ Cache válido! Vence em: {msg_validade}")
            cacheados += 1
            sucesso_leitura = True
        else:
            if msg_validade == "Vencido":
                print("   🔄 Arquivo VENCIDO. Atualizando...")
            elif msg_validade == "Arquivo inexistente":
                print("   ⬇️ Arquivo novo. Baixando...")
            else:
                print(f"   ⚠️ Revalidando ({msg_validade})...")
            
            # --- DOWNLOAD COM CURL_CFFI (Suporta POST) ---
            status, msg = baixar_json_blindado(url, caminho_json)
            
            if status:
                print("   ✅ Atualizado com sucesso!")
                atualizados += 1
                sucesso_leitura = True
            else:
                print(f"   ❌ Falha no Download: {msg}")
                registrar_erro_log(nome, url, msg)
                erros += 1

        # --- PROCESSAMENTO ---
        if sucesso_leitura and os.path.exists(caminho_json):
            try:
                with open(caminho_json, 'r', encoding='utf-8', errors='ignore') as f:
                    conteudo_para_analise = f.read()
                extrair_parcerias_e_downloads(conteudo_para_analise, nome)
            except Exception as e:
                print(f"   ⚠️ Erro ao processar JSON: {e}")

        print("-" * 40)

    print(f"\n✅ FIM DA MINERAÇÃO.")
    print(f"🆕 Atualizados: {atualizados}")
    print(f"💾 Em Cache: {cacheados}")
    print(f"❌ Falhas: {erros}")

if __name__ == "__main__":
    main()