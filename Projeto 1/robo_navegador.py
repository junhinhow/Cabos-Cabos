import pyautogui
import time
import keyboard
import sys
import os
import ctypes
import robo_extrator as operario

# --- CORREÇÃO DO ERRO DE CRASH ---
# Desabilita o erro quando o mouse encosta no canto da tela
pyautogui.FAILSAFE = False 
# ---------------------------------

# --- CONFIGURAÇÕES ---
LIMITE_MINIMO = 1000.00      
SALDO_MAXIMO_ACEITAVEL = 1000.00 
CIDADE_ALVO = "MANAUS"
TEMPO_TRANSICAO = 1.5 

def forcar_janela_topo():
    """Força bruta para manter a janela visível"""
    try:
        # Pega o ID da janela do console atual
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        
        if hwnd:
            # Configura como TOPMOST (Sempre visível acima das outras)
            # Rect: (0,0) até (600, 800) no canto superior esquerdo
            # SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 600, 800, 0x0040)
            print("📌 Janela fixada no topo!")
        else:
            print("⚠️ Aviso: Rodando dentro de IDE? Janela flutuante só funciona no CMD nativo.")
    except:
        pass

def converter_dinheiro(texto):
    if not texto or texto == "[Vazio]": return 0.0
    try:
        limpo = texto.replace('.', '').replace(',', '.')
        return float(limpo)
    except:
        return 0.0

def validar_cliente(dados):
    cidade = dados.get('CIDADE', '').upper()
    
    # Validação de Cidade (Aceita MANAUS, MANAOS, MªNªUS)
    eh_manaus = False
    if CIDADE_ALVO in cidade or "MAN" in cidade:
        eh_manaus = True
    
    valor_limite = converter_dinheiro(dados.get('LIMITE', '0,00'))
    valor_saldo = converter_dinheiro(dados.get('SALDO_DEVEDOR', '0,00'))
    
    passou_cidade = eh_manaus
    passou_limite = valor_limite > LIMITE_MINIMO
    passou_saldo = valor_saldo < SALDO_MAXIMO_ACEITAVEL
    
    # Log colorido (simulado) para fácil leitura
    status = "✅ APROVADO" if (passou_cidade and passou_limite and passou_saldo) else "❌ REJEITADO"
    print(f"   📊 {status} | Cid: {eh_manaus} | Lim: {passou_limite} | Sal: {passou_saldo}")
    
    return (passou_cidade and passou_limite and passou_saldo)

def ciclo_automatico():
    print("\n🚀 ESTEIRA AUTOMÁTICA INICIADA!")
    print("   [ESC] = PARAR A QUALQUER MOMENTO")
    
    mapa = operario.carregar_coordenadas()
    if not mapa: return

    contador = 0
    
    while True:
        # Verifica parada de emergência
        if keyboard.is_pressed('esc'):
            print("\n🛑 PARADA SOLICITADA PELO USUÁRIO.")
            break

        print(f"\nScanning Cliente #{contador+1}...")
        
        # 1. Lê Sistema
        dados_sys = operario.extrair_sistema(mapa)
        
        # 2. Valida
        if validar_cliente(dados_sys):
            print("   ✅ ELEGÍVEL! Buscando Web...")
            
            cnpj_limpo = operario.limpar_digitos(dados_sys.get('CNPJ', ''))
            
            if len(cnpj_limpo) == 14:
                dados_web = operario.buscar_web(cnpj_limpo)
                operario.salvar_relatorio(dados_sys, dados_web)
            else:
                print("   ❌ CNPJ Inválido.")
        else:
            print("   ⏭️ Ignorado.")

        # 3. Próximo
        print("   ⬇️ Próximo...")
        pyautogui.press('down')
        contador += 1
        
        # Pausa para o sistema carregar o próximo cliente
        time.sleep(TEMPO_TRANSICAO)

def main():
    os.system('cls')
    forcar_janela_topo()
    
    print("="*60)
    print("🤖 ROBÔ NAVEGADOR V3 - ANTI-CRASH")
    print(f"🎯 Regras: {CIDADE_ALVO} | Limite > {LIMITE_MINIMO} | Saldo < {SALDO_MAXIMO_ACEITAVEL}")
    print("👉 Posicione no primeiro cliente.")
    print("👉 Pressione [Num 0] para iniciar.")
    print("="*60)
    
    keyboard.wait('0')
    ciclo_automatico()

if __name__ == "__main__":
    main()