import os
import json
import re
import datetime
from urllib.parse import urlparse
from collections import defaultdict
import time
import shutil

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
PASTA_ALVO = 'Listas-Downloaded'
PASTA_TXTS = 'TXTs'
PASTA_ATUALIZACOES = os.path.join(PASTA_TXTS, 'Atualizacoes')
PASTA_DBS = os.path.join(PASTA_ATUALIZACOES, 'Bancos_de_Dados') # Nova pasta para DBs fracionados
ARQUIVO_RELATORIO_GERAL = os.path.join(PASTA_TXTS, 'Relatorio_Servidores.txt')

# Caminho do antigo DB gigante (para migração automática)
ARQUIVO_DB_JSON_ANTIGO = os.path.join(PASTA_ATUALIZACOES, 'db_historico.json')

# Garante que as pastas existem
os.makedirs(PASTA_ATUALIZACOES, exist_ok=True)
os.makedirs(PASTA_DBS, exist_ok=True)

# ==============================================================================
# 1. MÓDULO: RELATÓRIO GERAL DE SERVIDORES
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
# 2. MÓDULO: GERENCIAMENTO DE DADOS (DB OTIMIZADO)
# ==============================================================================

def sanitizar_nome(nome):
    """Remove caracteres inválidos para nomes de arquivos no Windows"""
    return re.sub(r'[\\/*?:"<>|]', "", nome)

def get_db_path(nome_base):
    """Retorna o caminho do arquivo JSON específico para um grupo"""
    nome_seguro = sanitizar_nome(nome_base)
    return os.path.join(PASTA_DBS, f"db_{nome_seguro}.json")

def carregar_db_grupo(nome_base):
    """Carrega apenas o pequeno DB do grupo específico"""
    caminho = get_db_path(nome_base)
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return None

def salvar_db_grupo(dados, nome_base):
    """Salva o pequeno DB do grupo específico"""
    caminho = get_db_path(nome_base)
    try:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Erro ao salvar DB de {nome_base}: {e}")

def migrar_db_gigante_se_existir():
    """
    Função crucial: Detecta se existe o DB antigo de 3GB.
    Se existir, lê ele UMA VEZ e quebra em vários arquivinhos na pasta 'Bancos_de_Dados'.
    """
    if os.path.exists(ARQUIVO_DB_JSON_ANTIGO):
        print("\n⚠️  DETECTADO BANCO DE DADOS ANTIGO (GIGANTE). INICIANDO MIGRAÇÃO...")
        print("    Isso pode levar alguns minutos, mas só precisa ser feito uma vez.")
        print("    O objetivo é dividir o arquivo de 3GB em pedaços menores para não travar mais.")
        
        try:
            with open(ARQUIVO_DB_JSON_ANTIGO, 'r', encoding='utf-8') as f:
                db_gigante = json.load(f)
            
            total_grupos = len(db_gigante)
            print(f"    📦 Extraindo dados de {total_grupos} grupos de servidores...")

            for i, (nome_base, dados) in enumerate(db_gigante.items()):
                salvar_db_grupo(dados, nome_base)
                if i > 0 and i % 50 == 0: 
                    print(f"    ... processado {i}/{total_grupos} grupos")

            print("    ✅ Migração concluída! Renomeando arquivo antigo para .backup")
            shutil.move(ARQUIVO_DB_JSON_ANTIGO, ARQUIVO_DB_JSON_ANTIGO + ".backup")
        
        except Exception as e:
            print(f"    ❌ Erro durante a migração (pode ser falta de memória RAM para abrir o arquivo gigante): {e}")
            print("    O script tentará continuar criando DBs novos do zero se necessário.")

# ==============================================================================
# 3. MÓDULO: RASTREAMENTO E LIMPEZA
# ==============================================================================

def extrair_data_nome(nome_arquivo):
    # Procura padrão [19-01-2026_07h14]
    match = re.search(r'\[(\d{2}-\d{2}-\d{4}_\d{2}h\d{2})\]', nome_arquivo)
    if match:
        return datetime.datetime.strptime(match.group(1), "%d-%m-%Y_%Hh%M")
    return datetime.datetime.min

def extrair_itens_m3u(caminho_arquivo):
    itens = set()
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        grupo_atual = "Sem Grupo"
        for line in lines:
            line = line.strip()
            if line.startswith('#EXTINF'):
                match_group = re.search(r'group-title="([^"]+)"', line)
                if match_group: grupo_atual = match_group.group(1)
                nome = line.split(',')[-1].strip()
                item_formatado = f"[{grupo_atual}] {nome}"
                itens.add(item_formatado)
    except Exception as e:
        print(f"⚠️ Erro ao ler {caminho_arquivo}: {e}")
    return itens

def processar_mudancas(arquivos):
    # Passo 1: Verifica se precisa migrar o DB antigo antes de começar
    migrar_db_gigante_se_existir()

    print("\n🔄 Iniciando verificação de mudanças e limpeza (MODO OTIMIZADO)...")
    
    # Agrupar arquivos por "Nome Base" (Nome da lista)
    grupos_listas = defaultdict(list)
    for arq in arquivos:
        if '[' in arq:
            nome_base = arq.split('[')[0].strip(' _-')
        else:
            nome_base = arq.replace('.m3u', '').strip()
        grupos_listas[nome_base].append(arq)

    count_processados = 0
    count_deletados = 0

    # Iterar sobre cada grupo (Servidor/Lista)
    # A grande vantagem aqui: Carregamos e salvamos apenas UM DB por vez.
    for nome_base, lista_arquivos in grupos_listas.items():
        
        # 1. Carrega o histórico APENAS deste grupo
        db_grupo = carregar_db_grupo(nome_base)
        
        # Se não existir, cria estrutura nova
        if db_grupo is None:
            db_grupo = {
                "processed_files": [],
                "current_items": [], 
                "first_seen": {}     
            }

        # Ordena arquivos por data
        lista_arquivos.sort(key=extrair_data_nome)
        
        # Prepara arquivo de log
        nome_log_seguro = sanitizar_nome(nome_base)
        arquivo_log_mudancas = os.path.join(PASTA_ATUALIZACOES, f"LOG_{nome_log_seguro}.txt")

        arquivo_anterior_para_deletar = None
        mudanca_no_db = False # Flag para saber se precisamos salvar no final

        for i, arquivo in enumerate(lista_arquivos):
            caminho_full = os.path.join(PASTA_ALVO, arquivo)
            
            # Se já processamos este arquivo, pulamos a análise, mas marcamos como 'anterior' para possível deleção
            if arquivo in db_grupo["processed_files"]:
                if i < len(lista_arquivos) - 1:
                    arquivo_anterior_para_deletar = caminho_full
                continue 

            print(f"   🔎 Analisando: {arquivo}...")
            data_arq_obj = extrair_data_nome(arquivo)
            data_str = data_arq_obj.strftime("%d/%m/%Y %H:%M") if data_arq_obj != datetime.datetime.min else "Data Desconhecida"

            novos_itens_set = extrair_itens_m3u(caminho_full)
            itens_anteriores = set(db_grupo["current_items"])

            adicionados = novos_itens_set - itens_anteriores
            removidos = itens_anteriores - novos_itens_set
            
            # Atualiza datas de 'primeira vez visto'
            for item in adicionados:
                if item not in db_grupo["first_seen"]:
                    db_grupo["first_seen"][item] = data_str
            
            eh_primeira_carga = len(db_grupo["processed_files"]) == 0
            
            # Escreve no Log
            with open(arquivo_log_mudancas, 'a', encoding='utf-8') as log:
                log.write(f"\n{'='*60}\n")
                log.write(f"📁 ARQUIVO: {arquivo}\n")
                log.write(f"📅 DATA: {data_str}\n")
                log.write(f"{'-'*60}\n")

                if eh_primeira_carga:
                    log.write(f"ℹ️ BASE DE DADOS INICIADA: {len(novos_itens_set)} itens.\n")
                else:
                    if not adicionados and not removidos:
                        log.write("✅ SEM MUDANÇAS NA GRADE.\n")
                    if adicionados:
                        log.write(f"🟢 ENTRARAM ({len(adicionados)}):\n")
                        for item in sorted(list(adicionados)):
                            data_visto = db_grupo["first_seen"].get(item, "Hoje")
                            log.write(f"   + {item}  | (1ª vez: {data_visto})\n")
                    if removidos:
                        log.write(f"\n🔴 SAÍRAM ({len(removidos)}):\n")
                        for item in sorted(list(removidos)):
                            data_visto = db_grupo["first_seen"].get(item, "N/A")
                            log.write(f"   - {item}  | (Visto em: {data_visto})\n")

            # Atualiza dados na memória
            db_grupo["current_items"] = list(novos_itens_set)
            db_grupo["processed_files"].append(arquivo)
            count_processados += 1
            mudanca_no_db = True

            # Lógica de Limpeza: Deletar arquivo anterior se este for mais novo
            if i > 0:
                arquivo_velho_nome = lista_arquivos[i-1]
                caminho_velho = os.path.join(PASTA_ALVO, arquivo_velho_nome)
                if os.path.exists(caminho_velho):
                    try:
                        os.remove(caminho_velho)
                        print(f"      🗑️  Versão antiga deletada: {arquivo_velho_nome}")
                        count_deletados += 1
                    except Exception as e:
                        print(f"      ⚠️  Não foi possível deletar {arquivo_velho_nome}: {e}")
            
            # Limpeza de cache pendente
            if arquivo_anterior_para_deletar and os.path.exists(arquivo_anterior_para_deletar) and arquivo_anterior_para_deletar != caminho_full:
                 try:
                    os.remove(arquivo_anterior_para_deletar)
                    print(f"      🗑️  Versão antiga (cache) deletada: {os.path.basename(arquivo_anterior_para_deletar)}")
                    count_deletados += 1
                    arquivo_anterior_para_deletar = None
                 except: pass
        
        # IMPORTANTE: Salva o DB deste grupo apenas DEPOIS de processar todos os arquivos dele
        if mudanca_no_db:
            salvar_db_grupo(db_grupo, nome_base)
            # Ao sair do loop e voltar para o início, o 'db_grupo' sai da memória (Garbage Collection)

    print(f"\n✅ Concluído! {count_processados} atualizados, {count_deletados} arquivos antigos removidos.")
    print(f"📂 Logs em: {PASTA_ATUALIZACOES}")
    print(f"📂 Bancos de dados otimizados em: {PASTA_DBS}")

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    if not os.path.exists(PASTA_ALVO):
        print(f"❌ Pasta '{PASTA_ALVO}' não encontrada.")
        return

    todos_arquivos = [f for f in os.listdir(PASTA_ALVO) if f.endswith('.m3u')]
    
    if not todos_arquivos:
        print("Nenhum arquivo .m3u encontrado.")
        return

    gerar_relatorio_servidores(todos_arquivos)
    processar_mudancas(todos_arquivos)

if __name__ == "__main__":
    main()