import os

PASTA = 'Listas-Downloaded'

removidos = 0
if os.path.exists(PASTA):
    for f in os.listdir(PASTA):
        caminho = os.path.join(PASTA, f)
        try:
            # Se for menor que 2KB (2048 bytes), é lixo/erro
            if os.path.getsize(caminho) < 2048:
                os.remove(caminho)
                print(f"🗑️ Removido lixo: {f}")
                removidos += 1
        except:
            pass

print(f"\n✅ Limpeza concluída! {removidos} arquivos inválidos removidos.")