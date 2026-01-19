import os
import re
import datetime

# --- CONFIGURAÇÃO ---
PASTA_ALVO = 'Listas-Downloaded'
# Padrão para identificar se já tem data: _[DD-MM-YYYY_HHhMM]
# Ex: _[18-01-2026_22h30]
PADRAO_DATA = re.compile(r'_\[\d{2}-\d{2}-\d{4}_\d{2}h\d{2}\]')

def obter_timestamp_arquivo(caminho_arquivo):
    """Pega a data de modificação do arquivo e formata"""
    timestamp = os.path.getmtime(caminho_arquivo)
    data = datetime.datetime.fromtimestamp(timestamp)
    # Formato: [18-01-2026_22h30]
    return data.strftime("[%d-%m-%Y_%Hh%M]")

def main():
    if not os.path.exists(PASTA_ALVO):
        print(f"❌ Pasta '{PASTA_ALVO}' não encontrada.")
        return

    arquivos = [f for f in os.listdir(PASTA_ALVO) if f.endswith('.m3u')]
    
    print(f"📂 Analisando {len(arquivos)} arquivos em '{PASTA_ALVO}'...\n")
    
    renomeados = 0
    ignorados = 0
    erros = 0

    for arquivo in arquivos:
        # Pula arquivos que parecem temporários
        if arquivo.endswith('.tmp') or arquivo.endswith('.temp'):
            continue

        caminho_antigo = os.path.join(PASTA_ALVO, arquivo)
        
        # 1. Verifica se já tem o timestamp no nome
        if PADRAO_DATA.search(arquivo):
            # print(f"⏭️  Ignorado (Já formatado): {arquivo}")
            ignorados += 1
            continue

        try:
            # 2. Gera o novo nome com a data real do arquivo
            timestamp_str = obter_timestamp_arquivo(caminho_antigo)
            nome_base = arquivo.replace('.m3u', '')
            
            # Remove qualquer timestamp antigo ou mal formatado se houver (opcional, mas bom pra limpeza)
            # Aqui vamos apenas adicionar ao final
            novo_nome = f"{nome_base}_{timestamp_str}.m3u"
            caminho_novo = os.path.join(PASTA_ALVO, novo_nome)

            # 3. Renomeia
            os.rename(caminho_antigo, caminho_novo)
            print(f"✅ Renomeado: {arquivo[:30]}... -> {novo_nome}")
            renomeados += 1

        except Exception as e:
            print(f"❌ Erro ao renomear '{arquivo}': {e}")
            erros += 1

    print("\n" + "="*40)
    print("RESUMO DA ORGANIZAÇÃO")
    print("="*40)
    print(f"✅ Arquivos Renomeados: {renomeados}")
    print(f"⏭️  Já estavam corretos: {ignorados}")
    print(f"❌ Erros: {erros}")
    print("="*40)

if __name__ == "__main__":
    main()