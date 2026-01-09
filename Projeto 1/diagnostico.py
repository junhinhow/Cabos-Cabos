import pyautogui
import pytesseract
import cv2
import numpy as np
import re
import os

# --- AJUSTE OBRIGATÓRIO SE MUDOU A TELA ---
# Como você dividiu a tela, RECOMENDO rodar o 'mapear.py' de novo rapidinho
# para pegar a nova posição do bloco "CGC / CNPJ" no canto inferior esquerdo.
# Se não quiser mapear agora, tente estas coordenadas estimadas para tela dividida:
REGION_DADOS = (9, 790, 800, 240) # Tentei pegar uma area menor na esquerda

# Configuração do Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def diagnostico():
    print("📸 Tirando foto da área...")
    screenshot = pyautogui.screenshot(region=REGION_DADOS)
    img = np.array(screenshot)
    
    # --- NOVO TRATAMENTO DE IMAGEM (MELHOR QUALIDADE) ---
    
    # 1. Converte para escala de cinza
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # 2. AUMENTAR RESOLUÇÃO (O Pulo do Gato)
    # Multiplica o tamanho por 3 (fx=3, fy=3) usando interpolação CÚBICA (melhor qualidade)
    # Isso ajuda muito em textos pequenos de tela.
    scaled = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # 3. Threshold (Preto e Branco) ajustado
    # Usei 180 em vez de 127. Isso considera tons de cinza mais claros como "preto",
    # deixando a letra mais "gorda" e legível.
    _, thresh = cv2.threshold(scaled, 180, 255, cv2.THRESH_BINARY)
    
    # ----------------------------------------------------

    # SALVA O QUE O ROBÔ VIU (Para você conferir)
    cv2.imwrite("debug_robo.png", thresh)
    print("💾 Imagem salva como 'debug_robo.png'. Abra ela na pasta para ver se pegou o texto!")
    
    # Tenta ler (Usei 'eng' pois números funcionam melhor que 'por' se o pacote falhar)
    print("📖 Tentando ler texto...")
    try:
        texto = pytesseract.image_to_string(thresh, lang='eng') 
    except:
        # Fallback se o 'eng' falhar, tenta sem idioma
        texto = pytesseract.image_to_string(thresh)
        
    print("-" * 30)
    print(f"TEXTO BRUTO ENCONTRADO:\n{texto}")
    print("-" * 30)
    
    # Regex Novo: Aceita 14 digitos seguidos OU formatado
    match = re.search(r'\d{14}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto)
    
    if match:
        print(f"✅ SUCESSO! CNPJ ENCONTRADO: {match.group(0)}")
    else:
        print("❌ CNPJ não identificado no texto extraído.")
        print("DICA: Se o texto acima estiver vazio ou errado, ajuste as coordenadas em REGION_DADOS.")

if __name__ == "__main__":
    diagnostico()