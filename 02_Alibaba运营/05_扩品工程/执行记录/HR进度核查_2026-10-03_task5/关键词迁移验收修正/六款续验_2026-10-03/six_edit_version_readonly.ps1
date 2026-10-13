param([ValidateSet('2627BSK','805','H219','F2888','936')][string]$Product='2627BSK',[ValidateSet('open','read','selling','scroll','home')][string]$Mode='read',[string]$Name='notice',[int]$Pages=1)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type 'using System;using System.Runtime.InteropServices;public class SixVersionRead { [DllImport("user32.dll")]public static extern bool SetProcessDPIAware();[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);[DllImport("user32.dll")]public static extern IntPtr GetForegroundWindow(); }'
[void][SixVersionRead]::SetProcessDPIAware()
$w=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]16452386)
if($w.Current.ProcessId -ne 20640){throw 'Original spq Chrome identity changed'}
$rect=$w.Current.BoundingRectangle
if($rect.X -lt -100 -or $rect.Y -lt -100 -or $rect.Height -lt 700){throw 'Actual browser window unavailable; do not capture a hidden window'}
[void][SixVersionRead]::SetForegroundWindow([IntPtr]16452386);Start-Sleep -Milliseconds 250
if([SixVersionRead]::GetForegroundWindow() -ne [IntPtr]16452386){throw 'Foreground unavailable; preserve dialogs'}
$out=Join-Path $PSScriptRoot ('six_version_acceptance_resume/'+$Product);[void](New-Item -ItemType Directory -Path $out -Force)
$check=Get-Content -LiteralPath (Join-Path $PSScriptRoot ('hr_public_readonly_20261003/'+$Product+'_minimal_checklist.json')) -Raw -Encoding utf8|ConvertFrom-Json
$nav=Join-Path $out 'navigation.json'
$bar=$w.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'地址和搜索栏'))
if($Mode -eq 'open'){
 if($Product -eq '2627BSK' -or (Test-Path -LiteralPath $nav)){throw 'Existing product tab must be reused, no duplicate open'}
 [Windows.Forms.SendKeys]::SendWait('^t');Start-Sleep -Milliseconds 300
 $bar=$w.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'地址和搜索栏'))
 $url='https://post.alibaba.com/product/publish.htm?itemId='+$check.product_id+'&from=common&catId='+$check.category_id
 $bar.SetFocus();$bar.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($url);[Windows.Forms.SendKeys]::SendWait('{ENTER}')
 @{atUTC=(Get-Date).ToUniversalTime().ToString('o');url=$url;newReadOnlyTab=$true;platformWrites=0}|ConvertTo-Json|Set-Content -LiteralPath $nav -Encoding utf8
 Start-Sleep -Seconds 10
}
$address=$bar.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).Current.Value
if($address -notmatch ('itemId='+$check.product_id+'(?:&|$)')){throw 'Active editor is not exact assigned product'}
if($Mode -eq 'selling'){
 $a=@($w.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'去填写'))|Where-Object{-not $_.Current.IsOffscreen})
 if($a.Count -ne 1){throw 'Unique observed selling-point read navigation absent'}
 $a[0].GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke();Start-Sleep -Milliseconds 500
}elseif($Mode -in @('home','scroll')){
 $doc=$w.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Document))|Select-Object -Last 1
 $doc.SetFocus()
 if($Mode -eq 'home'){[Windows.Forms.SendKeys]::SendWait('^{HOME}')}else{1..$Pages|ForEach-Object{[Windows.Forms.SendKeys]::SendWait('{PGDN}');Start-Sleep -Milliseconds 200}}
 Start-Sleep -Milliseconds 400
}
$notices=@();$documents=@()
foreach($doc in $w.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Document))){
 $tp=$null;if($doc.TryGetCurrentPattern([Windows.Automation.TextPattern]::Pattern,[ref]$tp)){
  $t=$tp.DocumentRange.GetText(-1);$i=$t.IndexOf('副标题和关键词')
  if($i -ge 0){$notices+=@{text=$t.Substring([Math]::Max(0,$i-1)).Split("`n")[0];titleBound=$t.Contains($check.title)}}
  if($t.Contains($check.title)){$documents+=@{knownTitleBound=$true;pageText=$t}}
 }
}
$cache=[Windows.Automation.CacheRequest]::new()
foreach($p in @([Windows.Automation.AutomationElement]::NameProperty,[Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.AutomationElement]::AutomationIdProperty,[Windows.Automation.AutomationElement]::IsOffscreenProperty,[Windows.Automation.AutomationElement]::BoundingRectangleProperty)){$cache.Add($p)}
$scope=$cache.Activate();try{$all=$w.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)}finally{$scope.Dispose()}
$rows=@($all|Where-Object{$_.Cached.ControlType.ProgrammaticName -in @('ControlType.Text','ControlType.Button','ControlType.Edit','ControlType.Document')}|ForEach-Object{
 $b=$_.Cached.BoundingRectangle;$v=$null
 if($_.Cached.ControlType.ProgrammaticName -eq 'ControlType.Edit'){$vp=$null;if($_.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){$v=$vp.Current.Value}}
 @{name=$_.Cached.Name;type=$_.Cached.ControlType.ProgrammaticName;id=$_.Cached.AutomationId;value=$v;offscreen=$_.Cached.IsOffscreen;x=$b.X;y=$b.Y;width=$b.Width;height=$b.Height}
})
@{atUTC=(Get-Date).ToUniversalTime().ToString('o');candidate=$Product;productId=$check.product_id;categoryId=$check.category_id;address=$address;notice=$notices;documents=$documents;rows=$rows;mode=$Mode;platformWrites=0}|ConvertTo-Json -Depth 7|Set-Content -LiteralPath (Join-Path $out ($Name+'.json')) -Encoding utf8
$b=$w.Current.BoundingRectangle;$bmp=[Drawing.Bitmap]::new([int]$b.Width,[int]$b.Height);$g=[Drawing.Graphics]::FromImage($bmp)
try{$g.CopyFromScreen([int]$b.X,[int]$b.Y,0,0,$bmp.Size);$bmp.Save((Join-Path $out ($Name+'.png')),[Drawing.Imaging.ImageFormat]::Png)}finally{$g.Dispose();$bmp.Dispose()}
@{product=$Product;mode=$Mode;notices=$notices.Count;atUTC=(Get-Date).ToUniversalTime().ToString('o');platformWrites=0}|ConvertTo-Json
