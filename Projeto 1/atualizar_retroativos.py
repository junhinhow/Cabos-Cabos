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
    """Verifica se a empresa é isenta de Capital Social"""
    termos_isentos = [
        "ASSOC", "IGREJA", "CONDOMINIO", "FUNDACAO", "INSTITUTO", 
        "SINDICATO", "CONSELHO", "MUNICIPIO", "ESTADO", "PREFEITURA",
        "EDUCACAO", "SOCIAL", "BENEFICENTE", "TEMPLO", "COMUNIDADE"
    ]
    razao_upper = razao_social.upper()
    for termo in termos_isentos:
        if termo in razao_upper: return True
    return False

def analisar_imagem(caminho_img):
    """Lê a imagem uma vez e retorna Fantasia e Capital"""
    if not os.path.exists(caminho_img): return None, None
    
    try:
        img = cv2.imread(caminho_img)
        if img.shape[0] > 1500: img = img[0:1500, :] # Lê só o topo
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        texto = pytesseract.image_to_string(thresh, lang='por')
        
        # --- Extrai Fantasia ---
        fantasia = None
        match_fan = re.search(r'Nome Fantasia[:\.]?\s*(.+)', texto, re.IGNORECASE)
        if match_fan:
            f = match_fan.group(1).strip()
            if len(f) > 2 and "CNPJ" not in f: fantasia = f
            
        # --- Extrai Capital ---
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

    print("📦 Criando backup de segurança...")
    shutil.copy(ARQUIVO_ALVO, f"{ARQUIVO_ALVO}.backup_master")
    
    with open(ARQUIVO_ALVO, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    # 1. Separação Inteligente dos Blocos
    # O split simples pode falhar se o arquivo começar vazio. 
    # Vamos usar regex para pegar tudo entre os separadores.
    blocos_raw = conteudo.split('AUDITORIA DO CLIENTE:')
    
    cabecalho_arquivo = blocos_raw[0] # Geralmente linhas tracejadas iniciais
    clientes_processados = OrderedDict() # Usamos OrderedDict para manter ordem e deduplicar
    
    duplicadas_removidas = 0
    total_lidos = len(blocos_raw) - 1
    
    print(f"🚀 Iniciando Auditoria Mestre em {total_lidos} entradas...")

    for i, bloco_texto in enumerate(blocos_raw[1:]):
        bloco_completo = f"AUDITORIA DO CLIENTE:{bloco_texto}"
        
        # Extrai Identificadores
        match_cnpj = re.search(r'CNPJ SISTEMA:\s*(\d{14})', bloco_completo)
        match_id = re.search(r'AUDITORIA DO CLIENTE:\s*(\d+)', bloco_completo)
        match_razao = re.search(r'WEB RAZÃO:\s*(.*?)\n', bloco_completo)
        
        # Chave Única: CNPJ (ou ID se CNPJ falhar)
        chave = match_cnpj.group(1) if match_cnpj else (match_id.group(1) if match_id else f"UNKNOWN_{i}")
        razao = match_razao.group(1).strip() if match_razao else ""
        
        # Lógica de Deduplicação:
        # Se a chave já existe, significa que o cliente apareceu de novo no log.
        # Vamos manter sempre o ÚLTIMO (sobrescrevendo o anterior), pois o último costuma ser o "correto".
        if chave in clientes_processados:
            duplicadas_removidas += 1
        
        # --- ENRIQUECIMENTO (FANTASIA E CAPITAL) ---
        
        # Verifica se precisa buscar na imagem
        tem_fantasia = "WEB FANTASIA:" in bloco_completo
        tem_capital = "CAPITAL SOCIAL (WEB):" in bloco_completo
        
        novo_fantasia = None
        novo_capital = None
        
        if (not tem_fantasia or not tem_capital) and match_cnpj:
            cnpj = match_cnpj.group(1)
            caminho_foto = os.path.join(PASTA_PRINTS, f"cnpj_{cnpj}.png")
            
            print(f"   🔎 Analisando CNPJ {cnpj}...", end=" ")
            fantasia_img, capital_img = analisar_imagem(caminho_foto)
            
            # Define valor Fantasia
            if not tem_fantasia:
                novo_fantasia = fantasia_img if fantasia_img else "---"
                print(f"[Fan: {novo_fantasia}]", end=" ")
            
            # Define valor Capital
            if not tem_capital:
                if capital_img:
                    novo_capital = capital_img
                    print(f"[Cap: {novo_capital}]", end=" ")
                elif verificar_isencao(razao):
                    novo_capital = "R$ 0,00 (Isento/Sem Fins)"
                    print(f"[Cap: Isento]", end=" ")
                else:
                    novo_capital = "Não detectado"
                    print(f"[Cap: ?]", end=" ")
            print("") # Pula linha
            
        # --- INSERÇÃO NO TEXTO ---
        bloco_final = bloco_completo
        
        # Inserir Fantasia (se não tiver)
        if novo_fantasia:
            # Insere DEPOIS da Razão
            linha_ins = f"WEB FANTASIA: {novo_fantasia}\n"
            match_r = re.search(r'(WEB RAZÃO:.*?\n)', bloco_final)
            if match_r:
                bloco_final = bloco_final.replace(match_r.group(0), match_r.group(0) + linha_ins, 1)
        
        # Inserir Capital (se não tiver)
        if novo_capital:
            linha_ins = f"CAPITAL SOCIAL (WEB): {novo_capital}\n"
            # Tenta inserir DEPOIS da Fantasia (se existir)
            match_f = re.search(r'(WEB FANTASIA:.*?\n)', bloco_final)
            if match_f:
                bloco_final = bloco_final.replace(match_f.group(0), match_f.group(0) + linha_ins, 1)
            else:
                # Se não tem fantasia, insere depois da Razão
                match_r = re.search(r'(WEB RAZÃO:.*?\n)', bloco_final)
                if match_r:
                    bloco_final = bloco_final.replace(match_r.group(0), match_r.group(0) + linha_ins, 1)

        # Salva no dicionário (Isso remove automaticamente os anteriores se a chave for igual)
        clientes_processados[chave] = bloco_final

    # 2. Reconstrução do Arquivo
    print("\n🧹 Consolidando arquivo e removendo duplicatas...")
    
    conteudo_final = [cabecalho_arquivo]
    conteudo_final.extend(clientes_processados.values())
    
    texto_final = "".join(conteudo_final)
    
    with open(ARQUIVO_ALVO, 'w', encoding='utf-8') as f:
        f.write(texto_final)
        
    print(f"✅ CONCLUÍDO!")
    print(f"   📉 Entradas originais: {total_lidos}")
    print(f"   🗑️ Duplicadas removidas: {duplicadas_removidas}")
    print(f"   📈 Clientes únicos finais: {len(clientes_processados)}")
    print(f"   💾 Arquivo salvo: {ARQUIVO_ALVO}")

if __name__ == "__main__":
    processar_arquivo()