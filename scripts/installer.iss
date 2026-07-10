#define MyAppName "Llanfeng Code Assistant"
#define MyAppPublisher "Llanfeng"
#define MyAppExeName "llanfeng-code-assistant.exe"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\build\windows"
#endif

#ifndef OutputDir
  #define OutputDir "..\build\installer"
#endif

[Setup]
AppId={{D0B60E5A-8337-46A6-9511-19DC52B58B1E}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Llanfeng Code Assistant
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=Llanfeng-Code-Assistant-Setup-{#AppVersion}
SetupIconFile=..\build\flutter\windows\runner\resources\app_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式（主程序）"; GroupDescription: "附加快捷方式："; Flags: unchecked
Name: "codexplugin"; Description: "创建桌面 Codex-Plugin 快捷方式（双击直接注入启动 ChatGPT）"; GroupDescription: "附加快捷方式："; Flags: checked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autodesktop}\Codex-Plugin"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--inject"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "直接启动 ChatGPT Desktop 并注入插件市场解锁 + 模型白名单"; Tasks: codexplugin

[Registry]
Root: HKCU; Subkey: "Software\Classes\llanfeng-code"; ValueType: string; ValueName: ""; ValueData: "URL:Llanfeng Code Assistant"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\llanfeng-code"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\llanfeng-code\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\llanfeng-code\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --import-url ""%1"""; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

