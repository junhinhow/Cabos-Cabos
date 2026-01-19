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
    urls = re.findall(r'(https?://[^\s<>"]+)', texto_resposta)
    apks = []
    for url in urls:
        if '.apk' in url.lower() or 'aftv.news' in url.lower() or 'dl.ntdev' in url.lower():
             if url not in apks: apks.append(url)
    
    if apks:
        with open(os.path.join(PASTA_DOWNLOADS, "Links_APKs.txt"), 'a', encoding='utf-8') as f:
            f.write(f"\n--- {nome_exibicao} ---\n")
            for l in apks: f.write(f"{l}\n")

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

# --- NOVA FUNÇÃO DE VALIDAÇÃO PELO JSON ---
def verificar_validade_pelo_json(caminho_arquivo):
    """
    Abre o JSON, lê 'expiresAt' e compara com a hora atual.
    Retorna True se ainda estiver válido.
    Retorna False se venceu, não existe ou deu erro.
    """
    if not os.path.exists(caminho_arquivo):
        return False

    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            dados = json.load(f)
        
        # Procura o campo expiresAt
        expires_at_str = dados.get("expiresAt")
        
        if not expires_at_str:
            # Se não tem data de validade, consideramos inválido para forçar atualização
            return False 

        # Converte string "2026-01-19 06:00:20" para objeto datetime
        # Formato esperado: YYYY-MM-DD HH:MM:SS
        data_vencimento = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
        agora = datetime.now()

        # Calcula tempo restante
        tempo_restante = (data_vencimento - agora).total_seconds()

        if tempo_restante > 60: # Se faltar mais de 1 minuto para vencer
            # Formatamos para mostrar no log
            msg_tempo = str(data_vencimento - agora).split('.')[0]
            return True, msg_tempo
        else:
            return False, "Vencido"

    except Exception:
        # Se o arquivo estiver corrompido ou formato de data errado
        return False, "Erro Leitura"

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

    print(f"🚀 MINERADOR V10 (SMART EXPIRATION) | Fontes: {len(fontes)}")
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

        # --- NOVA LÓGICA DE VALIDAÇÃO ---
        esta_valido, msg_validade = verificar_validade_pelo_json(caminho_json)
        
        if esta_valido:
            print(f"   ⏳ Cache válido! Vence em: {msg_validade}")
            cacheados += 1
            sucesso_leitura = True
        else:
            if msg_validade == "Vencido":
                print("   🔄 Arquivo VENCIDO. Baixando atualização...")
            else:
                print("   ⬇️ Arquivo novo ou inválido. Baixando via IDM...")
            
            status, msg = baixar_json_via_idm(url, caminho_json)
            
            if status:
                print("   🕒 Aguardando IDM...")
                if esperar_download_concluir(caminho_json):
                    print("   ✅ Download concluído!")
                    atualizados += 1
                    sucesso_leitura = True
                else:
                    print("   ❌ Timeout: IDM demorou demais.")
                    registrar_erro_log(nome, url, "Timeout IDM")
                    erros += 1
            else:
                print(f"   ❌ Erro IDM: {msg}")
                erros += 1

        # Processa o arquivo (seja antigo válido ou novo baixado)
        if sucesso_leitura and os.path.exists(caminho_json):
            try:
                with open(caminho_json, 'r', encoding='utf-8', errors='ignore') as f:
                    conteudo_para_analise = f.read()
                extrair_parcerias_e_downloads(conteudo_para_analise, nome)
            except Exception as e:
                print(f"   ⚠️ Erro ao processar JSON: {e}")

        print("-" * 40)

    print(f"\n✅ FIM DA MINERAÇÃO.")
    print(f"🆕 Atualizados (Vencidos/Novos): {atualizados}")
    print(f"💾 Mantidos (Ainda no prazo): {cacheados}")
    print(f"❌ Falhas: {erros}")

if __name__ == "__main__":
    main()