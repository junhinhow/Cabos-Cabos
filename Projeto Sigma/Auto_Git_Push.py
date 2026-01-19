import sys
import time
import subprocess
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

# --- CONFIGURAÇÕES ---
PASTA_PARA_VIGIAR = "."  # "." é a pasta atual
TEMPO_ESPERA = 10        # Segundos para esperar antes de commitar (evita flood)
BRANCH = "main"          # Ou "master", verifique seu github

class GitHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = datetime.now()
        self.pending_changes = False

    def processar_mudanca(self, event):
        # Ignora a própria pasta .git para não entrar em loop infinito
        if ".git" in event.src_path:
            return
        
        # Ignora arquivos temporários comuns
        if event.src_path.endswith('.tmp') or event.src_path.endswith('.temp'):
            return

        print(f"👀 Detetado: {event.src_path}")
        self.last_modified = datetime.now()
        self.pending_changes = True

    def on_modified(self, event):
        self.processar_mudanca(event)

    def on_created(self, event):
        self.processar_mudanca(event)

    def on_deleted(self, event):
        self.processar_mudanca(event)

    def on_moved(self, event):
        self.processar_mudanca(event)

def git_push_automatico():
    try:
        # 1. Verifica se tem algo para commitar
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not status.stdout.strip():
            return False # Nada mudou de verdade

        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        mensagem = f"Auto-Update: {timestamp}"

        print(f"⚡ Iniciando Commit: {mensagem}")

        # 2. Comandos Git
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", mensagem], check=True)
        
        print("🚀 Enviando para o GitHub (Push)...")
        subprocess.run(["git", "push", "origin", BRANCH], check=True)
        
        print(f"✅ SUCESSO! Código atualizado às {timestamp}\n")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Erro no Git: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro Geral: {e}")
        return False

def main():
    path = PASTA_PARA_VIGIAR
    event_handler = GitHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    print(f"🔭 VIGIA GITHUB ATIVADO na pasta: {os.path.abspath(path)}")
    print(f"🕒 Aguardando {TEMPO_ESPERA}s após alterações para commitar...")
    print("Pressione Ctrl+C para parar.")

    try:
        while True:
            time.sleep(1)
            
            # Lógica de Debounce (Espera o usuário parar de mexer)
            if event_handler.pending_changes:
                tempo_passado = (datetime.now() - event_handler.last_modified).total_seconds()
                
                # Se passaram X segundos desde a última modificação
                if tempo_passado > TEMPO_ESPERA:
                    git_push_automatico()
                    event_handler.pending_changes = False

    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()

if __name__ == "__main__":
    main()