#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$capability = Get-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
if ($capability.State -ne "Installed") {
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
}

Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

if (-not (Get-NetFirewallRule -Name OpenSSH-Server-In-TCP -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule `
        -Name OpenSSH-Server-In-TCP `
        -DisplayName "OpenSSH SSH Server (sshd)" `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort 22 `
        -Action Allow
}

$publicKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDjE8BHsfRe8hGUMgRXsmoEAYKH44a41NQUzJj8bG19f openmontage-to-LAPTOP-4L60GMSU"
$authFile = "$env:ProgramData\ssh\administrators_authorized_keys"

Set-Content -Path $authFile -Value $publicKey -Encoding ascii
icacls.exe $authFile /inheritance:r | Out-Null
icacls.exe $authFile /grant "*S-1-5-18:F" | Out-Null
icacls.exe $authFile /grant "*S-1-5-32-544:F" | Out-Null

Restart-Service sshd

Write-Host "USERNAME=$env:USERNAME"
Write-Host "SSH_STATUS=$((Get-Service sshd).Status)"
