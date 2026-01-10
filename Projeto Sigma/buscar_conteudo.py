import os
import re
import unicodedata
import sys
import time
from datetime import datetime

# --- CONFIGURAÇÕES ---
PASTA_LISTAS = "Listas-Downloaded"
PASTA_RESULTADOS = "Resultados-Busca"

def normalizar_texto(texto):
    if not texto: return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower()

def limpar_nome_arquivo(nome):
    return re.sub(r'[<>:"/\\|?*]', '_', nome).strip()

def extrair_info_m3u(linha):
    """
    Tenta extrair o nome do canal/filme e o grupo (categoria) da linha #EXTINF.
    """
    info = {
        "nome": "Desconhecido",
        "grupo": "Sem Categoria"
    }

    # 1. Tentar pegar o 'group-title' (Categoria)
    match_grupo = re.search(r'group-title="([^"]*)"', linha)
    if match_grupo:
        info["grupo"] = match_grupo.group(1)
    
    # 2. Tentar pegar o nome de exibição (tudo após a última vírgula)
    # A maioria das listas segue o padrão: ...tvg-logo="url",Nome do Canal
    if "," in linha:
        info["nome"] = linha.split(",")[-1].strip()
    else:
        # Fallback se não tiver virgula, tenta pegar tvg-name
        match_nome = re.search(r'tvg-name="([^"]*)"', linha)
        if match_nome:
            info["nome"] = match_nome.group(1)
        else:
            # Se não conseguir nada, usa a linha inteira (limpando o #EXTINF)
            info["nome"] = linha.replace("#EXTINF:", "").strip()

    return info

def main():
    if not os.path.exists(PASTA_LISTAS):
        print(f"❌ Pasta '{PASTA_LISTAS}' não encontrada.")
        return

    if not os.path.exists(PASTA_RESULTADOS):
        os.makedirs(PASTA_RESULTADOS)

    print("🔎 BUSCADOR SIGMA V5 (Layout Formatado)")
    try:
        termo_original = input("\nDigite o nome do filme/série: ").strip()
    except KeyboardInterrupt:
        return
    
    if not termo_original: return

    termos_busca = normalizar_texto(termo_original).split()
    
    # Prepara o buffer de escrita (vamos montar o texto primeiro)
    conteudo_arquivo = []
    conteudo_arquivo.append("RELATÓRIO DE BUSCA\n")
    conteudo_arquivo.append(f"Termo: {termo_original}\n")
    conteudo_arquivo.append(f"Data: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}\n")
    conteudo_arquivo.append("="*60 + "\n\n")

    arquivos = [f for f in os.listdir(PASTA_LISTAS) if f.endswith(('.m3u', '.m3u8', '.txt'))]
    total_arquivos = len(arquivos)

    print(f"\n🚀 Buscando em {total_arquivos} listas...")
    print("-" * 60)

    total_encontrados_geral = 0

    for idx, arquivo in enumerate(arquivos, 1):
        caminho_lista = os.path.join(PASTA_LISTAS, arquivo)
        resultados_na_lista = [] # Lista de dicionários {'nome': 'X', 'grupo': 'Y'}
        
        try:
            with open(caminho_lista, 'r', encoding='utf-8', errors='replace') as f_in:
                linhas = f_in.readlines()
            
            total_linhas = len(linhas)
            nome_curto = arquivo[:17] + "..." if len(arquivo) > 20 else arquivo
            
            # Loop de busca
            i = 0
            while i < total_linhas:
                # Visual
                if i % 3000 == 0 or i == total_linhas - 1:
                    pct = int((i / total_linhas) * 100) if total_linhas > 0 else 100
                    msg = f"\r⏳ [{idx}/{total_arquivos}] {nome_curto} | {pct}% "
                    sys.stdout.write(msg)
                    sys.stdout.flush()

                linha = linhas[i].strip()
                
                if linha.startswith("#EXTINF"):
                    linha_norm = normalizar_texto(linha)
                    
                    if all(t in linha_norm for t in termos_busca):
                        # Se achou, extrai os dados bonitinhos
                        dados_extraidos = extrair_info_m3u(linha)
                        resultados_na_lista.append(dados_extraidos)
                i += 1
            
            # Limpa linha visual
            sys.stdout.write("\r" + " " * 65 + "\r")
            sys.stdout.flush()

            # Se encontrou algo nesta lista, formata e guarda
            if resultados_na_lista:
                print(f"✅ {len(resultados_na_lista):02d} itens em: {arquivo}")
                
                conteudo_arquivo.append(f"📁 LISTA: {arquivo}\n")
                for item in resultados_na_lista:
                    conteudo_arquivo.append(f"   ├─ [Canal/Filme]: {item['nome']}\n")
                    conteudo_arquivo.append(f"   └─ [Categoria]  : {item['grupo']}\n")
                    conteudo_arquivo.append("   " + "-" * 30 + "\n")
                
                # Adiciona separador entre listas no arquivo
                conteudo_arquivo.append("\n" + "="*40 + "\n\n")

                total_encontrados_geral += len(resultados_na_lista)

        except Exception as e:
            sys.stdout.write("\r" + " " * 65 + "\r")
            print(f"⚠️ Erro em {arquivo}: {e}")

    # --- FINALIZAÇÃO ---
    print("-" * 60)
    
    if total_encontrados_geral == 0:
        print("❌ Nada encontrado em nenhuma lista.")
    else:
        # Salvar o arquivo TXT
        nome_arquivo_saida = f"Busca_{limpar_nome_arquivo(termo_original)}.txt"
        caminho_saida = os.path.join(PASTA_RESULTADOS, nome_arquivo_saida)
        
        # Adiciona rodapé no buffer
        conteudo_arquivo.append(f"Total encontrado: {total_encontrados_geral}\n")
        
        with open(caminho_saida, 'w', encoding='utf-8') as f:
            f.writelines(conteudo_arquivo)

        print(f"🎉 BUSCA CONCLUÍDA! Total de itens: {total_encontrados_geral}")
        print(f"📄 Relatório salvo em: {caminho_saida}")
        try: os.startfile(caminho_saida) 
        except: pass

if __name__ == "__main__":
    main()