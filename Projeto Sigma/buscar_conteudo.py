import os
import re
import sys
import time
from datetime import datetime

# --- CONFIGURAÇÕES ---
PASTA_LISTAS = "Listas-Downloaded"
PASTA_RESULTADOS = "Resultados-Busca"

def limpar_nome_arquivo(nome):
    """Remove caracteres inválidos para nome de arquivo"""
    return re.sub(r'[<>:"/\\|?*]', '', nome).strip().replace(" ", "_")

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
    if "," in linha:
        info["nome"] = linha.split(",")[-1].strip()
    else:
        match_nome = re.search(r'tvg-name="([^"]*)"', linha)
        if match_nome:
            info["nome"] = match_nome.group(1)

    return info

def buscar_nas_listas(termo_busca):
    termo_original = termo_busca
    termo_busca = termo_busca.lower()
    
    # Verificar se a pasta de listas existe
    if not os.path.exists(PASTA_LISTAS):
        print(f"❌ A pasta '{PASTA_LISTAS}' não existe. Rode o script de download primeiro.")
        return

    # Criar pasta de resultados se não existir
    if not os.path.exists(PASTA_RESULTADOS):
        os.makedirs(PASTA_RESULTADOS)

    arquivos_m3u = [f for f in os.listdir(PASTA_LISTAS) if f.endswith('.m3u')]
    total_arquivos = len(arquivos_m3u)
    
    if not arquivos_m3u:
        print("❌ Nenhuma lista .m3u encontrada na pasta.")
        return

    print(f"\n🔎 Resultados para: '{termo_original}'\n")
    print("="*60)

    # Preparar buffer para salvar no arquivo
    conteudo_arquivo = []
    timestamp = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    conteudo_arquivo.append(f"RELATÓRIO DE BUSCA\n")
    conteudo_arquivo.append(f"Termo: {termo_original}\n")
    conteudo_arquivo.append(f"Data: {timestamp}\n")
    conteudo_arquivo.append("="*60 + "\n\n")

    total_encontrados_geral = 0

    # Loop pelos arquivos com índice (começando do 1)
    for i, arquivo in enumerate(arquivos_m3u, 1):
        caminho = os.path.join(PASTA_LISTAS, arquivo)
        
        # --- VISUALIZAÇÃO DE PROGRESSO ---
        porcentagem = int((i / total_arquivos) * 100)
        msg_status = f"⏳ [{i}/{total_arquivos}] {porcentagem}% - Lendo: {arquivo[:30]}..."
        sys.stdout.write(f"\r{msg_status:<80}") 
        sys.stdout.flush()
        # ----------------------------------

        resultados_na_lista = []
        
        try:
            with open(caminho, 'r', encoding='utf-8', errors='ignore') as f:
                for linha in f:
                    if linha.startswith("#EXTINF"):
                        # Pré-filtro rápido
                        if termo_busca in linha.lower():
                            dados = extrair_info_m3u(linha)
                            nome_conteudo = dados['nome']
                            
                            # Verificação precisa no nome
                            if termo_busca in nome_conteudo.lower():
                                resultados_na_lista.append(dados)
                            
        except Exception as e:
            sys.stdout.write(f"\n⚠️ Erro em {arquivo}: {e}\n")

        # --- EXIBIÇÃO E ARMAZENAMENTO ---
        if resultados_na_lista:
            # 1. Limpa a linha de "Buscando..." na tela
            sys.stdout.write(f"\r{' ':<80}\r") 
            
            # 2. Imprime na TELA
            print(f"📁 LISTA: {arquivo}")
            
            # 3. Adiciona no BUFFER do ARQUIVO
            conteudo_arquivo.append(f"📁 LISTA: {arquivo}\n")

            for item in resultados_na_lista:
                # Tela
                print(f"   ├─ 📺 {item['nome']}")
                print(f"   └─ 🏷️  {item['grupo']}")
                print("   " + "-" * 30)
                
                # Arquivo
                conteudo_arquivo.append(f"   ├─ [Canal/Filme]: {item['nome']}\n")
                conteudo_arquivo.append(f"   └─ [Categoria]  : {item['grupo']}\n")
                conteudo_arquivo.append("   " + "-" * 30 + "\n")
            
            # Adiciona separador entre listas no arquivo
            conteudo_arquivo.append("\n" + "="*40 + "\n\n")

            total_encontrados_geral += len(resultados_na_lista)
            print("="*60)

    # --- FINALIZAÇÃO ---
    sys.stdout.write(f"\r{' ':<80}\r") # Limpa linha final
    
    if total_encontrados_geral == 0:
        print("🚫 Nada encontrado em nenhuma lista.")
    else:
        # Salvar o arquivo TXT
        nome_arquivo_saida = f"Busca_{limpar_nome_arquivo(termo_original)}.txt"
        caminho_saida = os.path.join(PASTA_RESULTADOS, nome_arquivo_saida)
        
        # Adiciona rodapé no buffer
        conteudo_arquivo.append(f"Total encontrado: {total_encontrados_geral}\n")
        
        with open(caminho_saida, 'w', encoding='utf-8') as f:
            f.writelines(conteudo_arquivo)

        print(f"✅ Busca finalizada. Total de itens: {total_encontrados_geral}")
        print(f"📄 Relatório salvo em: {caminho_saida}")
    
    print("\n")

def main():
    while True:
        termo = input("Digite o nome do canal, filme ou série (ou 'sair'): ").strip()
        if termo.lower() in ['sair', 'exit', 'quit']:
            break
        
        if len(termo) < 2:
            print("⚠️ Digite pelo menos 2 caracteres.")
            continue
            
        buscar_nas_listas(termo)

if __name__ == "__main__":
    main()