import os
import json
import re
import datetime
from urllib.parse import urlparse
from collections import defaultdict

# --- CONFIGURAÇÕES ---
PASTA_ALVO = 'Listas-Downloaded'
PASTA_TXTS = 'TXTs'
PASTA_ATUALIZACOES = os.path.join(PASTA_TXTS, 'Atualizações')
ARQUIVO_RELATORIO_GERAL = os.path.join(PASTA_TXTS, 'Relatorio_Servidores.txt')
ARQUIVO_DB_JSON = os.path.join(PASTA_ATUALIZACOES, 'db_historico.json')

# Garante que as pastas existem
os.makedirs(PASTA_ATUALIZACOES, exist_ok=True)

# ==============================================================================
# 1. MÓDULO: RELATÓRIO GERAL DE SERVIDORES (Funcionalidade Original)
# ==============================================================================

def extrair_servidor_base(url):
    try:
        parsed = urlparse(url.strip())
        if not parsed.netloc: return None
        return f"{parsed.scheme}://{parsed.netloc}"
    except: return None

def descobrir_servidor_do_arquivo(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            for linha in f:
                linha = linha.strip()
                if linha.startswith('http'):
                    base = extrair_servidor_base(linha)
                    if base: return base
    except: return "⚠️ Erro de Leitura"
    return "⚠️ Nenhum link encontrado"

def gerar_relatorio_servidores(arquivos):
    print("📊 Gerando Relatório Geral de Servidores...")
    agrupamento = defaultdict(list)
    dados_tabela = []

    for arquivo in arquivos:
        caminho = os.path.join(PASTA_ALVO, arquivo)
        servidor = descobrir_servidor_do_arquivo(caminho)
        dados_tabela.append((arquivo, servidor))
        if "⚠️" not in servidor:
            agrupamento[servidor].append(arquivo)

    dados_tabela.sort(key=lambda x: x[0])

    with open(ARQUIVO_RELATORIO_GERAL, 'w', encoding='utf-8') as f:
        f.write(f"RELATÓRIO DE SERVIDORES - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
        f.write("="*100 + "\n")
        f.write(f"{'NOME DO ARQUIVO':<55} | {'SERVIDOR BASE'}\n")
        f.write("="*100 + "\n")
        for nome, serv in dados_tabela:
            nome_display = (nome[:52] + '..') if len(nome) > 52 else nome
            f.write(f"{nome_display:<55} | {serv}\n")
        
        f.write("\n\n" + "="*100 + "\nAGRUPAMENTO POR SERVIDOR\n" + "="*100 + "\n")
        for servidor, lista in sorted(agrupamento.items(), key=lambda x: len(x[1]), reverse=True):
            f.write(f"\n📡 {servidor} ({len(lista)} arquivos)\n")
            for arq in lista: f.write(f"   ├─ {arq}\n")

    print(f"✅ Relatório Geral salvo em: {ARQUIVO_RELATORIO_GERAL}")

# ==============================================================================
# 2. MÓDULO: RASTREAMENTO DE MUDANÇAS (Nova Funcionalidade)
# ==============================================================================

def carregar_db():
    if os.path.exists(ARQUIVO_DB_JSON):
        try:
            with open(ARQUIVO_DB_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {} # Estrutura: {'Nome_Base_Lista': {'processed_files': [], 'current_items': [], 'history_dates': {}}}

def salvar_db(db):
    with open(ARQUIVO_DB_JSON, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def extrair_data_nome(nome_arquivo):
    # Procura padrão [19-01-2026_07h14]
    match = re.search(r'\[(\d{2}-\d{2}-\d{4}_\d{2}h\d{2})\]', nome_arquivo)
    if match:
        return datetime.datetime.strptime(match.group(1), "%d-%m-%Y_%Hh%M")
    return datetime.datetime.min

def extrair_itens_m3u(caminho_arquivo):
    """Retorna um set com strings formatadas: '[Grupo] Nome do Canal'"""
    itens = set()
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        grupo_atual = "Sem Grupo"
        for line in lines:
            line = line.strip()
            if line.startswith('#EXTINF'):
                # Extrai grupo
                match_group = re.search(r'group-title="([^"]+)"', line)
                if match_group: grupo_atual = match_group.group(1)
                
                # Extrai nome (tudo após a última vírgula)
                nome = line.split(',')[-1].strip()
                
                # Chave única para comparação
                item_formatado = f"[{grupo_atual}] {nome}"
                itens.add(item_formatado)
    except Exception as e:
        print(f"Erro ao ler {caminho_arquivo}: {e}")
    return itens

def processar_mudancas(arquivos):
    print("\n🔄 Iniciando verificação de mudanças nos catálogos...")
    db = carregar_db()
    
    # 1. Agrupar arquivos por "Nome Base" (ignorando timestamp)
    grupos_listas = defaultdict(list)
    for arq in arquivos:
        # Remove o timestamp para pegar o nome base
        nome_base = re.sub(r'_\[\d{2}-\d{2}-\d{4}.*\]\.m3u', '', arq)
        grupos_listas[nome_base].append(arq)

    count_processados = 0

    for nome_base, lista_arquivos in grupos_listas.items():
        # Ordena cronologicamente (do mais antigo para o mais novo)
        lista_arquivos.sort(key=extrair_data_nome)
        
        # Inicializa DB para esta lista se não existir
        if nome_base not in db:
            db[nome_base] = {
                "processed_files": [],
                "current_items": [], # Lista do último estado
                "first_seen": {}     # Histórico { "Item": "Data" }
            }

        # Caminho do log desta lista específica
        arquivo_log_mudancas = os.path.join(PASTA_ATUALIZACOES, f"LOG_{nome_base}.txt")

        for arquivo in lista_arquivos:
            if arquivo in db[nome_base]["processed_files"]:
                continue # Já processamos este arquivo antes

            print(f"   Processando: {arquivo}...")
            caminho_full = os.path.join(PASTA_ALVO, arquivo)
            data_arq_obj = extrair_data_nome(arquivo)
            data_str = data_arq_obj.strftime("%d/%m/%Y %H:%M") if data_arq_obj != datetime.datetime.min else "Data Desconhecida"

            novos_itens_set = extrair_itens_m3u(caminho_full)
            itens_anteriores = set(db[nome_base]["current_items"])

            # Cálculos de Diferença
            adicionados = novos_itens_set - itens_anteriores
            removidos = itens_anteriores - novos_itens_set
            
            # Atualiza datas de "Primeira vez visto"
            for item in adicionados:
                if item not in db[nome_base]["first_seen"]:
                    db[nome_base]["first_seen"][item] = data_str
            
            # Se for a PRIMEIRA carga de todas, não considera como "Adicionado", apenas "Carga Inicial"
            eh_primeira_carga = len(db[nome_base]["processed_files"]) == 0
            
            # Escreve no Log TXT
            with open(arquivo_log_mudancas, 'a', encoding='utf-8') as log:
                log.write(f"\n{'='*60}\n")
                log.write(f"📁 ARQUIVO: {arquivo}\n")
                log.write(f"📅 DATA DO ARQUIVO: {data_str}\n")
                log.write(f"🔁 COMPARADO COM: Versão anterior (ou carga inicial)\n")
                log.write(f"{'-'*60}\n")

                if eh_primeira_carga:
                    log.write(f"ℹ️ CARGA INICIAL: {len(novos_itens_set)} itens identificados.\n")
                    log.write(f"   (Mudanças serão rastreadas a partir do próximo arquivo)\n")
                else:
                    if not adicionados and not removidos:
                        log.write("✅ NENHUMA ALTERAÇÃO DETECTADA NA GRADE.\n")
                    
                    if adicionados:
                        log.write(f"🟢 ENTRARAM ({len(adicionados)}):\n")
                        # Ordena para ficar bonito
                        for item in sorted(list(adicionados)):
                            data_visto = db[nome_base]["first_seen"].get(item, "Hoje")
                            log.write(f"   + {item}  | (1ª vez visto: {data_visto})\n")
                    
                    if removidos:
                        log.write(f"\n🔴 SAÍRAM ({len(removidos)}):\n")
                        for item in sorted(list(removidos)):
                            # Verifica quando foi visto pela primeira vez antes de sair
                            data_visto = db[nome_base]["first_seen"].get(item, "N/A")
                            log.write(f"   - {item}  | (Estava na lista desde: {data_visto})\n")

            # Atualiza o estado no DB
            db[nome_base]["current_items"] = list(novos_itens_set)
            db[nome_base]["processed_files"].append(arquivo)
            count_processados += 1
            
            # Salva o DB a cada arquivo para evitar perda de dados se der erro
            salvar_db(db)

    print(f"\n✅ Processamento concluído! {count_processados} novos arquivos analisados.")
    print(f"📂 Logs de atualização salvos em: {PASTA_ATUALIZACOES}")

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    if not os.path.exists(PASTA_ALVO):
        print(f"❌ Pasta '{PASTA_ALVO}' não encontrada.")
        return

    # Pega apenas arquivos m3u
    todos_arquivos = [f for f in os.listdir(PASTA_ALVO) if f.endswith('.m3u')]
    
    if not todos_arquivos:
        print("Nenhum arquivo .m3u encontrado.")
        return

    # Executa Relatório 1 (Geral)
    gerar_relatorio_servidores(todos_arquivos)
    
    # Executa Relatório 2 (Atualizações Incrementais)
    processar_mudancas(todos_arquivos)

if __name__ == "__main__":
    main()