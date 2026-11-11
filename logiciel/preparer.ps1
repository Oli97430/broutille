# Broutille — préparation des bibliothèques (lancé par l'installateur, ou à la main pour réparer).
# Python 3.11 (installé s'il manque, pour l'utilisateur seul), environnement « venv » dans le dossier
# de l'application, PyTorch (carte NVIDIA si présente), puis le reste. Environ 3 Go, une seule fois ;
# relancé, il ne retélécharge que ce qui manque.
$ErrorActionPreference = "Continue"     # les erreurs se lisent dans $LASTEXITCODE (stderr de Python ne doit rien arrêter)
$App = "Broutille"
$Ici = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Ici
$Host.UI.RawUI.WindowTitle = "$App - preparation / setup"

function Dire($fr, $en) { Write-Host ""; Write-Host "== $fr" -ForegroundColor Cyan; Write-Host "   $en" -ForegroundColor DarkGray }
function Echec($fr, $en) {
    Write-Host ""; Write-Host "!! $fr" -ForegroundColor Red; Write-Host "   $en" -ForegroundColor Red
    Read-Host "Entree pour fermer / Press Enter to close" | Out-Null
    exit 1
}

function Trouver-Python {
    foreach ($essai in @(
            @("py", "-3.11"),
            @("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"),
            @("$env:ProgramFiles\Python311\python.exe"),
            @("python"))) {
        try {
            $exe = $essai[0]; $args_ = @($essai | Select-Object -Skip 1)
            $v = & $exe @args_ -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and "$v".Trim() -eq "3.11") { return ,$essai }
        } catch { }
    }
    return $null
}

$venv = Join-Path $Ici "venv\Scripts\python.exe"
if (-not (Test-Path $venv)) {
    Dire "Recherche de Python 3.11" "Looking for Python 3.11"
    $py = Trouver-Python
    if (-not $py) {
        Dire "Python 3.11 absent : installation (pour vous seul, sans droits administrateur)" "Python 3.11 missing: installing it (current user only)"
        try {
            winget install -e --id Python.Python.3.11 --scope user --silent --accept-package-agreements --accept-source-agreements
        } catch { }
        $py = Trouver-Python
        if (-not $py) {
            Start-Process "https://www.python.org/downloads/release/python-3119/"
            Echec "Installez Python 3.11 depuis la page qui vient de s'ouvrir, puis relancez « Preparer $App » (menu Demarrer)." `
                  "Install Python 3.11 from the page that just opened, then run « Preparer $App » again (Start menu)."
        }
    }
    Dire "Creation de l'environnement" "Creating the environment"
    $exe = $py[0]; $args_ = @($py | Select-Object -Skip 1)
    & $exe @args_ -m venv venv
    if ($LASTEXITCODE -ne 0) { Echec "Environnement impossible a creer." "Could not create the environment." }
}

& $venv -m pip install --upgrade pip --disable-pip-version-check -q
$gpu = $false
try { nvidia-smi *> $null; $gpu = ($LASTEXITCODE -eq 0) } catch { }
$torch = & $venv -c "import torch; print('cuda' if torch.version.cuda else 'cpu')" 2>$null
if ($LASTEXITCODE -ne 0) {
    if ($gpu) {
        Dire "PyTorch pour carte NVIDIA (environ 2,5 Go)" "PyTorch for NVIDIA GPU (about 2.5 GB)"
        & $venv -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
    } else {
        Dire "PyTorch pour processeur (environ 250 Mo)" "PyTorch for CPU (about 250 MB)"
        & $venv -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    }
    if ($LASTEXITCODE -ne 0) { Echec "Telechargement de PyTorch impossible : verifiez la connexion Internet." "PyTorch download failed: check the Internet connection." }
}
Dire "Bibliotheques de $App" "$App libraries"
# torch deja la : on ne le remplace pas par une autre version (la carte graphique serait perdue)
Get-Content requirements.txt | Where-Object { $_ -notmatch '^\s*torch' } | Set-Content -Encoding ascii requirements_sans_torch.txt
& $venv -m pip install -r requirements_sans_torch.txt --disable-pip-version-check
$code = $LASTEXITCODE
Remove-Item requirements_sans_torch.txt -ErrorAction SilentlyContinue
if ($code -ne 0) { Echec "Installation des bibliotheques impossible : verifiez la connexion Internet." "Library installation failed: check the Internet connection." }

Dire "Pret ! $App telechargera ses modeles de vision au premier lancement (environ 3 Go)." `
     "Ready! $App will download its vision models on first launch (about 3 GB)."
Start-Sleep -Seconds 3
exit 0
