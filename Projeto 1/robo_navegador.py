import pyautogui
import time
import keyboard
import sys
import os
import ctypes
import robo_extrator as operario # Importa as ferramentas do operário

# --- CONFIGURAÇÕES DO ROBÔ ---
LIMITE_MINIMO = 1000.00      
SALDO_MAXIMO_ACEITAVEL = 1000.00 
CIDADE_ALVO = "MANAUS"
TEMPO_ENTRE_CLIENTES = 1.5 # Tempo para o sistema carregar ao descer a seta

# --- ANTI-CRASH ---
pyautogui.FAILSAFE = False

def configurar_janela():
    """Joga o terminal para o canto direito e deixa sempre visível"""
    try:
        os.system('mode con: cols=60 lines=30') # Redimensiona
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        # Move para x=1200, y=0 (Canto direito superior) e Fixa no Topo (-1)
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 1100, 0, 0, 0, 0x0001)
    except:
        pass

def converter_dinheiro(texto):
    if not texto or texto == "[Vazio]": return 0.0
    try:
        return float(texto.replace('.', '').replace(',', '.'))
    except:
        return 0.0

def validar_cliente(dados):
    cidade = dados.get('CIDADE', '').upper()
    # Aceita variações de OCR para Manaus
    eh_manaus = (CIDADE_ALVO in cidade) or ("MAN" in cidade and "US" in cidade)
    
    valor_limite = converter_dinheiro(dados.get('LIMITE', '0,00'))
    valor_saldo = converter_dinheiro(dados.get('SALDO_DEVEDOR', '0,00'))
    
    aprovado = eh_manaus and (valor_limite > LIMITE_MINIMO) and (valor_saldo < SALDO_MAXIMO_ACEITAVEL)
    
    status_icon = "✅" if aprovado else "❌"
    print(f"   {status_icon} Análise: Cid={eh_manaus} | Lim={valor_limite} | Sal={valor_saldo}")
    return aprovado

def iniciar_esteira():
    print("\n" + "="*50)
    print("🚀 ESTEIRA AUTOMÁTICA LIGADA!")
    print("   Pressione [ESC] (segure) para PARAR.")
    print("="*50)

    # Carrega coordenadas do operário
    mapa = operario.carregar_coordenadas()
    if not mapa: return

    contador = 0
    
    while True:
        # Se apertar ESC, para tudo
        if keyboard.is_pressed('esc'):
            print("\n🛑 PARADA DE EMERGÊNCIA ACIONADA.")
            break
            
        print(f"\n--- CLIENTE #{contador + 1} ---")
        
        # 1. O Operário lê a tela
        dados_sys = operario.extrair_sistema(mapa)
        
        # 2. O Chefe valida
        if validar_cliente(dados_sys):
            print("   🌟 CLIENTE PROMISSOR! Buscando dados...")
            
            cnpj = operario.limpar_digitos(dados_sys.get('CNPJ', ''))
            if len(cnpj) == 14:
                # O Operário vai na Web
                dados_web = operario.buscar_web(cnpj)
                operario.salvar_relatorio(dados_sys, dados_web)
            else:
                print("   ⚠️ CNPJ Inválido ou Leitura Ruim.")
        else:
            print("   ⏭️ Ignorando cliente...")

        # 3. Vai para o próximo (Seta para Baixo)
        print("   ⬇️ Próximo...")
        pyautogui.press('down')
        contador += 1
        
        # Espera o sistema carregar
        time.sleep(TEMPO_ENTRE_CLIENTES)

def main():
    os.system('cls')
    configurar_janela()
    
    print("="*50)
    print("🤖 ROBÔ NAVEGADOR - MODO ESTEIRA")
    print(f"🎯 Filtros: {CIDADE_ALVO} | Limite > {LIMITE_MINIMO}")
    print("="*50)
    print("\n👉 1. Clique na janela do seu SISTEMA.")
    print("👉 2. Selecione o PRIMEIRO cliente.")
    print("👉 3. Pressione [Num 0] para DAR A PARTIDA.")
    
    keyboard.wait('0') # Espera o gatilho inicial
    iniciar_esteira()  # Entra no loop infinito

if __name__ == "__main__":
    main()