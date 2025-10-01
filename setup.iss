; Script Inno Setup pour InsporaRadio

[Setup]
AppName=InsporaRadio
AppVersion=1.0.0
AppPublisher=CelesteOffi
DefaultDirName={autopf}\InsporaRadio
DefaultGroupName=InsporaRadio
OutputDir=dist
OutputBaseFilename=InsporaRadioSetup
Compression=lzma
SolidCompression=yes

[Files]
; Ton exe principal
Source: "dist\InsporaRadio.exe"; DestDir: "{app}"; Flags: ignoreversion
; Dossier VLC embarqué
Source: "dist\vlc\*"; DestDir: "{app}\vlc"; Flags: recursesubdirs ignoreversion

[Icons]
; Raccourci bureau
Name: "{autodesktop}\InsporaRadio"; Filename: "{app}\InsporaRadio.exe"
; Raccourci menu démarrer
Name: "{group}\InsporaRadio"; Filename: "{app}\InsporaRadio.exe"

[Run]
; Lancer l'app à la fin de l'installation
Filename: "{app}\InsporaRadio.exe"; Description: "{cm:LaunchProgram,InsporaRadio}"; Flags: nowait postinstall skipifsilent
