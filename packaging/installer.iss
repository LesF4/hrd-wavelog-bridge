; Installeur Windows de HRDtoWavelog — Inno Setup 6 (https://jrsoftware.org).
; Construction : python packaging\build.py --installer
; Prérequis    : packaging\dist\HRDtoWavelog\ (produit par PyInstaller via build.py).

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName      "HRDtoWavelog"
#define AppFullName  "HRD Logbook → Wavelog"
#define AppPublisher "F4MAJ / Jean-Bernard"
#define AppURL       "https://github.com/LesF4/hrd-wavelog-bridge"
#define AppExe       "HRDtoWavelog.exe"

[Setup]
; AppId fige l'identité (mises à jour / désinstallation). NE PAS changer entre versions.
AppId={{E7A4F452-6ADB-4CF0-877B-1A30CCC454A6}
AppName={#AppFullName}
AppVersion={#AppVersion}
AppVerName={#AppFullName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppCopyright=© 2026 F4MAJ / Jean-Bernard — MIT
VersionInfoCompany={#AppPublisher}
VersionInfoCopyright=© 2026 F4MAJ / Jean-Bernard — MIT
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppFullName} {#AppVersion}
OutputDir=dist
OutputBaseFilename=HRDtoWavelog-Setup-{#AppVersion}
SetupIconFile=icon.ico
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Installation par utilisateur : pas de pop-up UAC, pas besoin d'être admin.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
; Ferme l'app si elle tourne pendant une mise à jour / désinstallation.
AppMutex=HRDtoWavelog_single_instance,Global\HRDtoWavelog_single_instance
CloseApplications=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
fr.AutoStart=Lancer HRDtoWavelog au démarrage de Windows (recommandé)
en.AutoStart=Start HRDtoWavelog with Windows (recommended)
fr.Options=Options :
en.Options=Options:
fr.ReadGuide=Lire le guide de configuration (à faire une fois)
en.ReadGuide=Read the setup guide (one-time setup)
fr.GuideName=Guide de configuration
en.GuideName=Setup guide

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:Options}"

[Files]
Source: "dist\HRDtoWavelog\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "LISEZ-MOI.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Registry]
; Démarrage automatique (la même clé que la case « Lancer au démarrage » des Réglages de l'app).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "HRDtoWavelog"; ValueData: """{app}\{#AppExe}"" --minimized"; Tasks: autostart
; Toujours retirée à la désinstallation.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "HRDtoWavelog"; Flags: uninsdeletevalue

[Icons]
Name: "{group}\{#AppFullName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:GuideName}"; Filename: "{app}\LISEZ-MOI.txt"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppFullName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\LISEZ-MOI.txt"; Description: "{cm:ReadGuide}"; Flags: postinstall shellexec skipifsilent nowait
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Les réglages, l'historique et la sauvegarde ADIF vivent dans %APPDATA%\HRDtoWavelog :
; on ne les touche PAS à la désinstallation (réglages, clé API, historique).
Type: dirifempty; Name: "{app}"
