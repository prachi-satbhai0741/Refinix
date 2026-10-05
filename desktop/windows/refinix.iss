; Refinix Windows installer (Inno Setup 6). Compiled by desktop/build.py:
;   iscc /DAppVersion=<version> /DSourceDir=<PyInstaller onedir> /DOutputDir=<out>
;        /DOutputBase=<artifact name without .exe> desktop\windows\refinix.iss
;
; Per-user, no administrator rights: the application goes to
; %LOCALAPPDATA%\Programs\Refinix. Durable data lives elsewhere
; (%LOCALAPPDATA%\Refinix, chosen by backend/coordinator/paths.py), so
; uninstalling or replacing the application never removes chats, models,
; instructions or artifacts.

#ifndef AppVersion
  #error AppVersion must be defined
#endif
#ifndef SourceDir
  #error SourceDir must be defined
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
#ifndef OutputBase
  #define OutputBase "Refinix-" + AppVersion + "-windows-x64-setup"
#endif

[Setup]
AppId={{6F4C2E7A-6E3B-4C55-9C8E-2B6B9E9B5A31}
AppName=Refinix
AppVersion={#AppVersion}
AppPublisher=Refinix
DefaultDirName={localappdata}\Programs\Refinix
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBase}
SetupIconFile=..\icons\Refinix.ico
UninstallDisplayIcon={app}\Refinix.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Refinix"; Filename: "{app}\Refinix.exe"
Name: "{userdesktop}\Refinix"; Filename: "{app}\Refinix.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\Refinix.exe"; Description: "Open Refinix"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2Client = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function WebView2Version(): String;
var
  Value: String;
begin
  Result := '';
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WebView2Client, 'pv', Value) and (Value <> '') and (Value <> '0.0.0.0') then
    Result := Value
  else if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WebView2Client, 'pv', Value) and (Value <> '') and (Value <> '0.0.0.0') then
    Result := Value
  else if RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\' + WebView2Client, 'pv', Value) and (Value <> '') and (Value <> '0.0.0.0') then
    Result := Value;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if WebView2Version() = '' then
  begin
    { Explained, never silently worked around: Refinix shows its window
      through WebView2 and installs nothing on its own. }
    SuppressibleMsgBox(
      'Refinix needs the Microsoft Edge WebView2 Runtime to show its window, ' +
      'and it is not installed on this computer.' + #13#10#13#10 +
      'It is part of Windows 11. Install it from Microsoft ' +
      '(https://developer.microsoft.com/microsoft-edge/webview2/), then run ' +
      'this installer again.', mbCriticalError, MB_OK, IDOK);
    Result := False;
  end;
end;
