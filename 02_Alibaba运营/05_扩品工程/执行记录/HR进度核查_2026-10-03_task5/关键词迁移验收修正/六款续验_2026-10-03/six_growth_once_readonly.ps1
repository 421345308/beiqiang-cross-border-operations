param([ValidateSet('open','read','scroll','home')][string]$Mode='read',[string]$Name='editor',[int]$Pages=1)
$ErrorActionPreference='Stop'
$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type 'using System;using System.Runtime.InteropServices;public class KeywordView { [DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);[DllImport("user32.dll")]public static extern IntPtr GetForegroundWindow();[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();[DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr h,int c);}'
[void][KeywordView]::SetProcessDPIAware()
$w=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]16452386)
if($w.Current.ProcessId -ne 20640){throw 'Chrome identity changed'}
$rect=$w.Current.BoundingRectangle
if($rect.X -lt -100 -or $rect.Y -lt -100 -or $rect.Height -lt 700){throw 'Actual browser unavailable'}
[void][KeywordView]::SetForegroundWindow([IntPtr]16452386)
Start-Sleep -Milliseconds 300
if([KeywordView]::GetForegroundWindow() -ne [IntPtr]16452386){throw 'Foreground unavailable'}
$out=Join-Path $PSScriptRoot 'six_version_acceptance_resume/growth'
[void](New-Item -ItemType Directory -Path $out -Force)
$nav=Join-Path $out 'growth_navigation.json'
$bar=$w.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'地址和搜索栏'))
if($Mode -eq 'open'){
 if(Test-Path -LiteralPath $nav){throw 'Already opened: inspect existing tab'}
 [Windows.Forms.SendKeys]::SendWait('^t');Start-Sleep -Milliseconds 350
 $bar=$w.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'地址和搜索栏'))
 $url='https://hz-productposting.alibaba.com/product_operate/product_growth.htm'
 $bar.SetFocus();$bar.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($url)
 [Windows.Forms.SendKeys]::SendWait('{ENTER}')
 @{url=$url;atUTC=(Get-Date).ToUniversalTime().ToString('o');platformMutations=0;newTab=$true}|ConvertTo-Json|Set-Content -LiteralPath $nav -Encoding utf8
 Start-Sleep -Seconds 8
}
$address=$bar.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).Current.Value
if($address -notmatch 'hz-productposting\.alibaba\.com/product_operate/product_growth\.htm'){throw ('Unexpected page: '+$address)}
if($Mode -in @('home','scroll')){
 $doc=$w.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Document))|Select-Object -Last 1
 $doc.SetFocus()
 if($Mode -eq 'home'){[Windows.Forms.SendKeys]::SendWait('^{HOME}')}else{1..$Pages|ForEach-Object{[Windows.Forms.SendKeys]::SendWait('{PGDN}');Start-Sleep -Milliseconds 200}}
 Start-Sleep -Milliseconds 500
}
$cache=[Windows.Automation.CacheRequest]::new()
foreach($p in @([Windows.Automation.AutomationElement]::NameProperty,[Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.AutomationElement]::AutomationIdProperty,[Windows.Automation.AutomationElement]::IsOffscreenProperty,[Windows.Automation.AutomationElement]::IsEnabledProperty,[Windows.Automation.AutomationElement]::BoundingRectangleProperty)){$cache.Add($p)}
$scope=$cache.Activate()
try{$els=$w.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)}finally{$scope.Dispose()}
$rows=@($els|Where-Object{$_.Cached.ControlType.ProgrammaticName -in @('ControlType.Text','ControlType.Hyperlink','ControlType.Button','ControlType.Document','ControlType.Edit','ControlType.CheckBox','ControlType.RadioButton','ControlType.ComboBox')}|ForEach-Object{
 $b=$_.Cached.BoundingRectangle;$v=$null
 if($_.Cached.ControlType.ProgrammaticName -eq 'ControlType.Edit'){$vp=$null;if($_.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){$v=$vp.Current.Value}}
 [pscustomobject]@{name=$_.Cached.Name;id=$_.Cached.AutomationId;type=$_.Cached.ControlType.ProgrammaticName;value=$v;offscreen=$_.Cached.IsOffscreen;enabled=$_.Cached.IsEnabled;x=$b.X;y=$b.Y;width=$b.Width;height=$b.Height}
})
@{atUTC=(Get-Date).ToUniversalTime().ToString('o');address=$address;rows=$rows;platformMutations=0}|ConvertTo-Json -Depth 7|Set-Content -LiteralPath (Join-Path $out ($Name+'.json')) -Encoding utf8
$b=$w.Current.BoundingRectangle;$bmp=[Drawing.Bitmap]::new([int]$b.Width,[int]$b.Height);$g=[Drawing.Graphics]::FromImage($bmp)
try{$g.CopyFromScreen([int]$b.X,[int]$b.Y,0,0,$bmp.Size);$bmp.Save((Join-Path $out ($Name+'.png')),[Drawing.Imaging.ImageFormat]::Png)}finally{$g.Dispose();$bmp.Dispose()}
$rows|Where-Object{-not $_.offscreen -and $_.y -ge 160}|Select-Object name,type,value,x,y|ConvertTo-Json -Depth 4
