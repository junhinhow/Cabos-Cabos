Set WshShell = CreateObject("WScript.Shell") 
WshShell.Run "powershell.exe -ExecutionPolicy Bypass -File ""C:\Users\Vendas Externa\Downloads\Codes\auto_sync.ps1""", 0
Set WshShell = Nothing