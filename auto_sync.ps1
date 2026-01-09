# Configuração
$intervaloMinutos = 10
$branch = "main" # Ou "master", verifique qual você usa

Write-Host "🤖 Iniciando Auto-Sync do Git a cada $intervaloMinutos minutos..." -ForegroundColor Green

while ($true) {
    # Pega a data atual para o log
    $data = Get-Date -Format "dd/MM/yyyy HH:mm:ss"
    
    # Verifica se há mudanças (arquivos modificados, deletados ou novos)
    if (git status --porcelain) {
        Write-Host "[$data] Alterações detectadas. Iniciando backup..." -ForegroundColor Yellow
        
        # 1. Adiciona tudo
        git add .
        
        # 2. Faz o commit com data/hora
        git commit -m "Auto-backup: $data"
        
        # 3. Tenta subir para o GitHub
        # O comando abaixo captura o erro caso falhe (ex: sem internet)
        try {
            git push origin $branch
            Write-Host "[$data] ✅ Sucesso! Código salvo no GitHub." -ForegroundColor Green
        }
        catch {
            Write-Host "[$data] ❌ Erro ao fazer Push. Tentaremos na próxima." -ForegroundColor Red
        }
    }
    else {
        Write-Host "[$data] Nada novo para salvar." -ForegroundColor Gray
    }

    # Espera X minutos antes de rodar de novo (60 segundos * minutos)
    Start-Sleep -Seconds ($intervaloMinutos * 60)
}