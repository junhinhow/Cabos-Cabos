import json
import os
import glob
from datetime import datetime

# --- CONFIGURAÇÕES ---
PASTA_JSON_RAW = "Dados-Brutos"
PASTA_SAIDA = "TXTs"
NOME_ARQUIVO_FINAL = "Todas_Replies_Agrupadas.json"

def carregar_json(caminho):
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return None

def main():
    # Garante que as pastas existem
    if not os.path.exists(PASTA_JSON_RAW):
        print(f"❌ Pasta '{PASTA_JSON_RAW}' não encontrada.")
        return

    os.makedirs(PASTA_SAIDA, exist_ok=True)

    arquivos = glob.glob(os.path.join(PASTA_JSON_RAW, "*.json"))
    print(f"🚀 Iniciando agrupamento de {len(arquivos)} arquivos...")

    lista_final = []
    contador_sucesso = 0
    contador_vazio = 0

    for caminho_arquivo in arquivos:
        nome_arquivo = os.path.basename(caminho_arquivo)
        dados = carregar_json(caminho_arquivo)

        if not dados:
            continue

        reply_encontrada = None

        # Tenta encontrar o campo 'reply'
        if isinstance(dados, dict):
            reply_encontrada = dados.get("reply")
        elif isinstance(dados, list) and len(dados) > 0:
            # Se for uma lista, tenta pegar do primeiro item se for dicionário
            if isinstance(dados[0], dict):
                reply_encontrada = dados[0].get("reply")

        if reply_encontrada:
            # Adiciona à lista final com a referência de onde veio
            objeto_agrupado = {
                "origem": nome_arquivo,
                "reply": reply_encontrada
            }
            lista_final.append(objeto_agrupado)
            contador_sucesso += 1
        else:
            contador_vazio += 1

    # Salva o arquivo consolidado
    caminho_saida_completo = os.path.join(PASTA_SAIDA, NOME_ARQUIVO_FINAL)
    
    try:
        with open(caminho_saida_completo, 'w', encoding='utf-8') as f:
            json.dump(lista_final, f, indent=4, ensure_ascii=False)
        
        print(f"\n✅ Concluído!")
        print(f"📂 Arquivo salvo em: {caminho_saida_completo}")
        print(f"📝 Total de Replies encontradas: {contador_sucesso}")
        print(f"⚠️ Arquivos sem reply: {contador_vazio}")

    except Exception as e:
        print(f"❌ Erro ao salvar arquivo final: {e}")

if __name__ == "__main__":
    main()