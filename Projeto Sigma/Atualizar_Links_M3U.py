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

# Pastas
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_PARCERIAS = "Parcerias"
PASTA_TXTS = "TXTs"  # Logs e Links ficam aqui

# Arquivos de Texto (Dentro da pasta TXTs)
ARQUIVO_LOG_ERROS = os.path.join(PASTA_TXTS, "erros_mineracao.txt")
ARQUIVO_LINKS_APKS = os.path.join(PASTA_TXTS, "Links_APKs.txt")

APPS_PARCERIA = {
    # --- APLICATIVOS FAMOSOS (TV BOX/ANDROID) ---
    "ASSIST": "Assist_Plus_Play_Sim", 
    "PLAY SIM": "Assist_Plus_Play_Sim",
    "LAZER": "Lazer_Play", 
    "VIZZION": "Vizzion", 
    "UNITV": "UniTV",
    "UNI TV": "UniTV",
    "XCLOUD": "XCloud_TV", 
    "P2P": "Codigos_P2P_Geral", 
    "SMARTERS": "IPTV_Smarters_DNS",
    "XCIPTV": "XCIPTV_Dados",
    "SSIPTV": "SSIPTV_Playlist",
    "NETRANGE": "NetRange",
    "CLOUDDY": "Clouddy_App",
    "IBO": "IBO_Player",
    "DUPLEX": "Duplex_Play",
    
    # --- SERVIÇOS PREMIUM ---
    "EAGLE": "Eagle_TV", 
    "FLASH": "Flash_P2P",
    "TVE": "TV_Express", 
    "TV EXPRESS": "TV_Express",
    "MY FAMILY": "MyFamily_Cinema", 
    "MFC": "MyFamily_Cinema",
    "REDPLAY": "RedPlay",
    "BTV": "BTV_Codes", 
    "HTV": "HTV_Codes",
    "YOUCINE": "YouCine",
    "BLUE": "Blue_TV",
    
    # --- SERVIDORES ESPECÍFICOS (Que apareceram nos JSONs) ---
    "UCAST": "UCast_App",
    "ALPHA": "Alpha_Master_App",
    "WAVE": "Wave_App",
    "TITÃ": "Tita_App",
    "ATENA": "Atena_App",
    "ANDRÔMEDA": "Andromeda_App",
    "SOLAR": "Solar_App",
    "FIRE": "Fire_App",
    "LUNAR": "Lunar_App",
    "GALAXY": "Galaxy_App",
    "OLYMPUS": "Olympus_App",
    "SPEED": "Speed_App",
    "SEVEN": "Seven_App",
    "SKY": "Sky_Alternative_App",
    "HADES": "Hades_App",
    "VÊNUS": "Venus_App",
    "URANO": "Urano_App",
    "K9": "K9_Play",
    "CINEMAX": "Cinemax_App",
    "GREEN": "Green_TV",
    "GTA": "GTA_Player"
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
        os.makedirs(PASTA_TXTS, exist_ok=True)
        with open(ARQUIVO_LOG_ERROS, 'a', encoding='utf-8') as f:
            f.write(msg)
    except: pass

def baixar_json_blindado(url, caminho_salvar):
    """
    Tenta POST primeiro. Se falhar com erro HTTP (400+), tenta GET.
    """
    session = cffi_requests.Session()
    
    # 1. TENTATIVA POST
    try:
        resp = session.post(url, impersonate="chrome120", timeout=20)
        
        if resp.status_code >= 400:
             raise Exception(f"POST falhou com {resp.status_code}")
        
        with open(caminho_salvar, 'wb') as f:
            f.write(resp.content)
        return True, "OK (via POST)"

    except Exception as e_post:
        # 2. TENTATIVA GET (FALLBACK)
        try:
            resp = session.get(url, impersonate="chrome120", timeout=20)
            
            if resp.status_code == 200:
                with open(caminho_salvar, 'wb') as f:
                    f.write(resp.content)
                return True, "OK (via GET Fallback)"
            else:
                return False, f"Erro Final: HTTP {resp.status_code}"
                
        except Exception as e_get:
            return False, f"Falha total: {str(e_get)}"

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
            # Salva na pasta TXTs
            with open(ARQUIVO_LINKS_APKS, 'a', encoding='utf-8') as f:
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
        str_data_formatada = data_vencimento.strftime("%d/%m/%Y %H:%M:%S")

        if (data_vencimento - agora).total_seconds() > 60: 
            return True, str_data_formatada
        else:
            return False, "Vencido"

    except json.JSONDecodeError:
        return False, "JSON Corrompido"
    except Exception as e:
        return False, f"Erro Leitura: {str(e)}"

def main():
    # Removi PASTA_DOWNLOADS da lista de criação
    for p in [PASTA_JSON_RAW, PASTA_PARCERIAS, PASTA_TXTS]:
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

    print(f"🚀 MINERADOR V15 (CLEAN) | Fontes: {len(fontes)}")
    print(f"📥 Organização: Pastas inúteis removidas.\n")
    
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
            
            status, msg = baixar_json_blindado(url, caminho_json)
            
            if status:
                print(f"   ✅ Atualizado! ({msg})")
                atualizados += 1
                sucesso_leitura = True
            else:
                print(f"   ❌ Falha no Download: {msg}")
                registrar_erro_log(nome, url, msg)
                erros += 1

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
    print(f"📂 Verifique a pasta '{PASTA_TXTS}' para logs e links.")

if __name__ == "__main__":
    main()