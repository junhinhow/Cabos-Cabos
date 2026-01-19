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
    padroes = [
        r'[Ss](\d+)', r'[Tt](\d+)', 
        r'(\d+)\s*[ªa]?\s*Temporada', 
        r'Season\s*(\d+)',
        r'(\d+)[xX]\d+' 
    ]
    temporadas = []
    for p in padroes:
        matches = re.findall(p, texto, re.IGNORECASE)
        if matches: temporadas.extend([int(m) for m in matches])
    return max(temporadas) if temporadas else 0

def extrair_episodio(texto):
    padroes = [
        r'[Ee](\d+)',               
        r'[Ee]p(?:isodio)?\s*(\d+)', 
        r'[Cc]ap(?:itulo)?\s*(\d+)', 
        r'\d+[xX](\d+)'              
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

def verificar_episodios_faltantes(itens_temporada):
    """Retorna uma lista de números de episódios que estão faltando na sequência."""
    if not itens_temporada: return []
    
    # Pega todos os números de episódios presentes
    eps_presentes = sorted(list(set(i['episodio'] for i in itens_temporada if i['episodio'] > 0)))
    if not eps_presentes: return []

    max_ep = max(eps_presentes)
    # Cria a sequência ideal de 1 até o máximo encontrado
    sequencia_ideal = set(range(1, max_ep + 1))
    
    faltantes = sorted(list(sequencia_ideal - set(eps_presentes)))
    return faltantes

def processar_busca(termo_original, tipo_relatorio):
    if not termo_original: return

    termos_busca = normalizar_texto(termo_original).split()
    resultados_por_arquivo = {} 

    arquivos = [f for f in os.listdir(PASTA_LISTAS) if f.endswith(('.m3u', '.m3u8', '.txt'))]
    total_arquivos = len(arquivos)

    print(f"\n🚀 Vasculhando {total_arquivos} listas por '{termo_original}'...")

    for idx, arquivo in enumerate(arquivos, 1):
        caminho_lista = os.path.join(PASTA_LISTAS, arquivo)
        try:
            with open(caminho_lista, 'r', encoding='utf-8', errors='replace') as f_in:
                linhas = f_in.readlines()
            
            nome_curto = (arquivo[:25] + "..") if len(arquivo) > 28 else arquivo
            
            for i, linha in enumerate(linhas):
                if i % 2000 == 0:
                    sys.stdout.write(f"\r⏳ [{idx}/{total_arquivos}] Lendo: {nome_curto:<30}")
                    sys.stdout.flush()

                if linha.startswith("#EXTINF"):
                    linha_norm = normalizar_texto(linha)
                    if all(t in linha_norm for t in termos_busca):
                        dados = extrair_info_m3u(linha)
                        
                        if arquivo not in resultados_por_arquivo:
                            resultados_por_arquivo[arquivo] = {"itens": [], "max_temp": 0, "max_ep": 0}
                        
                        resultados_por_arquivo[arquivo]["itens"].append(dados)
                        
                        # Atualiza Max Temp/Ep global do arquivo
                        if dados["temporada"] > resultados_por_arquivo[arquivo]["max_temp"]:
                            resultados_por_arquivo[arquivo]["max_temp"] = dados["temporada"]
                            resultados_por_arquivo[arquivo]["max_ep"] = dados["episodio"]
                        elif dados["temporada"] == resultados_por_arquivo[arquivo]["max_temp"]:
                            if dados["episodio"] > resultados_por_arquivo[arquivo]["max_ep"]:
                                resultados_por_arquivo[arquivo]["max_ep"] = dados["episodio"]

        except Exception as e: pass # Ignora erros de leitura silenciosamente para não poluir

    sys.stdout.write("\r" + " "*60 + "\r") # Limpa linha de progresso

    if not resultados_por_arquivo:
        print("❌ Nada encontrado.")
        return

    # --- GERAÇÃO DO RELATÓRIO ---
    gerar_relatorio(termo_original, resultados_por_arquivo, tipo_relatorio)

def gerar_relatorio(termo, resultados, tipo):
    conteudo = []
    conteudo.append("="*60)
    conteudo.append(f"          RELATÓRIO DE SÉRIES ({tipo.upper()})")
    conteudo.append(f" Termo: {termo}")
    conteudo.append(f" Data:  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    conteudo.append("="*60 + "\n")

    total_itens = 0

    if tipo == "simples":
        conteudo.append("📊 RESUMO INTELIGENTE (ÚLTIMO EPISÓDIO POR TEMPORADA):\n")
        
        for arquivo, dados in resultados.items():
            max_t = dados["max_temp"]
            max_e = dados["max_ep"]
            
            # Cabeçalho do Servidor
            info_server = f" > [SERVER: {arquivo}]"
            if max_t > 0:
                info_server += f" -> Maior Temp: {max_t}ª | Maior Ep: {max_e}"
            else:
                info_server += " -> Conteúdo sem numeração (Filmes/Outros)"
            
            conteudo.append(info_server)
            
            # Agrupar itens por temporada para análise
            itens_por_temp = {}
            for item in dados["itens"]:
                t = item["temporada"]
                if t not in itens_por_temp: itens_por_temp[t] = []
                itens_por_temp[t].append(item)
            
            # Exibir resumo por temporada
            temps_ordenadas = sorted(itens_por_temp.keys())
            
            if not temps_ordenadas:
                conteudo.append("   (Sem itens identificáveis)")
                conteudo.append("")
                continue

            conteudo.append("   " + "-"*40)
            
            for t in temps_ordenadas:
                lista_temp = itens_por_temp[t]
                # Pega o item com o maior número de episódio nesta temporada
                ultimo_ep_item = max(lista_temp, key=lambda x: x["episodio"])
                
                # Verifica buracos na sequência
                faltantes = verificar_episodios_faltantes(lista_temp)
                
                label_temp = f"{t}ª Temp" if t > 0 else "Outros"
                label_ep = f"Ep: {ultimo_ep_item['episodio']}" if ultimo_ep_item['episodio'] > 0 else ""
                
                conteudo.append(f"   ├─ {ultimo_ep_item['nome']}")
                conteudo.append(f"   └─ Localizado: [{label_temp} | {label_ep}] em {ultimo_ep_item['grupo']}")
                
                if faltantes:
                    # Formata a lista para não ficar gigante se faltar muitos
                    str_faltantes = str(faltantes) if len(faltantes) < 15 else f"{len(faltantes)} episódios (ex: {faltantes[:5]}...)"
                    conteudo.append(f"      ⚠️  ATENÇÃO: Faltam eps nesta sequência: {str_faltantes}")
                
                conteudo.append("   " + "-"*40)
                total_itens += len(lista_temp)
            
            conteudo.append("\n")

    elif tipo == "detalhada":
        # Formato Original: Resumo no topo + Lista completa embaixo
        conteudo.append("📊 RESUMO DE ATUALIZAÇÕES (POR SERVIDOR):")
        for arquivo, dados in resultados.items():
            if dados["max_temp"] > 0:
                resumo = f" > [SERVER: {arquivo}] -> {dados['max_temp']}ª Temp | Ep mais alto: {dados['max_ep']}"
                conteudo.append(resumo)
            else:
                conteudo.append(f" > [SERVER: {arquivo}] -> Conteúdo Único (Filme ou Sem numeração)")
        
        conteudo.append("\n" + "="*60 + "\n")
        conteudo.append("📝 LISTAGEM COMPLETA DOS ARQUIVOS ENCONTRADOS:\n")

        for arquivo, dados in resultados.items():
            conteudo.append(f"📁 LISTA: {arquivo}")
            for item in dados["itens"]:
                info_temp = f" {item['temporada']}ª Temp |" if item['temporada'] > 0 else ""
                info_ep = f" Ep: {item['episodio']}" if item['episodio'] > 0 else ""
                conteudo.append(f"   ├─ {item['nome']}")
                conteudo.append(f"   └─ Localizado: [{info_temp}{info_ep}] em {item['grupo']}")
                conteudo.append("   " + "-"*30)
            conteudo.append("\n")
            total_itens += len(dados["itens"])

    conteudo.append(f"\nFIM DO RELATÓRIO - Total de itens encontrados: {total_itens}")

    nome_saida = f"Busca_{tipo}_{limpar_nome_arquivo(termo)}.txt"
    caminho_saida = os.path.join(PASTA_RESULTADOS, nome_saida)
    
    with open(caminho_saida, 'w', encoding='utf-8') as f:
        f.write("\n".join(conteudo))

    print(f"\n✅ CONCLUÍDO! Relatório gerado: {nome_saida}")
    try: os.startfile(caminho_saida)
    except: pass

def main():
    if not os.path.exists(PASTA_LISTAS):
        print(f"❌ Pasta '{PASTA_LISTAS}' não encontrada. Crie a pasta e coloque as listas .m3u lá.")
        input("Pressione Enter para sair...")
        return

    if not os.path.exists(PASTA_RESULTADOS): os.makedirs(PASTA_RESULTADOS)

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("==========================================")
        print("🔎 BUSCADOR SIGMA V8 (Menu Interativo)")
        print("==========================================")
        print("1. Busca Simples (Resumo por Temporada + Faltantes)")
        print("2. Busca Detalhada (Lista completa de arquivos)")
        print("3. Sair")
        print("==========================================")
        
        opcao = input("Escolha uma opção: ").strip()

        if opcao == "3":
            print("Saindo...")
            break
        
        elif opcao in ["1", "2"]:
            tipo = "simples" if opcao == "1" else "detalhada"
            try:
                termo = input(f"\n[{tipo.upper()}] Digite o nome da série: ").strip()
                if termo:
                    processar_busca(termo, tipo)
                    input("\nPressione Enter para voltar ao menu...")
            except KeyboardInterrupt:
                print("\nOperação cancelada.")
        else:
            print("❌ Opção inválida.")
            import time
            time.sleep(1)

if __name__ == "__main__":
    main()