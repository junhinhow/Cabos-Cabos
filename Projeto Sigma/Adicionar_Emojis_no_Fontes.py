import json
import os
import shutil

# --- CONFIGURAÇÕES ---
ARQUIVO_ALVO = "fontes.json"
ARQUIVO_BACKUP = "fontes_backup_emojis_v2.json"

# Lista de Emojis que o sistema usa (para detecção)
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
    "FLASH": "📸", "EAGLE": "🦅", "MY": "Ⓜ️"
}

EMOJI_DEFAULT = "📺"

# Cria um conjunto com todos os emojis possíveis para verificação rápida
TODOS_EMOJIS = set(MAPA_EMOJIS.values())
TODOS_EMOJIS.add(EMOJI_DEFAULT)

def remover_emojis_duplicados(texto):
    """
    Remove emojis repetidos no início. 
    Ex: '📺 📺 Nome' vira '📺 Nome'
    """
    if not texto: return ""
    
    partes = texto.split(' ')
    # Se a primeira e a segunda parte forem emojis iguais (ou se forem dois emojis seguidos)
    if len(partes) > 1:
        # Se os dois primeiros caracteres são emojis conhecidos
        p1 = partes[0]
        p2 = partes[1]
        if p1 in TODOS_EMOJIS and p2 in TODOS_EMOJIS:
            # Mantém só o primeiro (ou o mais específico se quiser lógica complexa, mas aqui simplificamos)
            return " ".join(partes[1:])
    return texto

def ja_tem_emoji_conhecido(texto):
    """
    Verifica se o texto começa EXATAMENTE com um dos nossos emojis.
    Ignora [ ] ( ) - etc.
    """
    if not texto: return False
    # Verifica o primeiro caractere (ou o primeiro + espaço)
    primeiro_char = texto.split(' ')[0]
    return primeiro_char in TODOS_EMOJIS

def escolher_emoji(nome):
    nome_upper = nome.upper()
    for chave, emoji in MAPA_EMOJIS.items():
        if chave in nome_upper:
            return emoji
    return EMOJI_DEFAULT

def main():
    if not os.path.exists(ARQUIVO_ALVO):
        print(f"❌ Arquivo '{ARQUIVO_ALVO}' não encontrado.")
        return

    shutil.copy2(ARQUIVO_ALVO, ARQUIVO_BACKUP)
    print(f"📦 Backup criado: {ARQUIVO_BACKUP}")

    with open(ARQUIVO_ALVO, 'r', encoding='utf-8') as f:
        dados = json.load(f)

    contador = 0
    
    for item in dados:
        nome_original = item.get('nome', '').strip()
        
        # 1. Limpeza preventiva (remove duplos se já existirem)
        nome_limpo = remover_emojis_duplicados(nome_original)

        # 2. Verificação
        if not ja_tem_emoji_conhecido(nome_limpo):
            # Se não tem emoji conhecido no início, adiciona
            emoji = escolher_emoji(nome_limpo)
            novo_nome = f"{emoji} {nome_limpo}"
            
            item['nome'] = novo_nome
            contador += 1
            print(f"🔧 Adicionado: {novo_nome}")
        else:
            # Se já tinha, apenas salva o nome limpo (caso tenhamos removido duplos)
            if nome_limpo != nome_original:
                item['nome'] = nome_limpo
                contador += 1
                print(f"✨ Corrigido (Duplo): {nome_limpo}")

    if contador > 0:
        with open(ARQUIVO_ALVO, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
        print(f"\n✅ Concluído! {contador} nomes ajustados.")
    else:
        print("\n✅ Nenhum ajuste necessário.")

if __name__ == "__main__":
    main()