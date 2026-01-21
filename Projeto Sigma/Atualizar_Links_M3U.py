import json
import os
import re
import time
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- IMPORTAÇÃO DO MOTOR POTENTE ---
try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("❌ ERRO REAL: Biblioteca 'curl_cffi' faltando.")
    print("Detalhe: O Python não encontrou o módulo curl_cffi.")
    exit()

# --- IMPORTAÇÃO VISUAL (RICH) ---
# Removido o try/except para mostrar o erro real se acontecer
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console, Group # <--- Group agora vem daqui
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich import box
from rich.text import Text

# --- CONFIGURAÇÕES ---
ARQUIVO_FONTES = "fontes.json"
MAX_WORKERS = 10 

# Pastas
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_PARCERIAS = "Parcerias"
PASTA_TXTS = "TXTs"
ARQUIVO_LOG_ERROS = os.path.join(PASTA_TXTS, "erros_mineracao.txt")
ARQUIVO_LINKS_APKS = os.path.join(PASTA_TXTS, "Links_APKs.txt")

# --- CONTROLE DE THREADS E ESTADO VISUAL ---
lock_arquivo = threading.Lock()
lock_stats = threading.Lock()
lock_ui = threading.Lock() # Protege o dicionário de status da UI

# Estado Global para UI
active_tasks = {} # Armazena o que cada thread está fazendo: { "NomeFonte": "Status..." }
stats = {
    "atualizados": 0,
    "cacheados": 0,
    "erros": 0,
    "total": 0,
    "concluidos": 0
}

# --- LISTA DE APPS ---
APPS_PARCERIA = {
    "ASSIST": "Assist_Plus_Play_Sim", "PLAY SIM": "Assist_Plus_Play_Sim",
    "LAZER": "Lazer_Play", "VIZZION": "Vizzion", "UNITV": "UniTV",
    "UNI TV": "UniTV", "XCLOUD": "XCloud_TV", "P2P": "Codigos_P2P_Geral",
    "SMARTERS": "IPTV_Smarters_DNS", "XCIPTV": "XCIPTV_Dados",
    "SSIPTV": "SSIPTV_Playlist", "NETRANGE": "NetRange",
    "CLOUDDY": "Clouddy_App", "IBO": "IBO_Player", "DUPLEX": "Duplex_Play",
    "EAGLE": "Eagle_TV", "FLASH": "Flash_P2P", "TVE": "TV_Express",
    "TV EXPRESS": "TV_Express", "MY FAMILY": "MyFamily_Cinema",
    "MFC": "MyFamily_Cinema", "REDPLAY": "RedPlay", "BTV": "BTV_Codes",
    "HTV": "HTV_Codes", "YOUCINE": "YouCine", "BLUE": "Blue_TV",
    "UCAST": "UCast_App", "ALPHA": "Alpha_Master_App", "WAVE": "Wave_App",
    "TITÃ": "Tita_App", "ATENA": "Atena_App", "ANDRÔMEDA": "Andromeda_App",
    "SOLAR": "Solar_App", "FIRE": "Fire_App", "LUNAR": "Lunar_App",
    "GALAXY": "Galaxy_App", "OLYMPUS": "Olympus_App", "SPEED": "Speed_App",
    "SEVEN": "Seven_App", "SKY": "Sky_Alternative_App", "HADES": "Hades_App",
    "VÊNUS": "Venus_App", "URANO": "Urano_App", "K9": "K9_Play",
    "CINEMAX": "Cinemax_App", "GREEN": "Green_TV", "GTA": "GTA_Player"
}

# --- FUNÇÕES AUXILIARES ---

def update_ui_status(nome, status):
    """Atualiza o status de uma tarefa na UI"""
    with lock_ui:
        if status is None:
            if nome in active_tasks:
                del active_tasks[nome]
        else:
            active_tasks[nome] = status

def limpar_nome_arquivo(nome):
    try:
        nome_ascii = nome.encode('ascii', 'ignore').decode('ascii')
    except:
        nome_ascii = "Nome_Desconhecido"
    return re.sub(r'[<>:"/\\|?*]', '', nome_ascii).strip().replace(" ", "_")

def registrar_erro_log(nome, url, erro):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    msg = f"[{timestamp}] {nome} | {erro}\nLink: {url}\n{'-'*30}\n"
    with lock_arquivo:
        try:
            with open(ARQUIVO_LOG_ERROS, 'a', encoding='utf-8') as f:
                f.write(msg)
        except: pass

def baixar_json_blindado(url, caminho_salvar):
    session = cffi_requests.Session()
    try:
        resp = session.post(url, impersonate="chrome120", timeout=20)
        if resp.status_code >= 400:
             raise Exception(f"POST {resp.status_code}")
        with open(caminho_salvar, 'wb') as f: f.write(resp.content)
        return True, "OK (POST)"
    except Exception:
        try:
            resp = session.get(url, impersonate="chrome120", timeout=20)
            if resp.status_code == 200:
                with open(caminho_salvar, 'wb') as f: f.write(resp.content)
                return True, "OK (GET)"
            else: return False, f"HTTP {resp.status_code}"
        except Exception as e: return False, str(e)[:20]

def extrair_parcerias_e_downloads(texto_resposta, nome_exibicao):
    try:
        linhas = texto_resposta.split('\n')
        urls = re.findall(r'(https?://[^\s<>"]+)', texto_resposta)
        apks = [u for u in urls if any(ext in u.lower() for ext in ['.apk', 'aftv.news', 'dl.ntdev', 'mediafire'])]
        
        # Remove duplicados preservando ordem
        apks = list(dict.fromkeys(apks))

        if apks:
            with lock_arquivo:
                with open(ARQUIVO_LINKS_APKS, 'a', encoding='utf-8') as f:
                    f.write(f"\n--- {nome_exibicao} ---\n")
                    for l in apks: f.write(f"{l}\n")

        buffer_parcerias = {}
        for linha in linhas:
            l = linha.strip()
            if not l or len(l) > 300: continue
            
            app_detectado = None
            l_upper = l.upper()
            for k, v in APPS_PARCERIA.items():
                if k in l_upper:
                    app_detectado = v
                    break
            
            if app_detectado and any(x in l_upper for x in ["CÓDIGO", "CODIGO", "USUÁRIO", "USER", "SENHA", "PASS", "PIN", "DNS", "URL"]):
                if app_detectado not in buffer_parcerias: buffer_parcerias[app_detectado] = []
                buffer_parcerias[app_detectado].append(f"[{nome_exibicao}] {l}\n")
        
        if buffer_parcerias:
            with lock_arquivo:
                for app_nome, conteudos in buffer_parcerias.items():
                    with open(os.path.join(PASTA_PARCERIAS, f"{app_nome}.txt"), 'a', encoding='utf-8') as f:
                        f.writelines(conteudos)

    except Exception: pass

def verificar_validade_pelo_json(caminho_arquivo):
    if not os.path.exists(caminho_arquivo): return False, "Inexistente"
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            dados = json.load(f)
        expires_at = dados.get("expiresAt")
        if not expires_at: return False, "Sem validade"
        
        try: dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
        except: 
            try: dt = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S")
            except: return False, "Data Inválida"

        if (dt - datetime.now()).total_seconds() > 60: return True, "Válido"
        return False, "Vencido"
    except: return False, "Erro JSON"

def processar_fonte(item, progress_task_id, progress_obj):
    nome = item.get('nome', 'Sem Nome')
    url = item.get('api_url')
    
    if not url: 
        progress_obj.advance(progress_task_id)
        return

    update_ui_status(nome, "[yellow]Verificando Cache...[/]")
    
    nome_arq = f"{limpar_nome_arquivo(nome)}.json"
    caminho_json = os.path.join(PASTA_JSON_RAW, nome_arq)

    esta_valido, msg_validade = verificar_validade_pelo_json(caminho_json)
    
    sucesso_leitura = False
    
    if esta_valido:
        update_ui_status(nome, "[green]Cache OK[/]")
        time.sleep(0.3)
        with lock_stats: stats["cacheados"] += 1
        sucesso_leitura = True
    else:
        update_ui_status(nome, "[cyan]Baixando...[/]")
        status, msg = baixar_json_blindado(url, caminho_json)
        
        if status:
            update_ui_status(nome, "[bold green]Atualizado![/]")
            with lock_stats: stats["atualizados"] += 1
            sucesso_leitura = True
        else:
            update_ui_status(nome, f"[bold red]Falha: {msg}[/]")
            registrar_erro_log(nome, url, msg)
            with lock_stats: stats["erros"] += 1
            time.sleep(1)

    if sucesso_leitura and os.path.exists(caminho_json):
        update_ui_status(nome, "[magenta]Minerando...[/]")
        try:
            with open(caminho_json, 'r', encoding='utf-8', errors='ignore') as f:
                extrair_parcerias_e_downloads(f.read(), nome)
        except: pass

    update_ui_status(nome, None)
    with lock_stats: stats["concluidos"] += 1
    progress_obj.advance(progress_task_id)

# --- FUNÇÃO GERADORA DA INTERFACE ---
def gerar_dashboard(overall_progress):
    # 1. Tabela de Estatísticas
    tabela_stats = Table(box=box.SIMPLE_HEAVY, expand=True)
    tabela_stats.add_column("Total", justify="center", style="cyan")
    tabela_stats.add_column("Atualizados", justify="center", style="green")
    tabela_stats.add_column("Cache", justify="center", style="blue")
    tabela_stats.add_column("Falhas", justify="center", style="red")
    
    tabela_stats.add_row(
        str(stats["total"]),
        str(stats["atualizados"]),
        str(stats["cacheados"]),
        str(stats["erros"])
    )

    # 2. Tabela de Threads Ativas
    tabela_ativas = Table(box=box.ROUNDED, expand=True, title="[bold yellow]Requisições Ativas[/]")
    tabela_ativas.add_column("Fonte", style="bold white")
    tabela_ativas.add_column("Status", style="italic")
    
    with lock_ui:
        items_ativos = list(active_tasks.items())
        
    if not items_ativos:
        tabela_ativas.add_row("---", "[dim]Aguardando workers...[/]")
    else:
        for nome, status in items_ativos[:15]:
            tabela_ativas.add_row(nome, status)

    return Group(
        Panel(tabela_stats, title="[bold white]Estatísticas[/]", border_style="blue"),
        Panel(tabela_ativas, border_style="yellow"),
        Panel(overall_progress, title="Progresso Geral", border_style="green")
    )

def main():
    # Setup Pastas
    for p in [PASTA_JSON_RAW, PASTA_PARCERIAS, PASTA_TXTS]:
        os.makedirs(p, exist_ok=True)

    # Limpeza
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
    
    stats["total"] = len(fontes)
    
    overall_progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        expand=True
    )
    task_id = overall_progress.add_task("[green]Processando Fontes...", total=len(fontes))

    # --- EXECUÇÃO ---
    start_time = time.time()
    
    with Live(gerar_dashboard(overall_progress), refresh_per_second=10) as live:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for item in fontes:
                futures.append(executor.submit(processar_fonte, item, task_id, overall_progress))
            
            while stats["concluidos"] < stats["total"]:
                live.update(gerar_dashboard(overall_progress))
                time.sleep(0.1)
                
            for f in as_completed(futures):
                pass
            
            live.update(gerar_dashboard(overall_progress))

    tempo_total = time.time() - start_time
    
    print("\n")
    console = Console()
    console.print(f"[bold green]✅ FIM DA MINERAÇÃO em {tempo_total:.2f} segundos.[/]")
    console.print(f"📂 Resultados salvos em: [bold]{PASTA_PARCERIAS}[/]")

if __name__ == "__main__":
    main()