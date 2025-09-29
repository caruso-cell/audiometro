; ===== Inno Setup - Audiometro Audiofarm (senza #define) =====

#include "version.isi"

#define AppName "Audiometro Audiofarm"
#define AppExe "Audiometro.exe"
#define SetupBaseFilename "Audiometro_Setup"
[Setup]
AppId={{9F7F5A28-3C63-4F5E-9B22-3C8E9E6E1B11}}        ; <-- puoi sostituire con un tuo GUID
AppName={#AppName}                         ; <-- nome visualizzato
AppVersion={#AppVersion}                                     ; <-- versione
AppPublisher=Audiofarm Italia
AppPublisherURL=https://www.audiofarm.it
AppSupportURL=https://www.audiofarm.it
AppUpdatesURL=https://www.audiofarm.it

DefaultGroupName={#AppName}
OutputBaseFilename={#SetupBaseFilename}_{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin                             
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes
DisableDirPage=no
DefaultDirName={autopf}\SW MIMMO\AUDIOMETRO
UsePreviousAppDir=NO
; SetupIconFile=C:\PERCORSO\FACOLTATIVO\audiometro.ico

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea &icona sul Desktop"; GroupDescription: "Icone:"; Flags: unchecked

[Dirs]
Name: "{userdocs}\SW_MIMMO\Audiometro"; Flags: uninsalwaysuninstall
Name: "{userdocs}\SW_MIMMO\Audiometro\Pazienti"; Flags: uninsalwaysuninstall
Name: "{userdocs}\SW_MIMMO\Audiometro\Calibrazioni"; Flags: uninsalwaysuninstall
Name: "{userdocs}\SW_MIMMO\Audiometro\Export"; Flags: uninsalwaysuninstall

[Files]
; Copia il tuo eseguibile nella cartella dell'app
Source: "..\\dist\\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "audiometria_protocol.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\fondatore.json"; DestDir: "{userdocs}\SW_MIMMO\Audiometro\Calibrazioni"; DestName: "fondatore.json"; Flags: ignoreversion
; Aggiungi qui eventuali altri file richiesti:
; Source: "C:\PERCORSO\BUILD\dist\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\\{#AppExe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\\{#AppExe}"; Tasks: desktopicon

; ===== Registrazione protocollo personalizzato: audiometria:// =====
[Registry]
; Chiave radice del protocollo
Root: HKCR; Subkey: "audiometria"; ValueType: string; ValueName: ""; ValueData: "URL:Protocollo audiometria"; Flags: uninsdeletekey
; Valore speciale che identifica l'URL handler (può essere vuoto)
Root: HKCR; Subkey: "audiometria"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Flags: uninsdeletekey
; Icona predefinita (facoltativa)
Root: HKCR; Subkey: "audiometria\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Flags: uninsdeletekey
; Comando di apertura: lancia direttamente l'EXE e passa l'URL completo "%1"
Root: HKCR; Subkey: "audiometria\shell"; ValueType: none; Flags: uninsdeletekey
Root: HKCR; Subkey: "audiometria\shell\open"; ValueType: none; Flags: uninsdeletekey
Root: HKCR; Subkey: "audiometria\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Flags: uninsdeletekey
; Alias protocollo audiometro://
Root: HKCR; Subkey: "audiometro"; ValueType: string; ValueName: ""; ValueData: "URL:Protocollo audiometro"; Flags: uninsdeletekey
Root: HKCR; Subkey: "audiometro"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Flags: uninsdeletekey
Root: HKCR; Subkey: "audiometro\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Flags: uninsdeletekey
Root: HKCR; Subkey: "audiometro\shell"; ValueType: none; Flags: uninsdeletekey
Root: HKCR; Subkey: "audiometro\shell\open"; ValueType: none; Flags: uninsdeletekey
Root: HKCR; Subkey: "audiometro\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Flags: uninsdeletekey


[Run]
; Avvio opzionale a fine installazione
; Filename: "{app}\\{#AppExe}"; Description: "Avvia Audiometro Audiofarm"; Flags: nowait postinstall skipifsilent

; ===== Variante per-utente (NO admin) â€” DISATTIVATA =====
; Per registrare il protocollo solo per l'utente corrente, commenta il blocco HKCR sopra
; e scommenta questo (funziona senza privilegi admin):
; [Registry]
; Root: HKCU; Subkey: "Software\Classes\audiometria"; ValueType: string; ValueName: ""; ValueData: "URL:Protocollo audiometria"; Flags: uninsdeletekey
; Root: HKCU; Subkey: "Software\Classes\audiometria"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Flags: uninsdeletekey
; Root: HKCU; Subkey: "Software\Classes\audiometria\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Flags: uninsdeletekey
; Root: HKCU; Subkey: "Software\Classes\audiometria\shell"; ValueType: none; Flags: uninsdeletekey
; Root: HKCU; Subkey: "Software\Classes\audiometria\shell\open"; ValueType: none; Flags: uninsdeletekey
; Root: HKCU; Subkey: "Software\Classes\audiometria\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\\{#AppExe}"" ""%1"""; Flags: uninsdeletekey







