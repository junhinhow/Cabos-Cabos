import pyautogui
import os
import time
import json
import cv2
import numpy as np
import pytesseract

# --- CONFIGURAÇÃO ---
ARQUIVO_CONFIG = 'config_coordenadas.json'
PASTA_PRINTS = 'prints_campos'  # Pasta onde salvaremos as fotos
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Cria a pasta de prints se não existir
os.makedirs(PASTA_PRINTS, exist_ok=True)

# Lista de campos (Ordem de preenchimento)
CAMPOS_ALVO = [
    'CLIENTE_ID', 'CLIENTE_NOME', 'FANTASIA',
    'ENDERECO', 'COMPLEMENTO', 'BAIRRO',
    'TELEFONE', 'CONVENIO', 'CONTATO', 'CIDADE',
    'LIMITE', 'CNPJ', 'INSC_ESTADUAL', 'INSC_MUNICIPAL', 'SALDO_DEVEDOR'
]

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def carregar_config():
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            with open(ARQUIVO_CONFIG, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_config(mapa):
    with open(ARQUIVO_CONFIG, 'w') as f:
        json.dump(mapa, f, indent=4)
    print(f"\n💾 Configuração salva em '{ARQUIVO_CONFIG}'!")

def testar_leitura(coords, nome_campo="teste"):
    """
    Tira print, SALVA O ARQUIVO na pasta e roda o OCR.
    Retorna o texto lido.
    """
    if coords[2] <= 0 or coords[3] <= 0: return "[Área Inválida]"

    # Tira print
    screenshot = pyautogui.screenshot(region=tuple(coords))
    img = np.array(screenshot)
    
    # SALVA O PRINT PARA CONFERÊNCIA
    # Converte RGB (PyAutoGUI) para BGR (OpenCV) antes de salvar
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    caminho_img = os.path.join(PASTA_PRINTS, f"{nome_campo}.png")
    cv2.imwrite(caminho_img, img_bgr)
    
    # Tratamento de Imagem (IGUAL AO DO ROBÔ FINAL)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    scaled = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(scaled, 180, 255, cv2.THRESH_BINARY)
    
    config = r'--psm 7' # PSM 7: Assume linha única de texto
    try:
        texto = pytesseract.image_to_string(thresh, lang='por', config=config)
    except:
        texto = pytesseract.image_to_string(thresh, lang='eng', config=config)
    
    return texto.strip()

def capturar_campo(nome_campo):
    print(f"\n--- MAPEANDO: {nome_campo} ---")
    print("1. Posicione o mouse no CANTO SUPERIOR ESQUERDO da caixa.")
    input("   Aperte [ENTER] para capturar INÍCIO...")
    x1, y1 = pyautogui.position()
    print(f"   📍 Início: {x1}, {y1}")
    
    print("2. Posicione o mouse no CANTO INFERIOR DIREITO da caixa.")
    input("   Aperte [ENTER] para capturar FIM...")
    x2, y2 = pyautogui.position()
    
    # Corrige coordenadas invertidas
    x_start, y_start = min(x1, x2), min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    
    return [x_start, y_start, width, height]

def relatorio_geral(mapa_atual):
    print("\n" + "="*60)
    print("🕵️  RELATÓRIO GERAL - LEITURA EM TEMPO REAL")
    print("="*60)
    print(f"{'CAMPO':<20} | {'TEXTO LIDO PELO ROBÔ'}")
    print("-" * 60)
    
    for campo in CAMPOS_ALVO:
        coords = mapa_atual.get(campo)
        if coords:
            # Lê e salva o print com o nome do campo
            leitura = testar_leitura(coords, nome_campo=campo)
            print(f"{campo:<20} | {leitura}")
        else:
            print(f"{campo:<20} | [Não Mapeado]")
            
    print("-" * 60)
    print(f"📁 Prints salvos na pasta: ./{PASTA_PRINTS}/")
    input("\nPressione Enter para voltar ao menu...")

def menu_principal():
    mapa_atual = carregar_config()
    
    while True:
        limpar_tela()
        print("=== 🧠 MAPEADOR INTELIGENTE V3.0 ===")
        print(f"Arquivo: {ARQUIVO_CONFIG}")
        print("-" * 60)
        print(f"{'ID':<4} | {'CAMPO':<20} | {'STATUS':<10}")
        print("-" * 60)
        
        # Mostra tabela simples (sem leitura para não travar o menu)
        for idx, campo in enumerate(CAMPOS_ALVO):
            coords = mapa_atual.get(campo)
            status = "✅ OK" if coords else "❌ Vazio"
            print(f"{idx+1:<4} | {campo:<20} | {status:<10}")
            
        print("-" * 60)
        print("[A] Mapear TODOS (Sequencial)")
        print("[E] Editar/Mapear um único campo")
        print("[T] Testar Leitura de um Campo (Gera Print)")
        print("[G] GERAR RELATÓRIO GERAL (Lê tudo agora)")
        print("[S] Salvar e Sair")
        print("[X] Sair sem Salvar")
        
        opcao = input("\nEscolha uma opção: ").upper()
        
        if opcao == 'A':
            print("\n🚀 Iniciando Mapeamento Sequencial...")
            for campo in CAMPOS_ALVO:
                while True:
                    coords = capturar_campo(campo)
                    texto_lido = testar_leitura(coords, nome_campo=campo)
                    print(f"\n👀 O ROBÔ LEU: '{texto_lido}'")
                    print(f"   (Imagem salva em {PASTA_PRINTS}/{campo}.png)")
                    confirma = input("   A leitura está aceitável? (S para Sim / N para Tentar de novo): ").upper()
                    if confirma == 'S':
                        mapa_atual[campo] = coords
                        break
                    else:
                        print("   🔄 Vamos tentar marcar de novo...")
            salvar_config(mapa_atual)
            input("\n✅ Tudo mapeado! Pressione Enter para voltar...")

        elif opcao == 'E':
            try:
                num = int(input("Digite o ID do campo para editar (ex: 12): "))
                if 1 <= num <= len(CAMPOS_ALVO):
                    campo_sel = CAMPOS_ALVO[num-1]
                    while True:
                        coords = capturar_campo(campo_sel)
                        texto_lido = testar_leitura(coords, nome_campo=campo_sel)
                        print(f"\n👀 O ROBÔ LEU: '{texto_lido}'")
                        print(f"   (Imagem salva em {PASTA_PRINTS}/{campo_sel}.png)")
                        if input("   Confirmar? (S/N): ").upper() == 'S':
                            mapa_atual[campo_sel] = coords
                            break
            except: pass

        elif opcao == 'T':
            try:
                num = int(input("Digite o ID do campo para testar OCR: "))
                if 1 <= num <= len(CAMPOS_ALVO):
                    campo_sel = CAMPOS_ALVO[num-1]
                    coords = mapa_atual.get(campo_sel)
                    if coords:
                        print(f"\n📸 Tirando foto de {campo_sel}...")
                        texto = testar_leitura(coords, nome_campo=campo_sel)
                        print(f"\n>>> RESULTADO: '{texto}'")
                        print(f"   (Imagem salva em {PASTA_PRINTS}/{campo_sel}.png)")
                        input("\nPressione Enter para continuar...")
                    else:
                        print("❌ Esse campo ainda não foi mapeado.")
                        time.sleep(1)
            except: pass

        elif opcao == 'G':
            relatorio_geral(mapa_atual)

        elif opcao == 'S':
            salvar_config(mapa_atual)
            print("👋 Até logo!")
            break
            
        elif opcao == 'X':
            break

if __name__ == "__main__":
    menu_principal()