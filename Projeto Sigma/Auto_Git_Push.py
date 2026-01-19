import time
import subprocess
from datetime import datetime
import os

# --- CONFIGURAÇÕES ---
INTERVALO_VERIFICACAO = 10  # Segundos entre checagens
BRANCH = "main"             # Confirme se é 'main' ou 'master'

def verificar_e_enviar():
    try:
        # 1. Pergunta ao GIT se tem algo pendente
        # O comando 'git status --porcelain' é feito para scripts lerem
        result = subprocess.run(
            ["git", "status", "--porcelain"], 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='ignore'
        )
        
        mudancas = result.stdout.strip()

        # Se tiver qualquer texto na variável 'mudancas', significa que tem arquivo novo/modificado
        if mudancas:
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            print(f"\n[{timestamp}] 👁️ Git detectou alterações!")
            
            # Pequena pausa para garantir que o arquivo terminou de ser salvo pelo editor
            time.sleep(2)
            
            mensagem = f"Auto-Update: {timestamp}"
            
            print("⚙️ Adicionando arquivos...")
            subprocess.run(["git", "add", "."], check=True)
            
            print(f"📝 Commitando...")
            subprocess.run(["git", "commit", "-m", mensagem], check=True)
            
            print(f"🚀 Enviando para GitHub...")
            push_result = subprocess.run(
                ["git", "push", "origin", BRANCH], 
                capture_output=True, 
                text=True
            )
            
            if push_result.returncode == 0:
                print(f"✅ SUCESSO! Sincronizado.")
            else:
                print(f"⚠️ O Push falhou (pode ser internet ou conflito):\n{push_result.stderr}")
            
            print("-" * 40)
            return True
            
        else:
            return False

    except Exception as e:
        print(f"❌ Erro no Script: {e}")
        return False

def main():
    print(f"🔭 VIGIA GIT (MODO DIRETO) INICIADO")
    print(f"📂 Pasta: {os.getcwd()}")
    print("------------------------------------------------")

    try:
        while True:
            verificar_e_enviar()
            time.sleep(INTERVALO_VERIFICACAO)

    except KeyboardInterrupt:
        print("\n🛑 Parando script.")

if __name__ == "__main__":
    main()