import os
import json
import shutil

# ==============================================================================
# CONFIGURAÇÕES DE PASTAS
# ==============================================================================
PASTA_TXTS = 'TXTs'
PASTA_ATUALIZACOES = os.path.join(PASTA_TXTS, 'Atualizacoes')
PASTA_DBS = os.path.join(PASTA_ATUALIZACOES, 'Bancos_de_Dados')

# Separador usado nos seus logs (copiado do seu script anterior)
SEPARADOR_LOG = "="*60

def limpar_json_duplicados():
    print(f"\n🔍 1. Verificando duplicatas nos JSONs em: {PASTA_DBS}")
    
    if not os.path.exists(PASTA_DBS):
        print("❌ Pasta de Banco de Dados não encontrada.")
        return

    arquivos_json = [f for f in os.listdir(PASTA_DBS) if f.endswith('.json')]
    total_corrigidos = 0

    for arquivo in arquivos_json:
        caminho = os.path.join(PASTA_DBS, arquivo)
        alterado = False
        
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                dados = json.load(f)

            # 1. Limpar lista de arquivos processados
            lista_arquivos = dados.get("processed_files", [])
            set_arquivos = sorted(list(set(lista_arquivos))) # Remove duplicatas e ordena
            
            if len(lista_arquivos) != len(set_arquivos):
                print(f"   🔧 {arquivo}: Removido {len(lista_arquivos) - len(set_arquivos)} arquivos duplicados no histórico.")
                dados["processed_files"] = set_arquivos
                alterado = True

            # 2. Limpar lista de itens atuais (canais)
            lista_itens = dados.get("current_items", [])
            set_itens = sorted(list(set(lista_itens)))
            
            if len(lista_itens) != len(set_itens):
                print(f"   🔧 {arquivo}: Removido {len(lista_itens) - len(set_itens)} itens duplicados na lista atual.")
                dados["current_items"] = set_itens
                alterado = True

            if alterado:
                # Cria backup antes de salvar por segurança
                shutil.copy2(caminho, caminho + ".bak_clean")
                
                with open(caminho, 'w', encoding='utf-8') as f:
                    json.dump(dados, f, indent=4, ensure_ascii=False)
                total_corrigidos += 1

        except Exception as e:
            print(f"   ❌ Erro ao ler {arquivo}: {e}")

    print(f"✅ Fim da limpeza JSON. {total_corrigidos} arquivos foram otimizados.")

def limpar_logs_duplicados():
    print(f"\n🔍 2. Verificando blocos repetidos nos LOGs em: {PASTA_ATUALIZACOES}")
    
    arquivos_log = [f for f in os.listdir(PASTA_ATUALIZACOES) if f.startswith('LOG_') and f.endswith('.txt')]
    total_logs_limpos = 0

    for arquivo in arquivos_log:
        caminho = os.path.join(PASTA_ATUALIZACOES, arquivo)
        
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                conteudo = f.read()

            # Divide o log pelos separadores de bloco
            # O split vai criar uma lista onde cada item é um bloco de registro
            blocos = conteudo.split(SEPARADOR_LOG)
            
            blocos_unicos = []
            seen = set()
            duplicatas_encontradas = 0

            for bloco in blocos:
                if not bloco.strip(): continue # Pula blocos vazios
                
                # Normaliza o bloco para comparar (remove espaços extras nas pontas)
                assinatura = bloco.strip()
                
                if assinatura in seen:
                    duplicatas_encontradas += 1
                else:
                    seen.add(assinatura)
                    blocos_unicos.append(bloco)

            if duplicatas_encontradas > 0:
                print(f"   🧹 {arquivo}: Encontrados {duplicatas_encontradas} blocos repetidos. Limpando...")
                
                # Reconstrói o arquivo
                novo_conteudo = SEPARADOR_LOG.join(blocos_unicos)
                # Adiciona o separador no início/fim se necessário para manter formatação
                if not novo_conteudo.startswith('\n'): novo_conteudo = '\n' + novo_conteudo
                
                with open(caminho, 'w', encoding='utf-8') as f:
                    f.write(novo_conteudo)
                
                total_logs_limpos += 1

        except Exception as e:
            print(f"   ❌ Erro ao processar log {arquivo}: {e}")

    print(f"✅ Fim da limpeza de Logs. {total_logs_limpos} arquivos limpos.")

if __name__ == "__main__":
    limpar_json_duplicados()
    limpar_logs_duplicados()
    print("\n🚀 Manutenção concluída.")