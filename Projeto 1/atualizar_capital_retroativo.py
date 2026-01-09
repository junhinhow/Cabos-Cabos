import os
import re
import shutil
import cv2
import pytesseract

# --- CONFIGURAÇÃO ---
ARQUIVO_TXT = "auditoria_completa.txt"
ARQUIVO_NOVO = "auditoria_completa_COM_CAPITAL.txt"
PASTA_PRINTS = "prints_web"
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extrair_capital_da_imagem(caminho_img):
    """Lê o print e procura o valor do Capital Social"""
    if not os.path.exists(caminho_img):
        return None
    
    try:
        # Lê a imagem
        img = cv2.imread(caminho_img)
        
        # Otimização: O Capital Social costuma estar no topo. 
        # Vamos ler apenas os primeiros 2000 pixels de altura para ser rápido.
        altura, largura, _ = img.shape
        if altura > 2000:
            img = img[0:2000, 0:largura] # Corta o topo
            
        # Converte para cinza
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # OCR
        texto = pytesseract.image_to_string(gray, lang='por')
        
        # Regex para achar: "Capital Social: R$ 1.000,00" ou "Capital Social R$ 1.000,00"
        # Procura algo como "Capital Social" seguido de numeros
        match = re.search(r'Capital Social.*?R\$\s*([\d\.]+,\d{2})', texto, re.IGNORECASE)
        
        if match:
            return f"R$ {match.group(1)}"
        
        # Tentativa secundária (sem o R$)
        match2 = re.search(r'Capital Social.*?(\d{1,3}(?:\.\d{3})*,\d{2})', texto, re.IGNORECASE)
        if match2:
            return f"R$ {match2.group(1)}"
            
        return "Não detectado no print"
        
    except Exception as e:
        print(f"   ⚠️ Erro ao ler imagem: {e}")
        return None

def processar_arquivo():
    if not os.path.exists(ARQUIVO_TXT):
        print("❌ Arquivo de auditoria não encontrado!")
        return

    print(f"📦 Criando backup de segurança...")
    shutil.copy(ARQUIVO_TXT, f"{ARQUIVO_TXT}.backup")
    
    print(f"📖 Lendo {ARQUIVO_TXT}...")
    with open(ARQUIVO_TXT, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    # Separa os blocos de clientes (cada cliente é separado por linha tracejada longa)
    # O padrão é que cada bloco começa e termina com linhas de traços.
    # Vamos dividir pelo cabeçalho padrão
    blocos = conteudo.split('AUDITORIA DO CLIENTE:')
    
    novo_conteudo = []
    
    # O primeiro item do split geralmente é vazio ou cabeçalho inicial
    novo_conteudo.append(blocos[0])
    
    total = len(blocos) - 1
    print(f"🚀 Processando {total} clientes...")

    for i, bloco in enumerate(blocos[1:]):
        # Reconstrói o cabeçalho que o split removeu
        bloco_completo = f"AUDITORIA DO CLIENTE:{bloco}"
        
        # 1. Verifica se já tem Capital Social
        if "CAPITAL SOCIAL (WEB):" in bloco_completo:
            print(f"   🔹 Cliente {i+1}: Já possui Capital. Pulando.")
            novo_conteudo.append(bloco_completo)
            continue

        # 2. Extrai o CNPJ desse bloco para achar a foto
        match_cnpj = re.search(r'CNPJ SISTEMA:\s*(\d{14})', bloco_completo)
        
        if match_cnpj:
            cnpj = match_cnpj.group(1)
            caminho_foto = os.path.join(PASTA_PRINTS, f"cnpj_{cnpj}.png")
            
            print(f"   🔸 Cliente {i+1} (CNPJ {cnpj}): Buscando na imagem...")
            
            capital = extrair_capital_da_imagem(caminho_foto)
            
            if capital:
                print(f"      ✅ Encontrado: {capital}")
                
                # INSERÇÃO CIRÚRGICA:
                # Vamos inserir a linha do Capital logo após a linha do CNPJ/Razão Web
                # Procura o fim da linha que contém "WEB RAZÃO:"
                padrao_insercao = r'(WEB RAZÃO:.*?\n)'
                linha_capital = f"CAPITAL SOCIAL (WEB): {capital}\n"
                
                bloco_atualizado = re.sub(padrao_insercao, f"\\1{linha_capital}", bloco_completo)
                novo_conteudo.append(bloco_atualizado)
            else:
                print(f"      ⚠️ Imagem não encontrada ou ilegível.")
                # Adiciona linha vazia para manter padrão
                padrao_insercao = r'(WEB RAZÃO:.*?\n)'
                linha_capital = f"CAPITAL SOCIAL (WEB): [Sem Print Anterior]\n"
                bloco_atualizado = re.sub(padrao_insercao, f"\\1{linha_capital}", bloco_completo)
                novo_conteudo.append(bloco_atualizado)
        else:
            print(f"   ⚠️ Erro: Não achei CNPJ no bloco {i+1}")
            novo_conteudo.append(bloco_completo)

    # Salva o novo arquivo
    print(f"\n💾 Salvando novo arquivo: {ARQUIVO_NOVO}")
    texto_final = "".join(novo_conteudo)
    
    with open(ARQUIVO_NOVO, 'w', encoding='utf-8') as f:
        f.write(texto_final)
        
    print("✅ Concluído! Verifique o arquivo novo.")

if __name__ == "__main__":
    processar_arquivo()