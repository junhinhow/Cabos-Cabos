import pyautogui
import time
import keyboard
import sys
import os
import ctypes # Biblioteca para mexer no Windows
from datetime import datetime

# Importa o operário
import robo_extrator as operario

# --- CONFIGURAÇÕES DE FILTRO ---
LIMITE_MINIMO = 1000.00      
SALDO_MAXIMO_ACEITAVEL = 1000.00 
CIDADE_ALVO = "MANAUS"
TEMPO_TRANSICAO = 1.5 

def configurar_janela_console():
    """
    Mágica do Windows:
    1. Pega o ID da janela do console.
    2. Define como 'TOPMOST' (Sempre no topo).
    3. Redimensiona e move para o canto superior direito.
    """
    try:
        # Constantes da API do Windows
        HWND_TOPMOST = -1
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_SHOWWINDOW = 0x0040
        
        # Pega a janela atual
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        
        # 1. Força a janela a ficar SEMPRE NO TOPO
        # Os zeros são posições ignoradas pelas flags NOMOVE/NOSIZE
        ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        
        # 2. Opcional: Move para o canto direito (X=1000, Y=0) e diminui tamanho (W=600, H=800)
        # Se atrapalhar, comente a linha abaixo
        ctypes.windll.user32.MoveWindow(hwnd, 1200, 0, 700, 600, True)
        
        print("🖥️ Janela configurada: SEMPRE NO TOPO + CANTO DIREITO")
        
    except Exception as e:
        print(f"⚠️ Não foi possível configurar a janela: {e}")

def converter_dinheiro(texto):
    if not texto or texto == "[Vazio]": return 0.0
    try:
        limpo = texto.replace('.', '').replace(',', '.')
        return float(limpo)
    except:
        return 0.0

def validar_cliente(dados):
    cidade = dados.get('CIDADE', '').upper()
    eh_manaus = CIDADE_ALVO in cidade or "MAN" in cidade or "MANAUS" in cidade
    
    valor_limite = converter_dinheiro(dados.get('LIMITE', '0,00'))
    valor_saldo = converter_dinheiro(dados.get('SALDO_DEVEDOR', '0,00'))
    
    passou_cidade = eh_manaus
    passou_limite = valor_limite > LIMITE_MINIMO
    passou_saldo = valor_saldo < SALDO_MAXIMO_ACEITAVEL
    
    # Log visual claro
    status = "✅ APROVADO" if (passou_cidade and passou_limite and passou_saldo) else "❌ REJEITADO"
    print(f"   📊 {status} | Cid: {passou_cidade} | Lim: {passou_limite} | Sal: {passou_saldo}")
    
    if passed := (passou_cidade and passou_limite and passou_saldo):
        return True
    return False

def ciclo_automatico():
    print("\n🚀 ESTEIRA AUTOMÁTICA INICIADA!")
    print("   [ESC] = PARAR")
    
    mapa = operario.carregar_coordenadas()
    if not mapa: return

    contador_processados = 0
    contador_pulados = 0

    while True:
        if keyboard.is_pressed('esc'):
            print("\n🛑 PARADA SOLICITADA.")
            break

        print(f"\nScanning... (Feitos: {contador_processados} | Pulados: {contador_pulados})")
        
        # 1. Lê Sistema
        dados_sys = operario.extrair_sistema(mapa)
        
        # 2. Valida
        if validar_cliente(dados_sys):
            print("   ✅ CLIENTE ELEGÍVEL! Iniciando Web...")
            
            cnpj_limpo = operario.limpar_digitos(dados_sys.get('CNPJ', ''))
            
            if len(cnpj_limpo) == 14:
                dados_web = operario.buscar_web(cnpj_limpo)
                operario.salvar_relatorio(dados_sys, dados_web)
                contador_processados += 1
            else:
                print("   ❌ CNPJ Inválido.")
        else:
            print("   ⏭️ Pulando...")
            contador_pulados += 1

        # 3. Próximo
        print("   ⬇️ NEXT...")
        pyautogui.press('down')
        time.sleep(TEMPO_TRANSICAO)

    print("="*50)
    print(f"RESUMO: {contador_processados} Salvos | {contador_pulados} Ignorados")
    print("="*50)

def main():
    os.system('cls')
    configurar_janela_console() # <--- A MÁGICA ACONTECE AQUI
    
    print("="*60)
    print("🤖 ROBÔ NAVEGADOR - COM VISOR FLUTUANTE")
    print(f"🎯 Regras: {CIDADE_ALVO} | Limite > {LIMITE_MINIMO} | Saldo < {SALDO_MAXIMO_ACEITAVEL}")
    print("👉 Foque no sistema e pressione [Num 0] para iniciar.")
    print("👉 Pressione [ESC] para parar.")
    print("="*60)
    
    keyboard.wait('0')
    ciclo_automatico()

if __name__ == "__main__":
    main()