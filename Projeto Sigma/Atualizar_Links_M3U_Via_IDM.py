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

# ✅ SEU CAMINHO DO IDM
CAMINHO_IDM = r"D:\Program Files (x86)\Internet Download Manager\IDMan.exe"

# Timeout para o IDM baixar (segundos)
TIMEOUT_DOWNLOAD_IDM = 60 

# Lista expandida de parcerias
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
        with open(ARQUIVO_LOG_ERROS, 'a', encoding='utf-8') as f:
            f.write(msg)
    except: pass

def baixar_json_via_idm(url, caminho_completo):
    """Envia o comando para o IDM baixar o JSON"""
    if not os.path.exists(CAMINHO_IDM):
        return False, "IDM não encontrado"

    if os.path.exists(caminho_completo):
        try: os.remove(caminho_completo)
        except: pass

    pasta_absoluta = os.path.abspath(os.path.dirname(caminho_completo))
    nome_arquivo = os.path.basename(caminho_completo)

    try:
        cmd = [
            CAMINHO_IDM,
            '/d', url,
            '/p', pasta_absoluta,
            '/f', nome_arquivo,
            '/n',
            '/a'
        ]
        subprocess.run(cmd, check=True)
        # Tenta iniciar a fila logo em seguida
        subprocess.run([CAMINHO_IDM, '/s'], check=False)
        return True, "Enviado ao IDM"
    except Exception as e:
        return False, str(e)

def esperar_download_concluir(caminho_arquivo):
    inicio = time.time()
    while True:
        if os.path.exists(caminho_arquivo) and os.path.getsize(caminho_arquivo) > 0:
            time.sleep(0.5)
            return True
        if time.time() - inicio > TIMEOUT_DOWNLOAD_IDM:
            return False
        time.sleep(1)

def extrair_parcerias_e_downloads(texto_resposta, nome_exibicao):
    linhas = texto_resposta.split('\n')
    
    # Extração de APKs
    urls = re.findall(r'(https?://[^\s<>"]+)', texto_resposta)
    apks = []
    for url in urls:
        url_lower = url.lower()
        if '.apk' in url_lower or 'aftv.news' in url_lower or 'dl.ntdev' in url_lower or 'mediafire' in url_lower:
             if url not in apks: apks.append(url)
    
    if apks:
        try:
            with open(os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt"), 'a', encoding='utf-8') as f:
                f.write(f"\n--- {nome_exibicao} ---\n")
                for l in apks: f.write(f"{l}\n")
        except: pass

    # Extração de Parcerias
    for linha in linhas:
        l = linha.strip()
        if not l or len(l) > 300: continue
        
        app_detectado = None
        
        # Verifica se alguma chave do dicionário está na linha
        for k, v in APPS_PARCERIA.items():
            if k in l.upper():
                app_detectado = v
                break
        
        # Se achou o nome do app E palavras chave de credencial
        if app_detectado and any(x in l.upper() for x in ["CÓDIGO", "CODIGO", "USUÁRIO", "USER", "SENHA", "PASS", "PIN", "DNS", "URL"]):
            try:
                with open(os.path.join(PASTA_PARCERIAS, f"{app_detectado}.txt"), 'a', encoding='utf-8') as f:
                    f.write(f"[{nome_exibicao}] {l}\n")
            except: pass

# --- FUNÇÃO CORRIGIDA ---
def verificar_validade_pelo_json(caminho_arquivo):
    """
    Retorna SEMPRE uma tupla (bool, str).
    """
    if not os.path.exists(caminho_arquivo):
        return False, "Arquivo inexistente" # CORRIGIDO: Retorna tupla

    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            dados = json.load(f)
        
        expires_at_str = dados.get("expiresAt")
        
        if not expires_at_str:
            return False, "Sem campo expiresAt" # CORRIGIDO: Retorna tupla

        # Tenta converter a data
        try:
            data_vencimento = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Tenta formato alternativo (com T) caso apareça
            try:
                 data_vencimento = datetime.strptime(expires_at_str, "%Y-%m-%dT%H:%M:%S")
            except:
                 return False, "Formato data inválido"

        agora = datetime.now()
        tempo_restante = (data_vencimento - agora).total_seconds()

        if tempo_restante > 60: 
            msg_tempo = str(data_vencimento - agora).split('.')[0]
            return True, msg_tempo
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

    # Limpa arquivos de parcerias antigos para não duplicar
    for f in os.listdir(PASTA_PARCERIAS):
        try: os.remove(os.path.join(PASTA_PARCERIAS, f))
        except: pass

    if not os.path.exists(ARQUIVO_FONTES):
        print(f"❌ '{ARQUIVO_FONTES}' não encontrado.")
        return

    with open(ARQUIVO_FONTES, 'r', encoding='utf-8') as f:
        fontes = json.load(f)

    print(f"🚀 MINERADOR V11 (BUGFIXED) | Fontes: {len(fontes)}")
    print(f"📥 Modo: Validação via 'expiresAt' do JSON\n")
    
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

        # Verifica validade
        esta_valido, msg_validade = verificar_validade_pelo_json(caminho_json)
        
        if esta_valido:
            print(f"   ⏳ Cache válido! Vence em: {msg_validade}")
            cacheados += 1
            sucesso_leitura = True
        else:
            if msg_validade == "Vencido":
                print("   🔄 Arquivo VENCIDO. Baixando atualização...")
            elif msg_validade == "Arquivo inexistente":
                print("   ⬇️ Arquivo novo. Baixando via IDM...")
            else:
                print(f"   ⚠️ Revalidando ({msg_validade}). Baixando novo...")
            
            status, msg = baixar_json_via_idm(url, caminho_json)
            
            if status:
                print("   🕒 Aguardando IDM...")
                if esperar_download_concluir(caminho_json):
                    print("   ✅ Download concluído!")
                    atualizados += 1
                    sucesso_leitura = True
                else:
                    print("   ❌ Timeout: IDM demorou ou link off.")
                    registrar_erro_log(nome, url, "Timeout IDM")
                    erros += 1
            else:
                print(f"   ❌ Erro IDM: {msg}")
                erros += 1

        # Processamento
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