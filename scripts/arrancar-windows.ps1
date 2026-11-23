# Abre el Chrome de TARS con ventana visible, en el monitor secundario, y lo verifica.
# Perfil limpio: el anterior quedó atado al modo headless.
$ErrorActionPreference = 'Continue'
$log = 'C:\tars-chrome\abrir3.log'
function Log($t) { $t | Out-File -FilePath $log -Append -Encoding utf8 }
"=== $(Get-Date -Format s) sesion=$([System.Diagnostics.Process]::GetCurrentProcess().SessionId) ===" | Out-File -FilePath $log -Encoding utf8

Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W4 {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr p);
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int t, bool repaint);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
function Ventanas($pids) {
  $lista = New-Object System.Collections.ArrayList
  $cb = [W4+EnumWindowsProc]{
    param($h, $p)
    $proc = 0
    [void][W4]::GetWindowThreadProcessId($h, [ref]$proc)
    if ($pids -contains $proc) {
      $n = [W4]::GetWindowTextLength($h)
      $sb = New-Object System.Text.StringBuilder ($n + 2)
      [void][W4]::GetWindowText($h, $sb, $sb.Capacity)
      $r = New-Object W4+RECT
      [void][W4]::GetWindowRect($h, [ref]$r)
      [void]$lista.Add([pscustomobject]@{ handle=$h; pid=$proc; titulo=$sb.ToString(); visible=[W4]::IsWindowVisible($h)
        minimizada=[W4]::IsIconic($h); x=$r.Left; y=$r.Top; w=($r.Right-$r.Left); h=($r.Bottom-$r.Top) })
    }
    return $true
  }
  [void][W4]::EnumWindows($cb, [IntPtr]::Zero)
  return $lista
}

# 1. Cerrar todo lo de ese perfil
for ($i = 0; $i -lt 4; $i++) {
  $v = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -like '*tars-chrome*' }
  if (-not $v) { break }
  $v | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 2
}
# 2. NO se borra el perfil: ahí vive la sesión una vez que el usuario se loguea.
if (Test-Path 'C:\tars-chrome\Default') { Log 'perfil_conservado' }

# 3. Monitor destino: el secundario, en la MITAD SUPERIOR (ZONA=arriba|abajo|completo)
$zona = if ($env:TARS_ZONA) { $env:TARS_ZONA } else { 'arriba' }
$pantallas = [System.Windows.Forms.Screen]::AllScreens
foreach ($p in $pantallas) { Log ("monitor {0} primario={1} x={2} y={3} {4}x{5}" -f $p.DeviceName,$p.Primary,$p.Bounds.X,$p.Bounds.Y,$p.Bounds.Width,$p.Bounds.Height) }
$seg = $pantallas | Where-Object { -not $_.Primary } | Select-Object -First 1
if (-not $seg) { $seg = $pantallas[0] }
$b = $seg.Bounds
$ancho = $b.Width - 8
switch ($zona) {
  'arriba'  { $alto = [int]([math]::Floor($b.Height / 2)) - 8; $x = $b.X + 4; $y = $b.Y + 4 }
  'abajo'   { $alto = [int]([math]::Floor($b.Height / 2)) - 8; $x = $b.X + 4; $y = $b.Y + [int]([math]::Floor($b.Height / 2)) + 4 }
  default   { $alto = $b.Height - 40; $x = $b.X + 4; $y = $b.Y + 4 }
}
Log ("zona=" + $zona + " ventana=" + $x + "," + $y + " " + $ancho + "x" + $alto)

$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$linea = '--user-data-dir=C:\tars-chrome --remote-debugging-port=9222 --no-first-run --no-default-browser-check --window-position=' + $x + ',' + $y + ' --window-size=' + $ancho + ',' + $alto + ' https://users.nexusmods.com/auth/sign_in'
Log ("lanzando: " + $linea)
Start-Process -FilePath $chrome -ArgumentList $linea

# 4. Verificar
$ok = $null
for ($i = 0; $i -lt 25; $i++) {
  Start-Sleep -Seconds 1
  $pids = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -like '*tars-chrome*' } | Select-Object -ExpandProperty ProcessId
  $ok = Ventanas $pids | Where-Object { $_.titulo -ne '' -and $_.w -gt 200 } | Select-Object -First 1
  if ($ok) { break }
}
if ($ok) {
  [void][W4]::ShowWindow($ok.handle, 9)
  [void][W4]::MoveWindow($ok.handle, $x, $y, $ancho, $alto, $true)
  [void][W4]::SetForegroundWindow($ok.handle)
  Start-Sleep -Milliseconds 700
  $r = New-Object W4+RECT
  [void][W4]::GetWindowRect($ok.handle, [ref]$r)
  Log ("VENTANA_OK hwnd={0} rect={1},{2} {3}x{4} visible={5} min={6} titulo='{7}'" -f $ok.handle,$r.Left,$r.Top,($r.Right-$r.Left),($r.Bottom-$r.Top),[W4]::IsWindowVisible($ok.handle),[W4]::IsIconic($ok.handle),$ok.titulo)
} else { Log 'SIN_VENTANA' }
try { $v = Invoke-RestMethod 'http://127.0.0.1:9222/json/version' -TimeoutSec 5; Log ("ua=" + $v.'User-Agent') } catch { Log 'cdp_fail' }
