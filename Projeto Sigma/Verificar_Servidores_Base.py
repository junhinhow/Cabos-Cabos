import os
import json
import re
import datetime
from urllib.parse import urlparse
from collections import defaultdict
import time

# --- CONFIGURAÇÕES ---
PASTA_ALVO = 'Listas-Downloaded'
PASTA_TXTS = 'TXTs'
# MUDANÇA 1: Removi acentos do nome da pasta para evitar erro "Errno 22" no Windows
PASTA_ATUALIZACOES = os.path.join(PASTA_TXTS, 'Atualizacoes')
ARQUIVO_RELATORIO_GERAL = os.path.join(PASTA_TXTS, 'Relatorio_Servidores.txt')
ARQUIVO_DB_JSON = os.path.join(PASTA_ATUALIZACOES, 'db_historico.json')

# Garante que as pastas existem
os.makedirs(PASTA_ATUALIZACOES, exist_ok=True)

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
# 2. MÓDULO: RASTREAMENTO DE MUDANÇAS & LIMPEZA
# ==============================================================================

def carregar_db():
    if os.path.exists(ARQUIVO_DB_JSON):
        try:
            with open(ARQUIVO_DB_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {} 

def salvar_db(db):
    try:
        with open(ARQUIVO_DB_JSON, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Erro ao salvar DB (possível erro de caminho): {e}")

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
    print("\n🔄 Iniciando verificação de mudanças e limpeza...")
    db = carregar_db()
    
    # 1. Agrupar arquivos por "Nome Base" (tudo antes do primeiro '[')
    grupos_listas = defaultdict(list)
    for arq in arquivos:
        # MUDANÇA 2: Lógica estrita para pegar o nome base
        if '[' in arq:
            nome_base = arq.split('[')[0].strip(' _-')
        else:
            nome_base = arq.replace('.m3u', '').strip()
        
        grupos_listas[nome_base].append(arq)

    count_processados = 0
    count_deletados = 0

    for nome_base, lista_arquivos in grupos_listas.items():
        # Ordena cronologicamente (do mais antigo para o mais novo)
        lista_arquivos.sort(key=extrair_data_nome)
        
        if nome_base not in db:
            db[nome_base] = {
                "processed_files": [],
                "current_items": [], 
                "first_seen": {}     
            }

        # Nome do log baseado no servidor
        nome_log_seguro = re.sub(r'[\\/*?:"<>|]', "", nome_base) # Remove caracteres ilegais para nome de arquivo
        arquivo_log_mudancas = os.path.join(PASTA_ATUALIZACOES, f"LOG_{nome_log_seguro}.txt")

        # Mantemos o controle do arquivo anterior para poder deletá-lo após processar o novo
        arquivo_anterior_para_deletar = None

        for i, arquivo in enumerate(lista_arquivos):
            caminho_full = os.path.join(PASTA_ALVO, arquivo)
            
            # Se já processamos este arquivo exato antes, ele se torna o "anterior" (candidato a deletar se houver um mais novo)
            if arquivo in db[nome_base]["processed_files"]:
                # Verifica se não é o ÚLTIMO da lista (o mais recente a gente nunca deleta)
                if i < len(lista_arquivos) - 1:
                    arquivo_anterior_para_deletar = caminho_full
                continue 

            print(f"   🔎 Analisando: {arquivo}...")
            data_arq_obj = extrair_data_nome(arquivo)
            data_str = data_arq_obj.strftime("%d/%m/%Y %H:%M") if data_arq_obj != datetime.datetime.min else "Data Desconhecida"

            novos_itens_set = extrair_itens_m3u(caminho_full)
            itens_anteriores = set(db[nome_base]["current_items"])

            adicionados = novos_itens_set - itens_anteriores
            removidos = itens_anteriores - novos_itens_set
            
            for item in adicionados:
                if item not in db[nome_base]["first_seen"]:
                    db[nome_base]["first_seen"][item] = data_str
            
            eh_primeira_carga = len(db[nome_base]["processed_files"]) == 0
            
            # Escreve Log
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
                            data_visto = db[nome_base]["first_seen"].get(item, "Hoje")
                            log.write(f"   + {item}  | (1ª vez: {data_visto})\n")
                    if removidos:
                        log.write(f"\n🔴 SAÍRAM ({len(removidos)}):\n")
                        for item in sorted(list(removidos)):
                            data_visto = db[nome_base]["first_seen"].get(item, "N/A")
                            log.write(f"   - {item}  | (Visto em: {data_visto})\n")

            # Atualiza DB
            db[nome_base]["current_items"] = list(novos_itens_set)
            db[nome_base]["processed_files"].append(arquivo)
            count_processados += 1
            salvar_db(db)

            # MUDANÇA 3: Lógica de Exclusão do Anterior
            # Se acabamos de processar um arquivo novo com sucesso, e existe um anterior na lista (mais velho), deletamos o anterior.
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
            
            # Se tínhamos um marcado para deletar de rodadas anteriores (cache), deleta agora
            if arquivo_anterior_para_deletar and os.path.exists(arquivo_anterior_para_deletar) and arquivo_anterior_para_deletar != caminho_full:
                 try:
                    os.remove(arquivo_anterior_para_deletar)
                    print(f"      🗑️  Versão antiga (cache) deletada: {os.path.basename(arquivo_anterior_para_deletar)}")
                    count_deletados += 1
                    arquivo_anterior_para_deletar = None
                 except: pass

    print(f"\n✅ Concluído! {count_processados} atualizados, {count_deletados} arquivos antigos removidos.")
    print(f"📂 Logs em: {PASTA_ATUALIZACOES}")

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