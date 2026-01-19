import os
from rich.console import Console
from rich.table import Table
from rich import box

# --- CONFIGURAÇÃO ---
PASTA_ALVO = 'Listas-Downloaded'
# --------------------

console = Console()

def analisar_conteudo(caminho):
    """Lê o início do arquivo para descobrir o que ele é"""
    try:
        tamanho = os.path.getsize(caminho)
        if tamanho == 0:
            return "[red]Vazio (0kb)[/]", "❌"

        with open(caminho, 'r', encoding='utf-8', errors='ignore') as f:
            inicio = f.read(200).strip() # Lê os primeiros 200 caracteres
        
        # Análise de Assinatura
        if "#EXTM3U" in inicio:
            if tamanho < 1024: # Menor que 1KB
                return "[yellow]M3U Curto (Poucos canais)[/]", "⚠️"
            return "[bold green]M3U Válido (Lista Real)[/]", "✅"
        
        elif "<html" in inicio.lower() or "<!doctype" in inicio.lower():
            return "[red]HTML (Site/Bloqueio/Erro 403)[/]", "❌"
        
        elif "{" in inicio and "}" in inicio and "error" in inicio.lower():
            return "[red]JSON (Erro de API/Token)[/]", "❌"
            
        else:
            return f"[yellow]Desconhecido ({inicio[:20]}...)[/]", "❓"

    except Exception as e:
        return f"[red]Erro leitura[/]", "❌"

def formatar_tamanho(tamanho):
    for unidade in ['B', 'KB', 'MB', 'GB']:
        if tamanho < 1024.0:
            return f"{tamanho:.1f} {unidade}"
        tamanho /= 1024.0
    return f"{tamanho:.1f} TB"

def main():
    if not os.path.exists(PASTA_ALVO):
        console.print(f"[red]Pasta '{PASTA_ALVO}' não encontrada![/]")
        return

    arquivos = [f for f in os.listdir(PASTA_ALVO) if f.endswith('.m3u')]
    if not arquivos:
        console.print("[yellow]Nenhum arquivo .m3u encontrado.[/]")
        return

    # Tabela
    table = Table(title=f"AUDITORIA DE ARQUIVOS ({len(arquivos)} arquivos)", box=box.SIMPLE)
    table.add_column("Arquivo", style="white")
    table.add_column("Tamanho", justify="right", style="cyan")
    table.add_column("Diagnóstico", justify="center")
    table.add_column("St", justify="center")

    validos = 0
    invalidos = 0

    arquivos.sort() # Ordena alfabeticamente

    for arq in arquivos:
        caminho = os.path.join(PASTA_ALVO, arq)
        tipo, status = analisar_conteudo(caminho)
        tamanho_fmt = formatar_tamanho(os.path.getsize(caminho))
        
        if status == "✅":
            validos += 1
            cor_arq = "green"
        else:
            invalidos += 1
            cor_arq = "white"

        # Encurta nome visualmente
        nome_display = (arq[:40] + '..') if len(arq) > 40 else arq
        
        table.add_row(f"[{cor_arq}]{nome_display}[/]", tamanho_fmt, tipo, status)

    console.print(table)
    console.print(f"\n[bold green]✅ Válidos: {validos}[/] | [bold red]❌ Inválidos/Erros: {invalidos}[/]")

if __name__ == "__main__":
    main()