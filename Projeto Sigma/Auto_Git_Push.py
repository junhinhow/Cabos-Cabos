import time
import subprocess
from datetime import datetime
import os

# --- CONFIGURAÇÕES ---
INTERVALO_VERIFICACAO = 10  # Segundos entre checagens
BRANCH = "main"             # Confirme se é 'main' ou 'master'

def obter_raiz_git():
    """Descobre a pasta raiz do repositório para evitar erros de caminho relativo"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], 
            capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except: pass
    return None

def verificar_e_enviar():
    try:
        # 1. Pergunta ao GIT se tem algo pendente
        result = subprocess.run(
            ["git", "status", "--porcelain"], 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='ignore'
        )
        
        mudancas = result.stdout.strip()

        if mudancas:
            # Cria lista de arquivos, ignorando linhas vazias
            lista_arquivos = [linha for linha in mudancas.split('\n') if linha.strip()]
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            print(f"\n[{timestamp}] 👁️ Git detectou {len(lista_arquivos)} alteração(ões)!")
            
            # Pausa para garantir salvamento do editor
            time.sleep(2)

            for linha in lista_arquivos:
                # O formato porcelain é "XY Caminho/Do/Arquivo"
                # Pegamos do caractere 3 para frente para ignorar o status (M, ??, etc)
                nome_bruto = linha[3:].strip()
                
                # Remove aspas duplas das pontas (Git adiciona aspas se tiver espaço no nome)
                nome_arquivo = nome_bruto.strip('"')

                print(f"🔄 Processando: {nome_arquivo}")

                try:
                    # a) Adiciona
                    subprocess.run(["git", "add", nome_arquivo], check=True)
                    
                    # b) Commita
                    msg_commit = f"Auto-Update: {os.path.basename(nome_arquivo)} | {timestamp}"
                    subprocess.run(["git", "commit", "-m", msg_commit], check=True)
                    
                    # c) Push Imediato
                    print(f"🚀 Enviando {os.path.basename(nome_arquivo)}...")
                    push_result = subprocess.run(
                        ["git", "push", "origin", BRANCH], 
                        capture_output=True, text=True
                    )

                    if push_result.returncode == 0:
                        print(f"✅ SUCESSO! Sincronizado.")
                    else:
                        print(f"⚠️ Push falhou:\n{push_result.stderr}")

                except subprocess.CalledProcessError as e:
                    print(f"❌ Erro no Git (Add/Commit): {e}")
                except Exception as e:
                    print(f"❌ Erro genérico no arquivo: {e}")

            print("-" * 40)
            return True
            
        else:
            return False

    except Exception as e:
        print(f"❌ Erro Crítico no Script: {e}")
        return False

def main():
    # --- CORREÇÃO DE DIRETÓRIO ---
    raiz_git = obter_raiz_git()
    if raiz_git:
        os.chdir(raiz_git) # Muda o script para rodar na raiz do projeto
        print(f"📂 Contexto ajustado para Raiz Git: {raiz_git}")
    else:
        print(f"⚠️ Não foi possível achar a raiz Git. Rodando em: {os.getcwd()}")

    print(f"🔭 VIGIA GIT (MODO INDIVIDUAL/CORRIGIDO) INICIADO")
    print("------------------------------------------------")

    try:
        while True:
            verificar_e_enviar()
            time.sleep(INTERVALO_VERIFICACAO)

    except KeyboardInterrupt:
        print("\n🛑 Parando script.")

if __name__ == "__main__":
    main()