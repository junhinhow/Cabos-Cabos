import os
import re
import shutil
import cv2
import pytesseract
import numpy as np
from collections import OrderedDict

# --- CONFIGURAÇÕES ---
ARQUIVO_ALVO = "auditoria_completa.txt"
PASTA_PRINTS = "prints_web"
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def verificar_isencao(razao_social):
    termos_isentos = [
        "ASSOC", "IGREJA", "CONDOMINIO", "FUNDACAO", "INSTITUTO", 
        "SINDICATO", "CONSELHO", "MUNICIPIO", "ESTADO", "PREFEITURA",
        "EDUCACAO", "SOCIAL", "BENEFICENTE", "TEMPLO", "COMUNIDADE"
    ]
    razao_upper = razao_social.upper()
    for termo in termos_isentos:
        if termo in razao_upper: return True
    return False

def limpar_fantasia(texto_bruto):
    """Remove sujeiras comuns de OCR e Popups"""
    if not texto_bruto: return None
    
    # 1. Remove frases de Popup
    sujeiras = [
        "Deseja receber", "Ative as notificações", "CNPJ.BIZ", 
        "Alavanque Suas", "Vendas Agora", "Empresas"
    ]
    for sujo in sujeiras:
        if sujo in texto_bruto:
            texto_bruto = texto_bruto.split(sujo)[0] # Corta tudo a partir da sujeira
            
    # 2. Se o resultado for uma Data ou outra label, ignora
    if "Data da Abertura" in texto_bruto or "Porte:" in texto_bruto:
        return None
        
    limpo = texto_bruto.strip().strip("-").strip()
    
    if len(limpo) < 2: return None
    return limpo

def analisar_imagem(caminho_img):
    if not os.path.exists(caminho_img): return None, None
    try:
        img = cv2.imread(caminho_img)
        # Otimização: Lê um pedaço maior para garantir que pegue o popup se ele cobrir
        if img.shape[0] > 1500: img = img[0:1500, :]
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        texto = pytesseract.image_to_string(thresh, lang='por')
        
        # --- Extração de Fantasia Melhorada ---
        fantasia = None
        # Tenta pegar apenas a linha exata
        match_fan = re.search(r'Nome Fantasia[:\.]?\s*([^\n]+)', texto, re.IGNORECASE)
        if match_fan:
            raw_fantasia = match_fan.group(1).strip()
            fantasia = limpar_fantasia(raw_fantasia)
            
        # --- Extração de Capital ---
        capital = None
        match_cap = re.search(r'Capital Social.*?R\$\s*([\d\.]+,\d{2})', texto, re.IGNORECASE)
        if match_cap: capital = f"R$ {match_cap.group(1)}"
        else:
            match_cap2 = re.search(r'Capital Social.*?(\d{1,3}(?:\.\d{3})*,\d{2})', texto, re.IGNORECASE)
            if match_cap2: capital = f"R$ {match_cap2.group(1)}"
            
        return fantasia, capital
    except:
        return None, None

def processar_arquivo():
    if not os.path.exists(ARQUIVO_ALVO):
        print(f"❌ Erro: '{ARQUIVO_ALVO}' não encontrado.")
        return

    print("📦 Criando backup (auditoria_completa.txt.backup)...")
    shutil.copy(ARQUIVO_ALVO, f"{ARQUIVO_ALVO}.backup")
    
    with open(ARQUIVO_ALVO, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    blocos_raw = conteudo.split('AUDITORIA DO CLIENTE:')
    cabecalho_arquivo = blocos_raw[0]
    clientes_processados = OrderedDict()
    
    total_lidos = len(blocos_raw) - 1
    print(f"🚀 Corrigindo Auditoria em {total_lidos} clientes...")
    print("-" * 60)

    for i, bloco_texto in enumerate(blocos_raw[1:]):
        bloco_completo = f"AUDITORIA DO CLIENTE:{bloco_texto}"
        
        match_cnpj = re.search(r'CNPJ SISTEMA:\s*(\d{14})', bloco_completo)
        match_id = re.search(r'AUDITORIA DO CLIENTE:\s*(\d+)', bloco_completo)
        match_razao = re.search(r'WEB RAZÃO:\s*(.*?)\n', bloco_completo)
        
        chave = match_cnpj.group(1) if match_cnpj else (match_id.group(1) if match_id else f"UNKNOWN_{i}")
        razao = match_razao.group(1).strip() if match_razao else ""
        
        # --- FORÇA RELEITURA DA FANTASIA ---
        # Mesmo que já tenha fantasia, vamos ler de novo para aplicar a correção
        novo_fantasia = None
        novo_capital = None
        status_fantasia = "Mantido"
        
        if match_cnpj:
            cnpj = match_cnpj.group(1)
            caminho_foto = os.path.join(PASTA_PRINTS, f"cnpj_{cnpj}.png")
            
            # Lê imagem
            fantasia_img, capital_img = analisar_imagem(caminho_foto)
            
            # Atualiza Fantasia (Sempre tenta melhorar)
            if fantasia_img:
                novo_fantasia = fantasia_img
                status_fantasia = f"✨ Corrigido: {novo_fantasia}"
            else:
                novo_fantasia = "---"
                status_fantasia = "⚠️ Vazio/Sujo"

            # Atualiza Capital (Só se faltar)
            tem_capital = "CAPITAL SOCIAL (WEB):" in bloco_completo
            if not tem_capital:
                if capital_img: novo_capital = capital_img
                elif verificar_isencao(razao): novo_capital = "R$ 0,00 (Isento)"
                else: novo_capital = "Não detectado"

        print(f"📄 Cli {i+1} ({cnpj}) | Fan: {status_fantasia}")

        # --- RECONSTRUÇÃO DO BLOCO ---
        # Remove linha antiga de fantasia se existir
        bloco_limpo = re.sub(r'WEB FANTASIA:.*\n', '', bloco_completo)
        
        # Insere a Fantasia Nova (Limpa)
        linha_fan = f"WEB FANTASIA: {novo_fantasia}\n"
        match_r = re.search(r'(WEB RAZÃO:.*?\n)', bloco_limpo)
        if match_r:
            bloco_limpo = bloco_limpo.replace(match_r.group(0), match_r.group(0) + linha_fan, 1)
            
        # Insere Capital (Se novo)
        if novo_capital:
            linha_cap = f"CAPITAL SOCIAL (WEB): {novo_capital}\n"
            match_f = re.search(r'(WEB FANTASIA:.*?\n)', bloco_limpo)
            if match_f: bloco_limpo = bloco_limpo.replace(match_f.group(0), match_f.group(0) + linha_cap, 1)

        clientes_processados[chave] = bloco_limpo

    print("-" * 60)
    print("💾 Salvando correções...")
    
    conteudo_final = [cabecalho_arquivo]
    conteudo_final.extend(clientes_processados.values())
    
    with open(ARQUIVO_ALVO, 'w', encoding='utf-8') as f:
        f.write("".join(conteudo_final))
        
    print(f"✅ SUCESSO! Base limpa e corrigida.")

if __name__ == "__main__":
    processar_arquivo()