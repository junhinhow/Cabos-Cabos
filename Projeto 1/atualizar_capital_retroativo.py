import os
import re
import shutil
import cv2
import pytesseract
import numpy as np

# --- CONFIGURAÇÃO ---
ARQUIVO_TXT = "auditoria_completa.txt"
ARQUIVO_NOVO = "auditoria_final_com_capital.txt"
PASTA_PRINTS = "prints_web"
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extrair_capital_da_imagem(caminho_img):
    """Tenta ler o valor do print"""
    if not os.path.exists(caminho_img): return None
    try:
        img = cv2.imread(caminho_img)
        # Otimização: Lê só o topo (cabeçalho)
        if img.shape[0] > 1500: img = img[0:1500, :]
        
        # Aumenta contraste para ler melhor
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        
        texto = pytesseract.image_to_string(thresh, lang='por')
        
        # Procura padrões de dinheiro
        match = re.search(r'Capital Social.*?R\$\s*([\d\.]+,\d{2})', texto, re.IGNORECASE)
        if match: return f"R$ {match.group(1)}"
        
        # Tenta sem o R$
        match2 = re.search(r'Capital Social.*?(\d{1,3}(?:\.\d{3})*,\d{2})', texto, re.IGNORECASE)
        if match2: return f"R$ {match2.group(1)}"
        
        return None
    except:
        return None

def verificar_isencao(razao_social):
    """Verifica se a empresa é do tipo que NÃO TEM capital social"""
    termos_isentos = [
        "ASSOC", "IGREJA", "CONDOMINIO", "FUNDACAO", "INSTITUTO", 
        "SINDICATO", "CONSELHO", "MUNICIPIO", "ESTADO", "PREFEITURA",
        "EDUCACAO", "SOCIAL", "BENEFICENTE", "TEMPLO", "COMUNIDADE"
    ]
    razao_upper = razao_social.upper()
    for termo in termos_isentos:
        if termo in razao_upper:
            return True
    return False

def processar_arquivo():
    if not os.path.exists(ARQUIVO_TXT):
        print("❌ Arquivo de auditoria não encontrado!")
        return

    print(f"📦 Criando backup e lendo dados...")
    shutil.copy(ARQUIVO_TXT, f"{ARQUIVO_TXT}.backup_antes_capital")
    
    with open(ARQUIVO_TXT, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    # Divide por cliente mantendo o separador
    blocos = conteudo.split('AUDITORIA DO CLIENTE:')
    novo_conteudo = [blocos[0]] # Cabeçalho inicial do arquivo
    
    print(f"🚀 Analisando {len(blocos)-1} clientes...")

    for i, bloco in enumerate(blocos[1:]):
        bloco_completo = f"AUDITORIA DO CLIENTE:{bloco}"
        
        # Pula se já tiver Capital
        if "CAPITAL SOCIAL (WEB):" in bloco_completo:
            novo_conteudo.append(bloco_completo)
            continue

        # Extrai CNPJ e Razão Social do Texto
        match_cnpj = re.search(r'CNPJ SISTEMA:\s*(\d{14})', bloco_completo)
        match_razao = re.search(r'WEB RAZÃO:\s*(.*?)\n', bloco_completo)
        
        razao = match_razao.group(1).strip() if match_razao else ""
        cnpj = match_cnpj.group(1) if match_cnpj else "000"
        
        print(f"   🔸 Cliente {i+1} ({razao[:30]}...):", end=" ")
        
        # 1. Tenta ler da imagem
        caminho_foto = os.path.join(PASTA_PRINTS, f"cnpj_{cnpj}.png")
        capital = extrair_capital_da_imagem(caminho_foto)
        
        if capital:
            print(f"✅ Achou: {capital}")
            valor_final = capital
        else:
            # 2. Se não achou, verifica se é Associação/Isento
            if verificar_isencao(razao):
                print(f"✅ Isento (Associação/Sem Fins)")
                valor_final = "R$ 0,00 (Entidade sem Fins Lucrativos)"
            else:
                print(f"⚠️ Não detectado.")
                valor_final = "Não detectado (Verificar Print)"

        # Insere a linha nova
        linha_capital = f"CAPITAL SOCIAL (WEB): {valor_final}\n"
        
        # Insere LOGO DEPOIS da Razão Web
        if match_razao:
            # Usa replace apenas na primeira ocorrência deste bloco
            padrao = match_razao.group(0) # Pega "WEB RAZÃO: ... \n"
            bloco_atualizado = bloco_completo.replace(padrao, padrao + linha_capital, 1)
        else:
            # Fallback: insere no fim se não achar a razão
            bloco_atualizado = bloco_completo + linha_capital
            
        novo_conteudo.append(bloco_atualizado)

    print(f"\n💾 Salvando: {ARQUIVO_NOVO}")
    with open(ARQUIVO_NOVO, 'w', encoding='utf-8') as f:
        f.write("".join(novo_conteudo))
    print("✅ Sucesso!")

if __name__ == "__main__":
    processar_arquivo()