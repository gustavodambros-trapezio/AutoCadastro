# Deixar o site sempre no ar (tarefa agendada)

O site (`site/app_autocadastro.py`) hoje roda como **processo manual** — se
ele morre (aconteceu em 31/07/2026) ou a máquina reinicia, ninguém acessa
`http://10.15.17.231:8025`. Esta tarefa resolve: sobe com o Windows e
reinicia sozinha se cair.

## Comando (PowerShell **como administrador**, uma única vez)

```powershell
$py = (Get-Command python).Source
$acao    = New-ScheduledTaskAction -Execute $py `
             -Argument 'site\app_autocadastro.py' `
             -WorkingDirectory 'C:\Users\ADMIN\Desktop\AutoCadastro'
$gatilho = New-ScheduledTaskTrigger -AtStartup
$conf    = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
             -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries `
             -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'AutoCadastro Site' -Action $acao -Trigger $gatilho `
  -Settings $conf -User 'ADMIN' -RunLevel Highest -Force
```

Depois, para subir agora sem reiniciar a máquina:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'app_autocadastro' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-ScheduledTask -TaskName 'AutoCadastro Site'
```

Conferir:

```powershell
Get-ScheduledTaskInfo -TaskName 'AutoCadastro Site'
(Invoke-WebRequest -UseBasicParsing http://10.15.17.231:8025 -Headers @{
   Authorization = "Basic " + [Convert]::ToBase64String(
     [Text.Encoding]::ASCII.GetBytes('admin:AUTO@users10'))}).StatusCode  # 200
```

## Observações

- `-RestartCount 999 -RestartInterval 1min`: se o processo morrer, o Windows
  sobe de novo em 1 minuto.
- `-ExecutionTimeLimit 0`: sem limite de tempo (é um serviço, não um job).
- ⚠️ O **Chrome do robô** precisa de sessão de usuário ativa (o WebAgent não
  roda em headless) — mantenha o usuário logado e, ao sair do acesso remoto,
  **desconecte** em vez de encerrar a sessão. O robô abre e reloga o Chrome
  sozinho quando precisa.
- Falta ainda a política do Chrome `AutoLaunchProtocolsFromOrigins` para o
  `web-agent:` (exige admin) — hoje a permissão está gravada no perfil
  `C:\ChromeProtheus`.
