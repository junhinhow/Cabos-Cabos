import pytesseract
import shutil

# Tenta achar o tesseract automaticamente no sistema
caminho_tesseract = shutil.which("tesseract")

if caminho_tesseract:
    print(f"✅ Tesseract encontrado em: {caminho_tesseract}")
    pytesseract.pytesseract.tesseract_cmd = caminho_tesseract
    
    # Lista os idiomas instalados para ver se o 'por' (português) aparece
    try:
        idiomas = pytesseract.get_languages(config='')
        print(f"🌍 Idiomas instalados: {idiomas}")
        
        if 'por' in idiomas:
            print("✅ Pacote de Português detectado com sucesso!")
        else:
            print("⚠️ AVISO: Português ('por') NÃO detectado. Verifique se colou o arquivo na pasta 'tessdata'.")
            
    except Exception as e:
        print(f"Erro ao listar idiomas: {e}")
else:
    print("❌ Tesseract não encontrado. Tente reiniciar o terminal ou o VS Code.")

# --- DICA PARA O SEU SCRIPT PRINCIPAL ---
# Quando formos usar o comando de ler texto, usaremos assim:
# texto = pytesseract.image_to_string(imagem, lang='por')