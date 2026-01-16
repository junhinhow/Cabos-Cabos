import os
import re
import unicodedata
import sys
from datetime import datetime

# --- CONFIGURAÇÕES ---
PASTA_LISTAS = "Listas-Downloaded"
PASTA_RESULTADOS = "Resultados-Busca"

def normalizar_texto(texto):
    if not texto: return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower()

def limpar_nome_arquivo(nome):
    return re.sub(r'[<>:"/\\|?*]', '_', nome).strip()

def extrair_temporada(texto):
    """Detecta S01, T05, 2ª Temporada, Season 3, 1x05, etc."""
    padroes = [
        r'[Ss](\d+)', r'[Tt](\d+)', 
        r'(\d+)\s*[ªa]?\s*Temporada', 
        r'Season\s*(\d+)',
        r'(\d+)[xX]\d+' # Captura o '1' de 1x05
    ]
    temporadas = []
    for p in padroes:
        matches = re.findall(p, texto, re.IGNORECASE)
        if matches: temporadas.extend([int(m) for m in matches])
    return max(temporadas) if temporadas else 0

def extrair_episodio(texto):
    """Detecta E01, Ep 05, Capitulo 10, 1x05, etc."""
    padroes = [
        r'[Ee](\d+)',               # E01, e05
        r'[Ee]p(?:isodio)?\s*(\d+)', # Ep 01, Episodio 10
        r'[Cc]ap(?:itulo)?\s*(\d+)', # Cap 01, Capitulo 05
        r'\d+[xX](\d+)'              # Captura o '05' de 1x05
    ]
    episodios = []
    for p in padroes:
        matches = re.findall(p, texto, re.IGNORECASE)
        if matches: episodios.extend([int(m) for m in matches])
    return max(episodios) if episodios else 0

def extrair_info_m3u(linha):
    info = {"nome": "Desconhecido", "grupo": "Sem Categoria", "temporada": 0, "episodio": 0}
    
    match_grupo = re.search(r'group-title="([^"]*)"', linha)
    if match_grupo: info["grupo"] = match_grupo.group(1)
    
    if "," in linha:
        info["nome"] = linha.split(",")[-1].strip()
    else:
        match_nome = re.search(r'tvg-name="([^"]*)"', linha)
        info["nome"] = match_nome.group(1) if match_nome else linha.replace("#EXTINF:", "").strip()

    info["temporada"] = extrair_temporada(info["nome"])
    info["episodio"] = extrair_episodio(info["nome"])
    return info

def main():
    if not os.path.exists(PASTA_LISTAS):
        print(f"❌ Pasta '{PASTA_LISTAS}' não encontrada.")
        return

    if not os.path.exists(PASTA_RESULTADOS): os.makedirs(PASTA_RESULTADOS)

    print("🔎 BUSCADOR SIGMA V7 (Analista de Séries e Episódios)")
    try:
        termo_original = input("\nDigite o nome da série: ").strip()
    except KeyboardInterrupt: return
    
    if not termo_original: return

    termos_busca = normalizar_texto(termo_original).split()
    resultados_por_arquivo = {} 

    arquivos = [f for f in os.listdir(PASTA_LISTAS) if f.endswith(('.m3u', '.m3u8', '.txt'))]
    total_arquivos = len(arquivos)

    print(f"\n🚀 Vasculhando {total_arquivos} listas...")

    for idx, arquivo in enumerate(arquivos, 1):
        caminho_lista = os.path.join(PASTA_LISTAS, arquivo)
        try:
            with open(caminho_lista, 'r', encoding='utf-8', errors='replace') as f_in:
                linhas = f_in.readlines()
            
            nome_curto = (arquivo[:17] + "..") if len(arquivo) > 20 else arquivo
            
            for i, linha in enumerate(linhas):
                if i % 5000 == 0:
                    sys.stdout.write(f"\r⏳ [{idx}/{total_arquivos}] Analisando: {nome_curto} ")
                    sys.stdout.flush()

                if linha.startswith("#EXTINF"):
                    linha_norm = normalizar_texto(linha)
                    if all(t in linha_norm for t in termos_busca):
                        dados = extrair_info_m3u(linha)
                        
                        if arquivo not in resultados_por_arquivo:
                            resultados_por_arquivo[arquivo] = {"itens": [], "max_temp": 0, "max_ep": 0}
                        
                        resultados_por_arquivo[arquivo]["itens"].append(dados)
                        
                        # Lógica para encontrar o MAIS ATUAL (Maior temp e maior ep daquela temp)
                        if dados["temporada"] > resultados_por_arquivo[arquivo]["max_temp"]:
                            resultados_por_arquivo[arquivo]["max_temp"] = dados["temporada"]
                            resultados_por_arquivo[arquivo]["max_ep"] = dados["episodio"]
                        elif dados["temporada"] == resultados_por_arquivo[arquivo]["max_temp"]:
                            if dados["episodio"] > resultados_por_arquivo[arquivo]["max_ep"]:
                                resultados_por_arquivo[arquivo]["max_ep"] = dados["episodio"]

        except Exception as e: print(f"\n⚠️ Erro em {arquivo}: {e}")

    if not resultados_por_arquivo:
        print("\n❌ Nada encontrado.")
        return

    conteudo_txt = []
    conteudo_txt.append("============================================================")
    conteudo_txt.append("          RELATÓRIO DE SÉRIES: TEMPORADAS E EPISÓDIOS")
    conteudo_txt.append(f" Termo: {termo_original}")
    conteudo_txt.append(f" Data:  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    conteudo_txt.append("============================================================\n")

    conteudo_txt.append("📊 RESUMO DE ATUALIZAÇÕES (POR SERVIDOR):")
    for arquivo, dados in resultados_por_arquivo.items():
        if dados["max_temp"] > 0:
            resumo = f" > [SERVER: {arquivo}] -> {dados['max_temp']}ª Temp | Ep mais alto: {dados['max_ep']}"
            conteudo_txt.append(resumo)
        else:
            conteudo_txt.append(f" > [SERVER: {arquivo}] -> Conteúdo Único (Filme ou Sem numeração)")
    
    conteudo_txt.append("\n" + "="*60 + "\n")
    conteudo_txt.append("📝 LISTAGEM COMPLETA DOS ARQUIVOS ENCONTRADOS:\n")

    total_geral = 0
    for arquivo, dados in resultados_por_arquivo.items():
        conteudo_txt.append(f"📁 LISTA: {arquivo}")
        for item in dados["itens"]:
            info_temp = f" {item['temporada']}ª Temp |" if item['temporada'] > 0 else ""
            info_ep = f" Ep: {item['episodio']}" if item['episodio'] > 0 else ""
            conteudo_txt.append(f"   ├─ {item['nome']}")
            conteudo_txt.append(f"   └─ Localizado: [{info_temp}{info_ep}] em {item['grupo']}")
            conteudo_txt.append("   " + "-"*30)
        conteudo_txt.append("\n")
        total_geral += len(dados["itens"])

    conteudo_txt.append(f"\nFIM DO RELATÓRIO - Total de links: {total_geral}")

    nome_saida = f"Busca_{limpar_nome_arquivo(termo_original)}.txt"
    caminho_saida = os.path.join(PASTA_RESULTADOS, nome_saida)
    
    with open(caminho_saida, 'w', encoding='utf-8') as f:
        f.write("\n".join(conteudo_txt))

    print(f"\n\n✅ CONCLUÍDO! Total de itens: {total_geral}")
    print(f"📄 Relatório gerado: {caminho_saida}")
    try: os.startfile(caminho_saida)
    except: pass

if __name__ == "__main__":
    main()