import json
import os
import shutil
import re

# --- CONFIGURAÇÕES ---
ARQUIVO_ALVO = "fontes.json"
ARQUIVO_BACKUP = "fontes_backup.json"

def limpar_para_ordenacao(texto):
    """
    Remove emojis e símbolos, deixando apenas letras e números para a comparação.
    Ex: "📺 BLACKBR" vira "blackbr"
    Ex: "❌ Servidor X" vira "servidor x"
    """
    if not texto: return ""
    # Regex: [^\w\s] remove tudo que não for letra(w) ou espaço(s)
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    return texto_limpo.strip().lower()

def main():
    if not os.path.exists(ARQUIVO_ALVO):
        print(f"❌ Erro: O arquivo '{ARQUIVO_ALVO}' não foi encontrado.")
        return

    try:
        # 1. Cria backup
        shutil.copy2(ARQUIVO_ALVO, ARQUIVO_BACKUP)
        print(f"📦 Backup criado: {ARQUIVO_BACKUP}")

        # 2. Carrega
        with open(ARQUIVO_ALVO, 'r', encoding='utf-8') as f:
            dados = json.load(f)

        print(f"📂 Lendo {len(dados)} fontes...")

        # 3. Ordenação Inteligente (Ignora Emoji)
        dados.sort(key=lambda x: limpar_para_ordenacao(x.get('nome', '')))

        # 4. Salva
        with open(ARQUIVO_ALVO, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)

        print(f"✅ SUCESSO! Arquivo reordenado alfabeticamente (ignorando ícones).")

    except Exception as e:
        print(f"❌ Erro: {e}")
        if os.path.exists(ARQUIVO_BACKUP):
            shutil.copy2(ARQUIVO_BACKUP, ARQUIVO_ALVO)
            print("⚠️ Backup restaurado.")

if __name__ == "__main__":
    main()