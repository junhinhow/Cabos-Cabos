import json
import os
import shutil

# --- CONFIGURAÇÕES ---
ARQUIVO_ALVO = "fontes.json"
ARQUIVO_BACKUP = "fontes_backup_limpo.json"

# Mapeamento Completo (Palavra-Chave -> Emoji)
MAPA_EMOJIS = {
    "ALPHA": "🐺", "LIDER": "👑", "CINEFLIX": "🎬", "NETPLAY": "🌐",
    "TOP Z": "🔝", "P2VIP": "🟢", "ZEROUM": "⚡", "EVOLUTION": "🔱",
    "HAVOK": "🔰", "AMERICAN": "🦅", "SUBZERO": "❄️", "PRIME": "💎",
    "GLOBAL": "🌍", "INVICTOS": "🎖️", "LIFE": "🧬", "WPM": "📺",
    "BLACKBR": "⚫", "AZONIX": "💎", "NETTURBO": "🚀", "P2BOX": "📦",
    "CARACOL": "🐌", "OPENBOX": "🎁", "ATIVABOX": "🏟️", "DUO": "👥",
    "CINEMANIA": "🍿", "PLAY": "▶️", "TV": "📺", "SERVER": "📡",
    "SERV": "📡", "P2P": "🔗", "UCAST": "⚡", "TITÃ": "👺", 
    "ATENA": "🦉", "ANDRÔMEDA": "☄️", "SOLAR": "☀️", "FIRE": "🔥",
    "LUNAR": "🌑", "GALAXY": "🌌", "OLYMPUS": "🏛️", "SPEED": "⏩",
    "SEVEN": "7️⃣", "SKY": "📡", "HADES": "🔥", "VÊNUS": "♀️",
    "URANO": "🪐", "K9": "🐕", "CINEMAX": "🎥", "GREEN": "🟩",
    "GTA": "🚘", "MAGIC": "🪄", "NICE": "👍", "PLUS": "➕",
    "BLESSED": "🙌", "MY FAMILY": "👪", "REDPLAY": "🔴",
    "FLASH": "📸", "EAGLE": "🦅", "MY": "Ⓜ️", "THUNDER": "⚡",
    "RYZEN": "🟣", "NET-ONE": "1️⃣", "CINE BR": "🇧🇷", "VOLTZ": "🔋",
    "SH-SERVER": "🟠", "CINE Z": "🔱", "PRO BLACK": "⚫", "SUPREME": "👑",
    "INFINITY": "♾️", "Z2": "♦️", "OURO": "🥇", "RUBI": "♟️",
    "DIAMOND": "🔷", "SAFIRA": "🪙", "FUSION": "⭐", "MAX": "⚡",
    "UCAST": "⚡", "WAVE": "🌊", "CINE RAIO": "🟡", "ONE": "1️⃣",
    "SHOW": "✨", "TOP SERVERS": "🆙", "LITE PLAY": "🎯",
    "INFRAX": "🏗️", "ALADDIN": "🧞", "MEUSERVIDOR": "🖥️", "VTVBR": "🇧🇷"
}

EMOJI_DEFAULT = "📺"

# Cria lista de todos os emojis possíveis para saber o que limpar
TODOS_EMOJIS = list(MAPA_EMOJIS.values())
TODOS_EMOJIS.append(EMOJI_DEFAULT)
# Adiciona variações e outros emojis que possam ter aparecido
OUTROS_EMOJIS_LIXO = ["❌", "✅", "☁️", "👽", "🍄", "🌹", "🐝", "☔", "🛑", "⚽", "〽️", "🔴", "💜", "🤍", "💚", "💛", "🥈", "🏹", "🟢", "🚘", "♾️", "🌎", "🍥", "⚡", "📡", "®️", "♦️", "🥇", "♟️", "🔷", "🪙", "⭐"]
TODOS_EMOJIS.extend(OUTROS_EMOJIS_LIXO)

def definir_emoji_correto(nome):
    nome_upper = nome.upper()
    for chave, emoji in MAPA_EMOJIS.items():
        if chave in nome_upper:
            return emoji
    return EMOJI_DEFAULT

def limpar_inicio_nome(nome):
    """
    Remove recursivamente emojis e espaços do início da string
    até encontrar uma letra, número ou símbolo de texto (como [ ou ().
    """
    texto = nome
    limpo = False
    
    while not limpo:
        texto = texto.strip() # Tira espaços das pontas
        encontrou_lixo = False
        
        # Verifica se começa com algum emoji conhecido
        for emoji in TODOS_EMOJIS:
            if texto.startswith(emoji):
                # Remove o emoji do inicio
                texto = texto[len(emoji):]
                encontrou_lixo = True
                break # Reinicia o loop para checar se tem MAIS emojis
        
        if not encontrou_lixo:
            limpo = True
            
    return texto.strip()

def main():
    if not os.path.exists(ARQUIVO_ALVO):
        print(f"❌ Arquivo '{ARQUIVO_ALVO}' não encontrado.")
        return

    # 1. Backup
    shutil.copy2(ARQUIVO_ALVO, ARQUIVO_BACKUP)
    print(f"📦 Backup criado: {ARQUIVO_BACKUP}")

    with open(ARQUIVO_ALVO, 'r', encoding='utf-8') as f:
        dados = json.load(f)

    contador = 0
    
    print("🧹 Iniciando limpeza e padronização...")

    for item in dados:
        nome_original = item.get('nome', '')
        
        # 1. Descobre qual emoji DEVERIA estar lá
        emoji_correto = definir_emoji_correto(nome_original)
        
        # 2. Limpa TUDO que for emoji no começo do nome atual
        nome_limpo = limpar_inicio_nome(nome_original)
        
        # 3. Monta o nome perfeito
        novo_nome = f"{emoji_correto} {nome_limpo}"

        # Só salva e avisa se houve mudança
        if novo_nome != nome_original:
            item['nome'] = novo_nome
            contador += 1
            # print(f"✨ Ajustado: {nome_original} -> {novo_nome}") 

    # 4. Salvar
    with open(ARQUIVO_ALVO, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ Finalizado! {contador} nomes foram corrigidos/padronizados.")
    print("   Agora não deve haver emojis duplicados no início.")

if __name__ == "__main__":
    main()