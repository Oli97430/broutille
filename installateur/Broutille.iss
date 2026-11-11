; Broutille — installateur Windows (Inno Setup 6). Construire : ISCC.exe Broutille.iss
; Installe pour l'utilisateur seul (aucun droit administrateur), puis prépare Python et les
; bibliothèques (preparer.ps1). Une mise à jour garde l'environnement déjà téléchargé.

#define Nom "Broutille"
#define Version "1.6.1"
#define Script "broutille_app.py"
#define Icone "broutille.ico"

[Setup]
AppId={{6C1F3E2A-9B57-4D2E-8A31-B70E5A1D4C21}
AppName={#Nom}
AppVersion={#Version}
AppVerName={#Nom} {#Version}
AppPublisher=Oli97430
AppPublisherURL=https://github.com/Oli97430/broutille
AppSupportURL=https://github.com/Oli97430/broutille/issues
AppUpdatesURL=https://github.com/Oli97430/broutille/releases
DefaultDirName={localappdata}\Programs\{#Nom}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename={#Nom}-Setup
SetupIconFile=..\logiciel\{#Icone}
UninstallDisplayIcon={app}\{#Icone}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "nl"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "th"; MessagesFile: "compiler:Languages\Thai.isl"

[CustomMessages]
fr.Preparer=Préparer Python et les bibliothèques (environ 3 Go, quelques minutes)
en.Preparer=Set up Python and the libraries (about 3 GB, a few minutes)
fr.PreparerIcone=Préparer {#Nom} (réparer les bibliothèques)
en.PreparerIcone=Set up {#Nom} (repair the libraries)
fr.Lancer=Lancer {#Nom}
en.Lancer=Launch {#Nom}
fr.Bureau=Créer une icône sur le Bureau
en.Bureau=Create a desktop icon

[Tasks]
Name: "bureau"; Description: "{cm:Bureau}"; Flags: unchecked

[Files]
Source: "..\logiciel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; \
  Excludes: "venv\*,__pycache__\*,*.pyc,tests\*,hf_cache\*,*.bat"

[Icons]
Name: "{autoprograms}\{#Nom}"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\{#Script}"""; \
  WorkingDir: "{app}"; IconFilename: "{app}\{#Icone}"
Name: "{autoprograms}\{cm:PreparerIcone}"; Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\preparer.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\{#Icone}"
Name: "{autodesktop}\{#Nom}"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\{#Script}"""; \
  WorkingDir: "{app}"; IconFilename: "{app}\{#Icone}"; Tasks: bureau

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\preparer.ps1"""; \
  WorkingDir: "{app}"; StatusMsg: "{cm:Preparer}"; Flags: waituntilterminated
Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\{#Script}"""; WorkingDir: "{app}"; \
  Description: "{cm:Lancer}"; Flags: postinstall nowait skipifsilent skipifdoesntexist

[UninstallDelete]
; l'environnement et les modèles téléchargés ; vos visites, fiches et réglages restent
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\hf_cache"

[Code]
// filet : un chemin de bibliotheque trop long (plus de 260 caracteres) echappe a [UninstallDelete] ;
// rmdir avec le prefixe \\?\ accepte les chemins longs
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Code: Integer;
begin
  if (CurUninstallStep = usPostUninstall) and DirExists(ExpandConstant('{app}\venv')) then
    Exec(ExpandConstant('{cmd}'), '/c rmdir /s /q "\\?\' + ExpandConstant('{app}\venv') + '"', '', SW_HIDE,
         ewWaitUntilTerminated, Code);
  if CurUninstallStep = usPostUninstall then
    RemoveDir(ExpandConstant('{app}'));     // vide : plus rien à garder
end;
