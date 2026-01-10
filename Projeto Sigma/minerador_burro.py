import json
import os
import re

# --- CONFIGURAÇÕES ---
ARQUIVO_ENTRADA = "lista_bruta.txt"
ARQUIVO_SAIDA = "fontes.json"

# --- MAPA DE EMOJIS (Para quem está sem) ---
MAPA_EMOJIS = {
    "SOCIAL MASTER": "🦁",
    "SERV X": "❌", "SERVIDOR X": "❌",
    "CINEMANIA": "🍿",
    "NETTURBO": "🚀", "NET TURBO": "🚀",
    "P2BOX": "📦", "TOURO": "🐂",
    "CARACOL": "🐌",
    "OPENBOX": "🎁",
    "ATIVABOX": "⚡", "ATIVA BOX": "⚡",
    "DUO": "👥",
    "ALPHA MASTER": "🅰️",
    "INFRAX": "🏗️", "LUVEM": "☁️",
    "THUNDER": "⚡",
    "LIDER": "👑",
    "VELOZNET": "🏎️", "MEUSERVIDOR": "🖥️",
    "CINEFLIX": "🎬", "WAVE": "🌊",
    "NETPLAY": "🌐", "SEVEN": "7️⃣", "GALAXY": "🌌", "LUNAR": "🌑", "SPEED": "⏩",
    "OLYMPUS": "🏛️", "EXPLOSION": "💣", "TITÃ": "👺", "SKY": "📡", "SOLAR": "☀️",
    "URANO": "🪐", "ATENA": "🦉", "ANDRÔMEDA": "☄️", "HADES": "🔥", "VÊNUS": "♀️",
    "FLASH": "⚡", "FIRE": "🔥",
    "TOP Z": "🔝", "TOPZ": "🔝",
    "PRO BLACK": "⚫",
    "AZONIX": "🅰️", "SUPREME": "💎"
}

def carregar_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def definir_nome_com_emoji(nome_bruto):
    nome_limpo = nome_bruto.strip()
    
    # Verifica se o primeiro caractere já é um emoji/símbolo
    # (Não é letra, nem número, nem pontuação comum de texto)
    primeiro_char = nome_limpo[0]
    if not primeiro_char.isalnum() and primeiro_char not in ['[', '(', '{', '-', '_']:
        return nome_limpo # Já tem emoji, retorna igual
    
    # Se não tem, procura no mapa
    emoji_escolhido = "📺" # Padrão genérico
    nome_upper = nome_limpo.upper()
    
    # Itera pelo mapa para achar a melhor correspondência
    for chave, icone in MAPA_EMOJIS.items():
        if chave in nome_upper:
            emoji_escolhido = icone
            break
            
    return f"{emoji_escolhido} {nome_limpo}"

def main():
    if not os.path.exists(ARQUIVO_ENTRADA):
        print(f"❌ '{ARQUIVO_ENTRADA}' não encontrado.")
        return

    # 1. Carrega Fontes Atuais
    fontes_atuais = carregar_json(ARQUIVO_SAIDA)
    urls_existentes = {item['api_url'] for item in fontes_atuais}
    
    # 2. Lê Lista Bruta
    with open(ARQUIVO_ENTRADA, 'r', encoding='utf-8') as f:
        linhas = [l.strip() for l in f.readlines() if l.strip()]

    print(f"📥 Processando {len(linhas)//2} itens da lista bruta...\n")

    novos_adicionados = 0
    linhas_para_manter = [] # Aqui ficam os erros

    # Processa de 2 em 2
    i = 0
    while i < len(linhas):
        try:
            # Pega par Nome/Link
            nome_original = linhas[i]
            
            # Verifica se existe linha seguinte (o link)
            if i + 1 >= len(linhas):
                print(f"⚠️ Linha órfã no final (sem link): {nome_original}")
                linhas_para_manter.append(nome_original)
                break
                
            url_api = linhas[i+1]

            # Validação básica
            if not url_api.startswith("http"):
                print(f"⚠️ Formato inválido nas linhas {i+1}-{i+2}. Mantendo no txt.")
                linhas_para_manter.append(nome_original)
                linhas_para_manter.append(url_api)
                i += 2
                continue

            # Verifica Duplicidade
            if url_api in urls_existentes:
                print(f"⏭️  Duplicado (Removendo do txt): {nome_original}")
                # Não adiciona ao JSON, mas não adiciona no 'manter', ou seja, some do txt
                i += 2
                continue

            # --- PROCESSAMENTO DO NOVO ITEM ---
            nome_final = definir_nome_com_emoji(nome_original)
            
            # Adiciona ao objeto JSON
            novo_item = {
                "nome": nome_final,
                "api_url": url_api
            }
            fontes_atuais.append(novo_item)
            urls_existentes.add(url_api)
            
            print(f"✅ Adicionado: {nome_final}")
            novos_adicionados += 1
            
            # Avança o iterador
            i += 2

        except Exception as e:
            print(f"❌ Erro genérico: {e}")
            i += 1

    # 3. Salva Fontes Atualizado
    with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
        json.dump(fontes_atuais, f, indent=4, ensure_ascii=False)

    # 4. Sobrescreve Lista Bruta (Apenas com o que sobrou/erros)
    with open(ARQUIVO_ENTRADA, 'w', encoding='utf-8') as f:
        for l in linhas_para_manter:
            f.write(f"{l}\n")

    print("\n" + "="*40)
    print(f"🎉 CONCLUÍDO!")
    print(f"🆕 Novos itens no JSON: {novos_adicionados}")
    print(f"📦 Total de Fontes: {len(fontes_atuais)}")
    
    if len(linhas_para_manter) == 0:
        print("🧹 Lista Bruta limpa com sucesso!")
    else:
        print(f"⚠️ Restaram {len(linhas_para_manter)} linhas no arquivo bruto (verifique erros).")

if __name__ == "__main__":
    main()