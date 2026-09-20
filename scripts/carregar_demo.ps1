<#
    Carga da base de demonstracao do Gestao de Frotas.

    Rode na RAIZ do projeto, no terminal PowerShell integrado do VSCode.

    Exemplos:

        # carga em producao, com backup, dry-run e confirmacao
        .\scripts\carregar_demo.ps1 -DatabaseUrl "postgresql://usuario:senha@host:5432/banco"

        # usando a DATABASE_URL ja definida na sessao, sem perguntar
        .\scripts\carregar_demo.ps1 -Sim

        # desfazer a carga
        .\scripts\carregar_demo.ps1 -Remover

    O script chama o management command popular_frota. Toda a massa fica numa
    organizacao separada, entao a frota real de outra organizacao nao e tocada.
#>

[CmdletBinding()]
param(
    [string]$DatabaseUrl,
    [string]$Organizacao = "SMS Cacador - Demonstracao",
    [string]$Gestor = "demo.frotas",
    [string]$Senha,
    [string]$Arquivo = "dados\frota_demo.json",
    [switch]$Remover,
    [switch]$SemBackup,
    [switch]$Sim
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path "manage.py")) {
    throw "Rode este script na raiz do projeto (manage.py nao encontrado no diretorio atual)."
}

# Interpretador: venv do projeto, se existir; senao o python do PATH.
$python = "python"
foreach ($candidato in @(".\venv\Scripts\python.exe", ".\.venv\Scripts\python.exe")) {
    if (Test-Path $candidato) { $python = $candidato; break }
}
Write-Host "Interpretador: $python"

if ($DatabaseUrl) { $env:DATABASE_URL = $DatabaseUrl }
if (-not $env:DATABASE_URL) {
    throw "Informe -DatabaseUrl ou defina `$env:DATABASE_URL antes de rodar."
}

$mascarado = $env:DATABASE_URL -replace "://[^@]+@", "://***@"
Write-Host "Banco de destino: $mascarado"
Write-Host "Organizacao: $Organizacao"

# ------------------------------------------------------------------ remocao

if ($Remover) {
    & $python manage.py popular_frota --arquivo $Arquivo --organizacao-nome $Organizacao --remover
    exit $LASTEXITCODE
}

if (-not (Test-Path $Arquivo)) {
    throw "Arquivo de dados nao encontrado: $Arquivo"
}

# ------------------------------------------------------------------ backup

if (-not $SemBackup) {
    if (Get-Command pg_dump -ErrorAction SilentlyContinue) {
        $arquivoBackup = "backup_frotas_{0}.dump" -f (Get-Date -Format "yyyyMMdd_HHmmss")
        Write-Host "Gerando backup em $arquivoBackup ..."
        pg_dump $env:DATABASE_URL -Fc -f $arquivoBackup
        if ($LASTEXITCODE -ne 0) { throw "pg_dump falhou; carga abortada." }
        Write-Host "Backup concluido: $arquivoBackup"
    }
    else {
        Write-Warning "pg_dump nao esta no PATH. Nenhum backup foi gerado."
        if (-not $Sim) {
            $resposta = Read-Host "Continuar mesmo assim? (s/N)"
            if ($resposta -ne "s") { Write-Host "Cancelado."; exit 1 }
        }
    }
}

# ------------------------------------------------------------------ dry-run

Write-Host ""
Write-Host "=== Simulacao (rollback no final) ==="
& $python manage.py popular_frota --arquivo $Arquivo --organizacao-nome $Organizacao --limpar --dry-run
if ($LASTEXITCODE -ne 0) { throw "A simulacao falhou; nada foi gravado." }

if (-not $Sim) {
    Write-Host ""
    $resposta = Read-Host "Gravar essa carga no banco acima? (s/N)"
    if ($resposta -ne "s") { Write-Host "Cancelado."; exit 1 }
}

# ------------------------------------------------------------------ carga

Write-Host ""
Write-Host "=== Carga definitiva ==="
$argumentos = @(
    "manage.py", "popular_frota",
    "--arquivo", $Arquivo,
    "--organizacao-nome", $Organizacao,
    "--limpar",
    "--criar-gestor", $Gestor
)
if ($Senha) { $argumentos += @("--senha", $Senha) }

& $python @argumentos
if ($LASTEXITCODE -ne 0) { throw "A carga falhou." }

Write-Host ""
Write-Host "Pronto. Entre com o usuario '$Gestor' (senha exibida acima)."
Write-Host "Para desfazer: .\scripts\carregar_demo.ps1 -Remover"
