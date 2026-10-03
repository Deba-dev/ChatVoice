; Inno Setup script (free) - turns dist\ChatVoice into a normal ChatVoice-Setup.exe
[Setup]
AppName=ChatVoice
AppVersion=0.3
AppPublisher=ChatVoice
DefaultDirName={autopf}\ChatVoice
DefaultGroupName=ChatVoice
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=ChatVoice-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\ChatVoice.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\ChatVoice\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\ChatVoice"; Filename: "{app}\ChatVoice.exe"
Name: "{autodesktop}\ChatVoice"; Filename: "{app}\ChatVoice.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ChatVoice.exe"; Description: "Start ChatVoice"; Flags: nowait postinstall skipifsilent
