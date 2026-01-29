import os
import re
import unicodedata
import sys
import threading
import time
from datetime import datetime

# Tenta importar msvcrt para detecção de tecla (Windows), senão usa input padrão
try:
    import msvcrt
    PLATAFORMA_WIN = True
except ImportError:
    PLATAFORMA_WIN = False

# --- CONFIGURAÇÕES ---
PASTA_LISTAS = "Listas-Downloaded"
PASTA_RESULTADOS = "Resultados-Busca"

# --- CLASSE PARA GERENCIAR O TRABALHO (JOB) ---
class BuscaJob:
    def __init__(self, id_job, termo, tipo):
        self.id = id_job
        self.termo = termo
        self.tipo = tipo  # 'simples', 'detalhada' ou 'categoria'
        self.status = "Aguardando..."
        self.progresso = 0.0
        self.total_arquivos = 0
        self.arquivo_atual = ""
        self.resultado_path = ""
        self.concluido = False
        self.encontrados = 0

# Lista global de trabalhos
JOBS = []

# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto: return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower()

def limpar_nome_arquivo(nome):
    return re.sub(r'[<>:"/\\|?*]', '_', nome).strip()

def extrair_temporada(texto):
    padroes = [r'[Ss](\d+)', r'[Tt](\d+)', r'(\d+)\s*[ªa]?\s*Temporada', r'Season\s*(\d+)', r'(\d+)[xX]\d+']
    temporadas = []
    for p in padroes:
        matches = re.findall(p, texto, re.IGNORECASE)
        if matches: temporadas.extend([int(m) for m in matches])
    return max(temporadas) if temporadas else 0

def extrair_episodio(texto):
    padroes = [r'[Ee](\d+)', r'[Ee]p(?:isodio)?\s*(\d+)', r'[Cc]ap(?:itulo)?\s*(\d+)', r'\d+[xX](\d+)']
    episodios = []
    for p in padroes:
        matches = re.findall(p, texto, re.IGNORECASE)
        if matches: episodios.extend([int(m) for m in matches])
    return max(episodios) if episodios else 0

def extrair_info_m3u(linha):
    info = {"nome": "Desconhecido", "grupo": "Sem Categoria", "temporada": 0, "episodio": 0}
    
    # Extrai o grupo (categoria)
    match_grupo = re.search(r'group-title="([^"]*)"', linha)
    if match_grupo: 
        info["grupo"] = match_grupo.group(1)
    
    # Extrai o nome
    if "," in linha:
        info["nome"] = linha.split(",")[-1].strip()
    else:
        match_nome = re.search(r'tvg-name="([^"]*)"', linha)
        info["nome"] = match_nome.group(1) if match_nome else linha.replace("#EXTINF:", "").strip()
        
    info["temporada"] = extrair_temporada(info["nome"])
    info["episodio"] = extrair_episodio(info["nome"])
    return info

def verificar_episodios_faltantes(itens_temporada):
    if not itens_temporada: return []
    eps_presentes = sorted(list(set(i['episodio'] for i in itens_temporada if i['episodio'] > 0)))
    if not eps_presentes: return []
    max_ep = max(eps_presentes)
    sequencia_ideal = set(range(1, max_ep + 1))
    return sorted(list(sequencia_ideal - set(eps_presentes)))

# --- MOTOR DE BUSCA ---
def worker_busca(job):
    job.status = "Iniciando..."
    
    if not os.path.exists(PASTA_LISTAS):
        job.status = "Erro: Pasta não encontrada"
        job.concluido = True
        return

    arquivos = [f for f in os.listdir(PASTA_LISTAS) if f.endswith(('.m3u', '.m3u8', '.txt'))]
    job.total_arquivos = len(arquivos)
    
    if job.total_arquivos == 0:
        job.status = "Erro: Pasta vazia"
        job.concluido = True
        return

    termos_busca = normalizar_texto(job.termo).split()
    resultados_por_arquivo = {}

    job.status = "Rodando"
    
    for idx, arquivo in enumerate(arquivos, 1):
        job.arquivo_atual = (arquivo[:20] + "..") if len(arquivo) > 23 else arquivo
        job.progresso = (idx / job.total_arquivos) * 100
        
        caminho_lista = os.path.join(PASTA_LISTAS, arquivo)
        try:
            with open(caminho_lista, 'r', encoding='utf-8', errors='replace') as f_in:
                linhas = f_in.readlines()
            
            for linha in linhas:
                if linha.startswith("#EXTINF"):
                    # --- LÓGICA DE CATEGORIA ---
                    if job.tipo == "categoria":
                        dados = extrair_info_m3u(linha)
                        grupo_norm = normalizar_texto(dados['grupo'])
                        
                        # Verifica se termos da busca estão no NOME DA CATEGORIA
                        if all(t in grupo_norm for t in termos_busca):
                            if arquivo not in resultados_por_arquivo:
                                resultados_por_arquivo[arquivo] = {"categorias": {}}
                            
                            nome_grupo_real = dados['grupo']
                            if nome_grupo_real not in resultados_por_arquivo[arquivo]["categorias"]:
                                resultados_por_arquivo[arquivo]["categorias"][nome_grupo_real] = []
                            
                            # Agora salvamos o item inteiro, não apenas contamos
                            resultados_por_arquivo[arquivo]["categorias"][nome_grupo_real].append(dados)

                    # --- LÓGICA DE CONTEÚDO (SIMPLES/DETALHADA) ---
                    else:
                        linha_norm = normalizar_texto(linha)
                        if all(t in linha_norm for t in termos_busca):
                            dados = extrair_info_m3u(linha)
                            if arquivo not in resultados_por_arquivo:
                                resultados_por_arquivo[arquivo] = {"itens": [], "max_temp": 0, "max_ep": 0}
                            
                            resultados_por_arquivo[arquivo]["itens"].append(dados)
                            
                            if dados["temporada"] > resultados_por_arquivo[arquivo]["max_temp"]:
                                resultados_por_arquivo[arquivo]["max_temp"] = dados["temporada"]
                                resultados_por_arquivo[arquivo]["max_ep"] = dados["episodio"]
                            elif dados["temporada"] == resultados_por_arquivo[arquivo]["max_temp"]:
                                if dados["episodio"] > resultados_por_arquivo[arquivo]["max_ep"]:
                                    resultados_por_arquivo[arquivo]["max_ep"] = dados["episodio"]
        except: pass

    # Gerar Relatório
    job.status = "Gerando Relatório..."
    if resultados_por_arquivo:
        caminho = gerar_relatorio_arquivo(job.termo, resultados_por_arquivo, job.tipo)
        job.resultado_path = caminho
        
        if job.tipo == "categoria":
            total = 0
            for arq in resultados_por_arquivo.values():
                for lista_itens in arq["categorias"].values():
                    total += len(lista_itens)
            job.encontrados = total
        else:
            job.encontrados = sum(len(d['itens']) for d in resultados_por_arquivo.values())
            
        job.status = "Concluído"
    else:
        job.status = "Nada encontrado"
    
    job.concluido = True

def gerar_relatorio_arquivo(termo, resultados, tipo):
    conteudo = []
    conteudo.append("="*60)
    conteudo.append(f"          RELATÓRIO: {termo.upper()}")
    conteudo.append(f" Tipo: {tipo.title()} | Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    conteudo.append("="*60 + "\n")

    if tipo == "categoria":
        conteudo.append("📚 CONTAGEM E LISTAGEM POR CATEGORIA:\n")
        total_geral = 0
        for arquivo, dados in resultados.items():
            conteudo.append(f"📁 SERVER: {arquivo}")
            categorias = dados["categorias"]
            
            # Ordena categorias pela quantidade de itens (do maior para o menor)
            cat_ordenadas = sorted(categorias.items(), key=lambda x: len(x[1]), reverse=True)
            
            subtotal = 0
            for nome_cat, lista_itens in cat_ordenadas:
                qtd = len(lista_itens)
                conteudo.append(f"   ├─ [CATEGORIA] {nome_cat}: {qtd} obras")
                
                # Lista os itens da categoria
                # Limitamos a exibição do nome para não ficar muito longo no txt
                for item in lista_itens:
                    conteudo.append(f"   │    • {item['nome']}")
                
                conteudo.append("   │") # Espaçamento
                subtotal += qtd
            
            conteudo.append(f"   └─ SUBTOTAL SERVER: {subtotal} itens")
            conteudo.append("   " + "-"*40)
            total_geral += subtotal
        
        conteudo.append(f"\n🏆 TOTAL GERAL ENCONTRADO: {total_geral}")

    elif tipo == "simples":
        conteudo.append("📊 RESUMO (ÚLTIMO EPISÓDIO POR TEMPORADA):\n")
        for arquivo, dados in resultados.items():
            info_server = f" > [SERVER: {arquivo}]"
            if dados["max_temp"] > 0: info_server += f" -> Maior Temp: {dados['max_temp']}ª | Maior Ep: {dados['max_ep']}"
            else: info_server += " -> Conteúdo sem numeração"
            conteudo.append(info_server)
            
            itens_por_temp = {}
            for item in dados["itens"]:
                t = item["temporada"]
                if t not in itens_por_temp: itens_por_temp[t] = []
                itens_por_temp[t].append(item)
            
            temps_ordenadas = sorted(itens_por_temp.keys())
            if temps_ordenadas: conteudo.append("   " + "-"*40)
            
            for t in temps_ordenadas:
                lista_temp = itens_por_temp[t]
                ultimo = max(lista_temp, key=lambda x: x["episodio"])
                faltantes = verificar_episodios_faltantes(lista_temp)
                
                lbl_t = f"{t}ª Temp" if t > 0 else "Outros"
                lbl_e = f"Ep: {ultimo['episodio']}" if ultimo['episodio'] > 0 else ""
                
                conteudo.append(f"   ├─ {ultimo['nome']}")
                conteudo.append(f"   └─ [{lbl_t} | {lbl_e}] em {ultimo['grupo']}")
                if faltantes:
                    s_falt = str(faltantes) if len(faltantes) < 15 else f"{len(faltantes)} eps (ex: {faltantes[:5]}...)"
                    conteudo.append(f"      ⚠️  FALTAM: {s_falt}")
                conteudo.append("   " + "-"*40)
            conteudo.append("\n")

    else: # Detalhada
        conteudo.append("📝 LISTAGEM COMPLETA:\n")
        for arquivo, dados in resultados.items():
            conteudo.append(f"📁 SERVER: {arquivo}")
            for item in dados["itens"]:
                info = f" T{item['temporada']} E{item['episodio']}" if item['temporada'] > 0 else ""
                conteudo.append(f"   ├─ {item['nome']}")
                conteudo.append(f"   └─ Grupo: {item['grupo']} {info}")
                conteudo.append("   " + "-"*30)
            conteudo.append("\n")

    nome_saida = f"Busca_{tipo}_{limpar_nome_arquivo(termo)}.txt"
    caminho_full = os.path.join(PASTA_RESULTADOS, nome_saida)
    with open(caminho_full, 'w', encoding='utf-8') as f:
        f.write("\n".join(conteudo))
    return caminho_full

# --- INTERFACE E MENU ---
def monitorar_status():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("================================================================")
        print("📊 MONITOR DE BUSCAS (Pressione 'ESC' ou 'Q' para voltar ao menu)")
        print("================================================================")
        print(f"{'ID':<3} | {'TERMO':<15} | {'STATUS':<15} | {'PROGRESSO':<20} | {'INFO'}")
        print("-" * 80)

        todos_concluidos = True
        
        for job in JOBS:
            if not job.concluido: todos_concluidos = False
            
            # Barra de progresso visual
            blocos = int(job.progresso / 5) # 20 blocos total
            barra = "█" * blocos + "░" * (20 - blocos)
            perc = f"{job.progresso:.1f}%"
            
            status_cor = job.status
            if job.status == "Concluído": status_cor = "✅ Concluído"
            elif job.status == "Nada encontrado": status_cor = "❌ Vazio"
            
            print(f"{job.id:<3} | {job.termo[:15]:<15} | {status_cor:<15} | {barra} {perc} | {job.arquivo_atual}")

        print("\n" + "=" * 80)
        
        # Verificar teclas para sair (Windows)
        if PLATAFORMA_WIN:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key in [b'q', b'Q', b'\x1b']: # ESC ou Q
                    break
        else:
            print("(Pressione Ctrl+C para voltar ao menu)")
            # Linux/Mac precisa de CTRL+C neste loop simples
            try:
                time.sleep(0.5)
            except KeyboardInterrupt:
                break
            continue
            
        time.sleep(0.5)

def main():
    if not os.path.exists(PASTA_LISTAS): os.makedirs(PASTA_LISTAS)
    if not os.path.exists(PASTA_RESULTADOS): os.makedirs(PASTA_RESULTADOS)

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("==========================================")
        print("🔎 BUSCADOR SIGMA V9 (MULTI-THREAD)")
        print("==========================================")
        print("1. Nova Busca Simples (Filmes/Series)")
        print("2. Nova Busca Detalhada (Lista tudo)")
        print("3. Nova Busca por Categoria (Contagem + Lista)")
        print("4. Monitorar Status das Buscas")
        print("5. Sair")
        print("==========================================")
        
        # Mostra um mini status no rodapé do menu
        ativos = len([j for j in JOBS if not j.concluido])
        if ativos > 0:
            print(f"⚠️  Existem {ativos} buscas rodando em segundo plano.")
            print("   Selecione '4' para ver detalhes.")
            print("==========================================")

        opcao = input("Opção: ").strip()

        if opcao == "5":
            if ativos > 0:
                resp = input("Ainda há buscas rodando. Sair mesmo? (S/N): ")
                if resp.lower() != 's': continue
            sys.exit()

        elif opcao in ["1", "2", "3"]:
            tipos = {"1": "simples", "2": "detalhada", "3": "categoria"}
            tipo = tipos[opcao]
            
            termo = input(f"\n[{tipo.upper()}] Termo: ").strip()
            if termo:
                novo_job = BuscaJob(len(JOBS)+1, termo, tipo)
                JOBS.append(novo_job)
                
                # Inicia a thread
                t = threading.Thread(target=worker_busca, args=(novo_job,))
                t.daemon = True # Thread morre se fechar o programa
                t.start()
                
                print(f"✅ Busca iniciada para '{termo}'!")
                time.sleep(1) # Pausa rápida para ler
        
        elif opcao == "4":
            try:
                monitorar_status()
            except KeyboardInterrupt:
                pass # Volta pro menu
        
        else:
            print("Opção inválida.")
            time.sleep(1)

if __name__ == "__main__":
    main()