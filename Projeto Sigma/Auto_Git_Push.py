import time
import subprocess
from datetime import datetime
import os

# --- CONFIGURAÇÕES ---
INTERVALO_VERIFICACAO = 10  # Segundos entre checagens
BRANCH = "main"             # Confirme se é 'main' ou 'master'

def verificar_e_enviar():
    try:
        # 1. Pergunta ao GIT se tem algo pendente (Staging ou Untracked)
        # --porcelain gera uma saída limpa e vazia se não houver mudanças
        result = subprocess.run(
            ["git", "status", "--porcelain"], 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='ignore' # Evita crash com caracteres estranhos
        )
        
        mudancas = result.stdout.strip()

        # Se a variável 'mudancas' não estiver vazia, TEM COISA NOVA!
        if mudancas:
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            print(f"\n[{timestamp}] 👁️ Git detectou alterações:\n{mudancas}")
            print("-" * 40)
            
            mensagem = f"Auto-Update: {timestamp}"
            
            print("⚙️ Adicionando arquivos (git add)...")
            subprocess.run(["git", "add", "."], check=True)
            
            print(f"📝 Commitando (git commit -m '{mensagem}')...")
            subprocess.run(["git", "commit", "-m", mensagem], check=True)
            
            print(f"🚀 Enviando para GitHub (git push origin {BRANCH})...")
            push_result = subprocess.run(
                ["git", "push", "origin", BRANCH], 
                capture_output=True, 
                text=True
            )
            
            if push_result.returncode == 0:
                print(f"✅ SUCESSO! Tudo sincronizado às {timestamp}.")
            else:
                print(f"⚠️ Atenção no Push:\n{push_result.stderr}")
            
            print("-" * 40)
            return True
            
        else:
            # Se não tem mudanças, não faz nada, só silêncio.
            return False

    except Exception as e:
        print(f"❌ Erro Crítico: {e}")
        return False

def main():
    print(f"🔭 VIGIA GIT DIRETO INICIADO")
    print(f"📂 Pasta: {os.getcwd()}")
    print(f"⏱️ Verificando o comando 'git status' a cada {INTERVALO_VERIFICACAO} segundos...")
    print("------------------------------------------------")

    # Loop Infinito
    try:
        while True:
            verificar_e_enviar()
            time.sleep(INTERVALO_VERIFICACAO)
            
            # Pequeno indicador visual de vida (opcional, imprime um ponto a cada ciclo)
            # print(".", end="", flush=True) 

    except KeyboardInterrupt:
        print("\n🛑 Parando script.")

if __name__ == "__main__":
    main()