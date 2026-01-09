import os
import re

# --- CONFIGURAÇÕES ---
PASTA_LISTAS = "Listas-Downloaded"

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
    # Exemplo: ...group-title="Filmes",Batman O Retorno
    if "," in linha:
        info["nome"] = linha.split(",")[-1].strip()
    else:
        # Se não achar vírgula, tenta pegar o atributo tvg-name
        match_nome = re.search(r'tvg-name="([^"]*)"', linha)
        if match_nome:
            info["nome"] = match_nome.group(1)

    return info

def buscar_nas_listas(termo_busca):
    termo_busca = termo_busca.lower()
    arquivos_encontrados = []
    
    # Verificar se a pasta existe
    if not os.path.exists(PASTA_LISTAS):
        print(f"❌ A pasta '{PASTA_LISTAS}' não existe. Rode o script de download primeiro.")
        return

    arquivos_m3u = [f for f in os.listdir(PASTA_LISTAS) if f.endswith('.m3u')]
    
    if not arquivos_m3u:
        print("❌ Nenhuma lista .m3u encontrada na pasta.")
        return

    print(f"\n🔎 Buscando por: '{termo_busca}' em {len(arquivos_m3u)} listas...\n")
    print("="*60)

    total_encontrados = 0

    for arquivo in arquivos_m3u:
        caminho = os.path.join(PASTA_LISTAS, arquivo)
        encontrou_nesta_lista = False
        
        try:
            # errors='ignore' evita travar se tiver caractere estranho na lista
            with open(caminho, 'r', encoding='utf-8', errors='ignore') as f:
                for linha in f:
                    if linha.startswith("#EXTINF"):
                        dados = extrair_info_m3u(linha)
                        nome_conteudo = dados['nome']
                        categoria = dados['grupo']

                        # Verifica se o termo está no NOME do canal/filme
                        if termo_busca in nome_conteudo.lower():
                            
                            # Se for a primeira vez que acha nesta lista, imprime o nome do arquivo
                            if not encontrou_nesta_lista:
                                print(f"📁 LISTA: {arquivo}")
                                encontrou_nesta_lista = True
                            
                            print(f"   ├─ 📺 Nome: {nome_conteudo}")
                            print(f"   └─ 🏷️  Grupo: {categoria}")
                            print("-" * 30)
                            total_encontrados += 1
                            
        except Exception as e:
            print(f"⚠️ Erro ao ler arquivo {arquivo}: {e}")

    print("="*60)
    if total_encontrados == 0:
        print("🚫 Nada encontrado.")
    else:
        print(f"✅ Busca finalizada. Total de resultados: {total_encontrados}")

def main():
    while True:
        termo = input("\nDigite o nome do canal, filme ou série (ou 'sair'): ").strip()
        if termo.lower() in ['sair', 'exit', 'quit']:
            break
        
        if len(termo) < 2:
            print("⚠️ Digite pelo menos 2 caracteres.")
            continue
            
        buscar_nas_listas(termo)

if __name__ == "__main__":
    main()