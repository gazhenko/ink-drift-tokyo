; Offline, per-user installer. package.py supplies config.nsh and uninstall-files.nsh.
Unicode true
!include "config.nsh"
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"

Name "${GAME_NAME}"
OutFile "${OUTPUT_FILE}"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
CRCCheck force
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1033 "ProductName" "${GAME_NAME}"
VIAddVersionKey /LANG=1033 "FileDescription" "${GAME_NAME} Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "${GAME_VERSION}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "See the game's bundled credits and licences."

!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${GAME_ID}"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "This will install ${GAME_NAME} ${GAME_VERSION} for your Windows account.$\r$\n$\r$\nNo extra software or administrator password is needed. The game works offline.$\r$\n$\r$\nClose the game before updating. Updates replace the game folder; your saved progress is kept separately."
!define MUI_FINISHPAGE_TEXT "${GAME_NAME} is installed.$\r$\n$\r$\nUse the shortcut on your desktop or search for ${GAME_NAME} in Start.$\r$\n$\r$\nYou can remove the game in Settings > Apps. Your saved progress will be kept."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchGame
!define MUI_FINISHPAGE_RUN_TEXT "Play ${GAME_NAME}"
!define MUI_FINISHPAGE_RUN_NOTCHECKED
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!define MUI_UNCONFIRMPAGE_TEXT_TOP "Remove ${GAME_NAME} from this Windows account? Your saved progress will be kept."
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

Var StageDir
Var BackupDir

Function .onInit
  SetShellVarContext current
  ${IfNot} ${IsNativeAMD64}
    MessageBox MB_OK|MB_ICONSTOP "This game needs an Intel or AMD 64-bit Windows computer."
    SetErrorLevel 1
    Quit
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONSTOP "This game needs Windows 10 or later."
    SetErrorLevel 1
    Quit
  ${EndIf}
  SetRegView 64
  ; Fixed location keeps install/update/removal predictable, including with /D=.
  StrCpy $INSTDIR "$LOCALAPPDATA\Programs\${GAME_ID}"
  ${If} ${FileExists} "$INSTDIR\*.*"
    ${IfNot} ${FileExists} "$INSTDIR\${GAME_EXE}"
      MessageBox MB_OK|MB_ICONSTOP "The installation folder already exists but does not contain ${GAME_NAME}. Please move or rename that folder first:$\r$\n$INSTDIR"
      SetErrorLevel 1
      Quit
    ${EndIf}
  ${EndIf}
FunctionEnd

Function LaunchGame
  SetOutPath "$INSTDIR"
  ExecShell "open" "$INSTDIR\${GAME_EXE}"
FunctionEnd

Section "Install"
  ; Extract fully into a unique sibling folder before touching an earlier install.
  ClearErrors
  CreateDirectory "$LOCALAPPDATA\Programs"
  GetTempFileName $StageDir "$LOCALAPPDATA\Programs"
  Delete "$StageDir"
  CreateDirectory "$StageDir"
  ${If} ${Errors}
    MessageBox MB_OK|MB_ICONSTOP "The installer could not create a temporary folder. Check your free space and try again."
    SetErrorLevel 1
    Abort
  ${EndIf}
  SetOutPath "$StageDir"
  ClearErrors
  File /r "${PAYLOAD_DIR}/*"
  WriteUninstaller "$StageDir\Uninstall.exe"
  ${If} ${Errors}
    SetOutPath "$TEMP"
    RMDir /r "$StageDir"
    MessageBox MB_OK|MB_ICONSTOP "The game could not be unpacked. Check your free space and try again. Your previous installation has been kept."
    SetErrorLevel 1
    Abort
  ${EndIf}
  SetOutPath "$TEMP"
  StrCpy $BackupDir ""
  ${If} ${FileExists} "$INSTDIR\*.*"
    ClearErrors
    GetTempFileName $BackupDir "$LOCALAPPDATA\Programs"
    Delete "$BackupDir"
    Rename "$INSTDIR" "$BackupDir"
    ${If} ${Errors}
      RMDir /r "$StageDir"
      MessageBox MB_OK|MB_ICONSTOP "Close ${GAME_NAME} and any windows showing its files, then run this installer again. Your previous installation has been kept."
      SetErrorLevel 1
      Abort
    ${EndIf}
  ${EndIf}
  ClearErrors
  Rename "$StageDir" "$INSTDIR"
  ${If} ${Errors}
    ${If} $BackupDir != ""
      ClearErrors
      Rename "$BackupDir" "$INSTDIR"
      ${If} ${Errors}
        MessageBox MB_OK|MB_ICONSTOP "The update could not finish. Your previous game folder is safe at:$\r$\n$BackupDir$\r$\nMove it back to:$\r$\n$INSTDIR"
      ${Else}
        MessageBox MB_OK|MB_ICONSTOP "The update could not finish. Your previous installation has been restored."
      ${EndIf}
    ${Else}
      MessageBox MB_OK|MB_ICONSTOP "The installation could not finish. Close any windows showing the game folder and try again."
    ${EndIf}
    RMDir /r "$StageDir"
    SetErrorLevel 1
    Abort
  ${EndIf}
  ${If} $BackupDir != ""
    RMDir /r "$BackupDir"
  ${EndIf}

  SetOutPath "$INSTDIR"
  CreateShortcut "$DESKTOP\${GAME_NAME}.lnk" "$INSTDIR\${GAME_EXE}"
  CreateShortcut "$SMPROGRAMS\${GAME_NAME}.lnk" "$INSTDIR\${GAME_EXE}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${GAME_NAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${GAME_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "Gazhenko"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${GAME_EXE}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" ${INSTALLED_KB}
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
SectionEnd

Function un.onInit
  SetShellVarContext current
  SetRegView 64
  StrCpy $INSTDIR "$LOCALAPPDATA\Programs\${GAME_ID}"
  ReadRegStr $0 HKCU "${UNINSTALL_KEY}" "InstallLocation"
  ${If} $0 != $INSTDIR
    MessageBox MB_OK|MB_ICONSTOP "This game is not registered as installed for this Windows account."
    SetErrorLevel 1
    Quit
  ${EndIf}
FunctionEnd

Section "Uninstall"
  ; First remove the executable. If it is locked, leave everything else in place.
  ClearErrors
  Delete "$INSTDIR\${GAME_EXE}"
  ${If} ${Errors}
    MessageBox MB_OK|MB_ICONSTOP "Close ${GAME_NAME}, then try removing it again."
    SetErrorLevel 1
    Abort
  ${EndIf}
  ; Delete only files shipped with this version. Extra user files and saves survive.
  !include "uninstall-files.nsh"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\${GAME_NAME}.lnk"
  Delete "$SMPROGRAMS\${GAME_NAME}.lnk"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
SectionEnd
