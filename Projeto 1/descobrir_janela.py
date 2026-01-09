import time
import pygetwindow as gw
import os

os.system('cls')
print("=== DESCOBRIDOR DE NOME DE JANELA ===")
print("1. Abra o seu sistema/programa.")
print("2. Clique nele para deixá-lo focado (ativo).")
print("3. Espere 5 segundos...")
print("=======================================")

for i in range(5, 0, -1):
    print(f"⏳ {i}...")
    time.sleep(1)

try:
    # Pega a janela que está ativa no momento
    janela_ativa = gw.getActiveWindow()
    print("\n✅ ACHEI!")
    print(f"O nome exato da janela é: '{janela_ativa.title}'")
    print("\nCopie esse nome (sem as aspas) para usar no robô.")
    print("=======================================")
    input("Pressione Enter para sair...")
except Exception as e:
    print(f"❌ Erro: {e}")
