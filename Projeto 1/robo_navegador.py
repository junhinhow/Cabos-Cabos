import pyautogui
import time
import keyboard
import sys
import os
import pygetwindow as gw
import robo_extrator as operario

# --- CONFIGURAÇÕES ---
LIMITE_MINIMO = 1000.00      
SALDO_MAXIMO_ACEITAVEL = 1000.00 
CIDADE_ALVO = "MANAUS"
TEMPO_ENTRE_CLIENTES = 1.0
NOME_JANELA_SISTEMA = ":: Cadastro de Clientes ::"

pyautogui.FAILSAFE = False

def focar_sistema():
    try:
        janelas = gw.getWindowsWithTitle(NOME_JANELA_SISTEMA)
        if janelas:
            janela = janelas[0]
            if janela.isMinimized: janela.restore()
            janela.activate()
            time.sleep(0.5)
            return True
        else:
            print(f"⚠️ ERRO: Janela '{NOME_JANELA_SISTEMA}' não encontrada.")
            return False
    except:
        return False

def converter_dinheiro(texto):
    if not texto or texto == "[Vazio]": return 0.0
    try: return float(texto.replace('.', '').replace(',', '.'))
    except: return 0.0

def validar_cliente(dados):
    cidade = dados.get('CIDADE', '').upper()
    eh_manaus = (CIDADE_ALVO in cidade) or ("MAN" in cidade and "US" in cidade)
    valor_limite = converter_dinheiro(dados.get('LIMITE', '0,00'))
    valor_saldo = converter_dinheiro(dados.get('SALDO_DEVEDOR', '0,00'))
    
    aprovado = eh_manaus and (valor_limite > LIMITE_MINIMO) and (valor_saldo < SALDO_MAXIMO_ACEITAVEL)
    
    status = "✅" if aprovado else "❌"
    print(f"   {status} Filtro: Cid={eh_manaus} | Lim={valor_limite} | Sal={valor_saldo}")
    return aprovado

def iniciar_esteira():
    os.system('cls')
    print("="*50)
    print("🚀 ESTEIRA AUTOMÁTICA - COM VERIFICAÇÃO DE LOOP")
    print("   Pressione [ESC] (segure) para PARAR.")
    print("="*50)

    mapa = operario.carregar_coordenadas()
    if not mapa: return

    contador = 0
    # Variável para lembrar quem foi o último
    ultimo_id_processado = None
    
    while True:
        if keyboard.is_pressed('esc'):
            print("\n🛑 PARADA SOLICITADA.")
            break
            
        print(f"\n--- CLIENTE #{contador + 1} ---")
        
        if not focar_sistema():
            print("⏳ Aguardando sistema...")
            time.sleep(2)
            continue
        
        # 1. Lê Sistema
        dados_sys = operario.extrair_sistema(mapa)
        id_atual = dados_sys.get('CLIENTE_ID', '')

        # --- LÓGICA ANTI-LOOP ---
        # Se o ID for igual ao último E não for vazio (pra evitar falsos positivos de OCR)
        if id_atual == ultimo_id_processado and id_atual != "[Vazio]":
            print(f"⚠️ ALERTA: O sistema travou no cliente ID {id_atual}!")
            print("   ⏭️ Ignorando validação e forçando descida...")
            
            # Pula direto para a próxima iteração
            print("   ⬇️ Forçando Próximo...")
            if focar_sistema():
                pyautogui.press('down')
                time.sleep(TEMPO_ENTRE_CLIENTES)
            continue
        # -------------------------

        # Atualiza o último ID
        ultimo_id_processado = id_atual
        
        # 2. Valida
        if validar_cliente(dados_sys):
            print("   🌟 APROVADO! Buscando dados...")
            cnpj = operario.limpar_digitos(dados_sys.get('CNPJ', ''))
            if len(cnpj) == 14:
                dados_web = operario.buscar_web(cnpj)
                operario.salvar_relatorio(dados_sys, dados_web)
            else:
                print("   ⚠️ CNPJ Inválido.")
        else:
            print("   ⏭️ Ignorando...")

        # 3. Próximo
        print("   ⬇️ Próximo...")
        if focar_sistema():
            pyautogui.press('down')
            contador += 1
            time.sleep(TEMPO_ENTRE_CLIENTES)
        else:
            time.sleep(5)

def main():
    print("="*50)
    print("🤖 PREPARAÇÃO")
    print(f"1. Janela: '{NOME_JANELA_SISTEMA}'")
    print("2. Pressione [Num 0] para iniciar.")
    print("="*50)
    keyboard.wait('0')
    iniciar_esteira()

if __name__ == "__main__":
    main()