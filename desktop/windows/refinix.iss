; Refinix Windows installer (Inno Setup 6). Compiled by desktop/build.py:
;   iscc /DAppVersion=<version> /DSourceDir=<PyInstaller onedir> /DOutputDir=<out>
;        /DOutputBase=<artifact name without .exe> /DWebView2Installer=<pinned file>
;        desktop\windows\refinix.iss
;
; The WebView2 Runtime shows Refinix's window. Windows 11 includes it; where it
; was removed or never installed, this setup installs Microsoft's offline
; Evergreen Standalone Installer, which build.py pins by SHA-256 and checks for
; a valid Microsoft signature. Run without administrator rights it installs per
; user. Nothing is downloaded during installation.
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
; X.Y.Z.N: the numeric version Windows shows, N the public build number
; (backend/coordinator/release.py), so file versions sort like releases.
#ifndef VersionInfo
  #define VersionInfo "0.0.0.0"
#endif

[Setup]
AppId={{6F4C2E7A-6E3B-4C55-9C8E-2B6B9E9B5A31}
AppName=Refinix
AppVersion={#AppVersion}
AppPublisher=Refinix
VersionInfoVersion={#VersionInfo}
VersionInfoProductVersion={#VersionInfo}
VersionInfoProductTextVersion={#AppVersion}
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
; Release builds: build.py defines SignTool and passes the signer as /Srefinix=…,
; so the setup program and its uninstaller carry the same Authenticode signature.
#ifdef SignTool
SignTool={#SignTool}
SignedUninstaller=yes
#endif

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifdef WebView2Installer
Source: "{#WebView2Installer}"; DestDir: "{tmp}"; DestName: "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; Flags: deleteafterinstall; Check: NeedsWebView2
#endif

[Icons]
Name: "{userprograms}\Refinix"; Filename: "{app}\Refinix.exe"
Name: "{userdesktop}\Refinix"; Filename: "{app}\Refinix.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
#ifdef WebView2Installer
Filename: "{tmp}\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; Parameters: "/silent /install"; StatusMsg: "Installing the Microsoft Edge WebView2 Runtime, which Refinix needs to show its window…"; Flags: waituntilterminated; Check: NeedsWebView2
#endif
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

function NeedsWebView2(): Boolean;
begin
  Result := WebView2Version() = '';
end;

#ifdef WebView2Installer
{ Said on the Ready page, before anything is installed. }
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := MemoDirInfo + NewLine + MemoTasksInfo;
  if NeedsWebView2() then
    Result := Result + NewLine + NewLine +
      'Also installs:' + NewLine + Space +
      'Microsoft Edge WebView2 Runtime (from Microsoft, included in this setup; ' +
      'Refinix uses it to show its window)';
end;

{ The Finished page comes after every [Run] entry above has completed. }
procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and NeedsWebView2() then
    SuppressibleMsgBox(
      'The Microsoft Edge WebView2 Runtime could not be installed, so Refinix''s ' +
      'window will not open yet.' + #13#10#13#10 +
      'Install it from Microsoft ' +
      '(https://developer.microsoft.com/microsoft-edge/webview2/), then open Refinix.',
      mbError, MB_OK, IDOK);
end;
#else
function InitializeSetup(): Boolean;
begin
  Result := True;
  if NeedsWebView2() then
  begin
    { A setup built without the bundled runtime explains, never works around. }
    SuppressibleMsgBox(
      'Refinix needs the Microsoft Edge WebView2 Runtime to show its window, ' +
      'and it is not installed on this computer.' + #13#10#13#10 +
      'It is part of Windows 11. Install it from Microsoft ' +
      '(https://developer.microsoft.com/microsoft-edge/webview2/), then run ' +
      'this installer again.', mbCriticalError, MB_OK, IDOK);
    Result := False;
  end;
end;
#endif
