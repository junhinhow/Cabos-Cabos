# Configuração
$intervaloMinutos = 10
$path = "C:\Users\Vendas Externa\Downloads\Codes"
Set-Location $path

# Função para criar notificação no Windows (Balãozinho no canto da tela)
function Enviar-Notificacao ($Titulo, $Mensagem) {
    [reflection.assembly]::loadwithpartialname("System.Windows.Forms") | Out-Null
    [reflection.assembly]::loadwithpartialname("System.Drawing") | Out-Null
    $icone = [System.Drawing.SystemIcons]::Information
    $notif = New-Object System.Windows.Forms.NotifyIcon
    $notif.Icon = $icone
    $notif.BalloonTipIcon = "Info"
    $notif.BalloonTipTitle = $Titulo
    $notif.BalloonTipText = $Mensagem
    $notif.Visible = $True
    $notif.ShowBalloonTip(10000)
    start-sleep -s 2
    $notif.Dispose() # Limpa o ícone da bandeja
}

while ($true) {
    $data = Get-Date -Format "dd/MM/yyyy HH:mm:ss"
    
    # Verifica mudanças
    if (git status --porcelain) {
        git add .
        git commit -m "Auto-backup: $data"
        
        try {
            git push origin main
            # AVISA QUE FEZ O BACKUP
            Enviar-Notificacao "GitHub Auto-Sync" "✅ Backup realizado com sucesso às $data"
        }
        catch {
            Enviar-Notificacao "GitHub Auto-Sync" "❌ Erro ao enviar para o GitHub. Verifique a internet."
        }
    }
    
    Start-Sleep -Seconds ($intervaloMinutos * 60)
}