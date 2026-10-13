param([ValidateSet('navigate','read','scroll','click','home','hover')][string]$Mode='read',[ValidateSet('2627BSK','805','H219','F2888','936','M001')][string]$Product='2627BSK',[string]$Name='top',[string]$ClickName='',[int]$Occurrence=0,[int]$Pages=1,[int]$TargetX=0,[int]$TargetY=0)
$ErrorActionPreference='Stop'
$OutputEncoding=[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new()
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class HRPublicRead { [DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h); [DllImport("user32.dll")]public static extern IntPtr GetForegroundWindow(); [DllImport("user32.dll")]public static extern bool SetProcessDPIAware(); [DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr h,int c); [DllImport("user32.dll")]public static extern void mouse_event(uint f,uint dx,uint dy,uint d,UIntPtr x); }'
[void][HRPublicRead]::SetProcessDPIAware()
$window=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]16452386)
if($window.Current.ProcessId -ne 20640){throw 'Original spq Chrome identity changed'}
$rect=$window.Current.BoundingRectangle
if($rect.X -lt -100 -or $rect.Y -lt -100 -or $rect.Height -lt 700){throw 'Actual browser unavailable'}
[void][HRPublicRead]::SetForegroundWindow([IntPtr]16452386)
Start-Sleep -Milliseconds 300
if([HRPublicRead]::GetForegroundWindow() -ne [IntPtr]16452386){throw 'Exclusive Chrome foreground unavailable'}
$out=Join-Path $PSScriptRoot ('six_version_acceptance_resume/'+$Product+'/public')
[void](New-Item -ItemType Directory -Path $out -Force)
$nav=Join-Path $out 'navigation.json'
if($Mode -eq 'navigate'){
 if(Test-Path -LiteralPath $nav){throw 'Already navigated this product; read existing tab, no blocked visit retries'}
 [Windows.Forms.SendKeys]::SendWait('^t');Start-Sleep -Milliseconds 350
 $check=Get-Content -LiteralPath (Join-Path $PSScriptRoot ('hr_public_readonly_20261003/'+$Product+'_minimal_checklist.json')) -Raw -Encoding utf8|ConvertFrom-Json
 $url=$check.public_url
 if($url -notmatch ('^https://www\.alibaba\.com/product-detail/[^?]+_'+$check.product_id+'\.html$')){throw 'Exact formal public URL invalid'}
 $bar=$window.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)|Where-Object{$_.Current.ControlType.ProgrammaticName -eq 'ControlType.Edit' -and $_.Current.Name -eq '地址和搜索栏'}|Select-Object -First 1
 if(-not $bar){throw 'Observed address bar absent'}
 $bar.SetFocus();$bar.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($url);[Windows.Forms.SendKeys]::SendWait('{ENTER}')
 @{url=$url;atUTC=(Get-Date).ToUniversalTime().ToString('o');writes=0;newTab=$true}|ConvertTo-Json|Set-Content -LiteralPath $nav -Encoding utf8
 Start-Sleep -Seconds 10
}elseif($Mode -eq 'scroll' -or $Mode -eq 'home'){
 $doc=$window.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Document))|Select-Object -Last 1
 if($doc){$doc.SetFocus()}
 if($Mode -eq 'home'){[Windows.Forms.SendKeys]::SendWait('^{HOME}')}
 else{1..$Pages|ForEach-Object{[Windows.Forms.SendKeys]::SendWait('{PGDN}');Start-Sleep -Milliseconds 200}}
 Start-Sleep -Milliseconds 700
}elseif($Mode -eq 'hover'){
 if($TargetX -lt 160 -or $TargetX -gt 320 -or $TargetY -lt 300 -or $TargetY -gt 1050){throw 'Hover restricted to observed gallery thumbnail rail'}
 [Windows.Forms.Cursor]::Position=[Drawing.Point]::new($TargetX,$TargetY);Start-Sleep -Milliseconds 900
}elseif($Mode -eq 'click'){
 if($ClickName -notin @('Product descriptions','Product description','Descriptions')){throw 'Forbidden or empty read-only interaction'}
 $matches=@($window.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$ClickName))|Where-Object{-not $_.Current.IsOffscreen -and $_.Current.ControlType.ProgrammaticName -in @('ControlType.Button','ControlType.Hyperlink','ControlType.RadioButton','ControlType.CheckBox','ControlType.TabItem')})
 if($matches.Count -le $Occurrence){throw 'Observed accessible click target absent'}
 $el=$matches[$Occurrence];$pattern=$null
 if($el.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){$pattern.Invoke()}
 else{$b=$el.Current.BoundingRectangle;if($b.Width -le 0 -or $b.Height -le 0){throw 'Visible target bounds unavailable'};[Windows.Forms.Cursor]::Position=[Drawing.Point]::new([int]($b.X+$b.Width/2),[int]($b.Y+$b.Height/2));[HRPublicRead]::mouse_event(2,0,0,0,[UIntPtr]::Zero);[HRPublicRead]::mouse_event(4,0,0,0,[UIntPtr]::Zero)}
 Start-Sleep -Milliseconds 850
}
$cache=[Windows.Automation.CacheRequest]::new()
foreach($property in @([Windows.Automation.AutomationElement]::NameProperty,[Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.AutomationElement]::IsOffscreenProperty,[Windows.Automation.AutomationElement]::IsEnabledProperty,[Windows.Automation.AutomationElement]::BoundingRectangleProperty)){$cache.Add($property)}
$scope=$cache.Activate()
try{$all=$window.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)}finally{$scope.Dispose()}
$rows=@($all|Where-Object{$_.Cached.Name -and $_.Cached.ControlType.ProgrammaticName -in @('ControlType.Text','ControlType.Hyperlink','ControlType.Button','ControlType.Document','ControlType.Edit','ControlType.CheckBox','ControlType.RadioButton')}|ForEach-Object{$b=$_.Cached.BoundingRectangle;[pscustomobject]@{name=$_.Cached.Name;type=$_.Cached.ControlType.ProgrammaticName;offscreen=$_.Cached.IsOffscreen;enabled=$_.Cached.IsEnabled;x=$b.X;y=$b.Y;width=$b.Width;height=$b.Height}})
@{atUTC=(Get-Date).ToUniversalTime().ToString('o');title=$window.Current.Name;mode=$Mode;interaction=$ClickName;rows=$rows;platformMutations=0}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $out ($Name+'.json')) -Encoding utf8
$b=$window.Current.BoundingRectangle;$bmp=[Drawing.Bitmap]::new([int]$b.Width,[int]$b.Height);$graphics=[Drawing.Graphics]::FromImage($bmp)
try{$graphics.CopyFromScreen([int]$b.X,[int]$b.Y,0,0,$bmp.Size);$bmp.Save((Join-Path $out ($Name+'.png')),[Drawing.Imaging.ImageFormat]::Png)}finally{$graphics.Dispose();$bmp.Dispose()}
$rows|Where-Object{-not $_.offscreen -and $_.y -ge 170}|Select-Object -ExpandProperty name|Select-Object -Unique|Select-Object -First 150
