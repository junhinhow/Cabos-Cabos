import os
import datetime
from urllib.parse import urlparse

# --- CONFIGURAÇÕES ---
PASTA_ALVO = 'Listas-Downloaded'  # Pasta onde estão os arquivos .m3u
ARQUIVO_SAIDA = 'Relatorio_Servidores_F.txt'
# ---------------------

def extrair_servidor_base(url):
    """
    Recebe: http://cdn.exemplo.com:8080/live/user/pass/123.ts
    Retorna: http://cdn.exemplo.com:8080
    """
    try:
        parsed = urlparse(url.strip())
        if not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"
    except:
        return None

def descobrir_servidor_do_arquivo(caminho_arquivo):
    """
    Lê o arquivo até encontrar a primeira linha de link válida.
    """
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            for linha in f:
                linha = linha.strip()
                # Ignora linhas de metadados (#) e linhas vazias
                if linha.startswith('http://') or linha.startswith('https://'):
                    base = extrair_servidor_base(linha)
                    if base:
                        return base
    except Exception as e:
        return "⚠️ Erro de Leitura"
    
    return "⚠️ Nenhum link encontrado"

def main():
    if not os.path.exists(PASTA_ALVO):
        print(f"ERRO: A pasta '{PASTA_ALVO}' não existe.")
        return

    # Lista todos os arquivos .m3u ou .m3u8
    arquivos = [f for f in os.listdir(PASTA_ALVO) if f.endswith('.m3u') or f.endswith('.m3u8')]
    
    if not arquivos:
        print(f"Nenhum arquivo .m3u encontrado em '{PASTA_ALVO}'.")
        return

    print(f"Analisando {len(arquivos)} arquivos na pasta '{PASTA_ALVO}'...")

    # Dicionário para agrupar: {'http://servidor.com': ['lista1.m3u', 'lista2.m3u']}
    agrupamento_servidores = {}
    
    # Lista para manter a ordem da tabela simples
    dados_tabela = []

    for arquivo in arquivos:
        caminho_completo = os.path.join(PASTA_ALVO, arquivo)
        servidor = descobrir_servidor_do_arquivo(caminho_completo)
        
        # Salva para a tabela geral
        dados_tabela.append((arquivo, servidor))

        # Salva para o agrupamento (se for um servidor válido)
        if "⚠️" not in servidor:
            if servidor not in agrupamento_servidores:
                agrupamento_servidores[servidor] = []
            agrupamento_servidores[servidor].append(arquivo)

    # Ordena a tabela por nome de arquivo
    dados_tabela.sort(key=lambda x: x[0])

    # --- GERANDO O RELATÓRIO TXT ---
    with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
        # Cabeçalho
        f.write(f"RELATÓRIO DE SERVIDORES IPTV - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
        f.write(f"Baseado apenas nos arquivos da pasta: {PASTA_ALVO}\n")
        f.write("="*100 + "\n")
        f.write(f"{'NOME DO ARQUIVO':<50} | {'SERVIDOR BASE IDENTIFICADO'}\n")
        f.write("="*100 + "\n")

        # Tabela Geral
        for nome_arq, serv in dados_tabela:
            # Corta o nome se for muito longo para não quebrar a tabela visualmente
            nome_display = (nome_arq[:47] + '..') if len(nome_arq) > 47 else nome_arq
            f.write(f"{nome_display:<50} | {serv}\n")

        f.write("\n\n")
        f.write("="*100 + "\n")
        f.write("RESUMO: GRUPOS POR SERVIDOR (Quem é 'clone' de quem)\n")
        f.write("="*100 + "\n")

        encontrou_grupo = False
        # Ordena os grupos por quantidade de arquivos (decrescente)
        grupos_ordenados = sorted(agrupamento_servidores.items(), key=lambda x: len(x[1]), reverse=True)

        for servidor, lista_arquivos in grupos_ordenados:
            f.write(f"\n📡 SERVIDOR: {servidor}\n")
            f.write(f"   Quantidade de listas: {len(lista_arquivos)}\n")
            for arq in lista_arquivos:
                f.write(f"   ├─ {arq}\n")
            
            if len(lista_arquivos) > 1:
                encontrou_grupo = True

        if not encontrou_grupo and not grupos_ordenados:
            f.write("\nNenhum servidor válido encontrado ou nenhum agrupamento possível.\n")

    print(f"✅ Sucesso! Relatório gerado em: {ARQUIVO_SAIDA}")

if __name__ == "__main__":
    main()