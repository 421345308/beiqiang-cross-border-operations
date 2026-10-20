param([Parameter(Mandatory=$true)][string]$InputFile,[Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null=[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null=[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$null=[Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
$script:asyncMethod=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'} | Select-Object -First 1
function Await-WinRT($Operation,[Type]$ResultType){$task=$script:asyncMethod.MakeGenericMethod($ResultType).Invoke($null,@($Operation));$task.Wait();return $task.Result}
$language=[Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | Select-Object -First 1
if($null -eq $language){throw 'No local OCR language is installed'}
$engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
$inputData=Get-Content -LiteralPath $InputFile -Raw -Encoding UTF8 | ConvertFrom-Json
$encoding=[System.Text.UTF8Encoding]::new($false);[Console]::OutputEncoding=$encoding
$seen=@{};if(Test-Path -LiteralPath $OutputFile){Get-Content -LiteralPath $OutputFile -Encoding UTF8 | ForEach-Object{if($_){$old=$_ | ConvertFrom-Json;$seen[$old.key]=$true}}}
$writer=[System.IO.StreamWriter]::new([System.IO.Path]::GetFullPath($OutputFile),$true,$encoding);$n=0
try{foreach($item in $inputData.items){
 if($seen.ContainsKey($item.key) -or !$item.file){continue}
 $bitmap=$null;$stream=$null
 try{
  $file=Await-WinRT ([Windows.Storage.StorageFile]::GetFileFromPathAsync([System.IO.Path]::GetFullPath($item.file))) ([Windows.Storage.StorageFile])
  $stream=Await-WinRT ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
  $decoder=Await-WinRT ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap=Await-WinRT ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result=Await-WinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $record=@{key=$item.key;text=$result.Text;language=$language.LanguageTag;state='OCR_EXTRACTED_NOT_VISUAL_ACCEPTANCE'}
 }catch{$record=@{key=$item.key;state='OCR_ERROR';error=$_.Exception.GetType().Name}}
 finally{if($bitmap){$bitmap.Dispose()};if($stream){$stream.Dispose()}}
 $writer.WriteLine(($record | ConvertTo-Json -Compress));$writer.Flush();$n++
 if($n % 100 -eq 0){Write-Output ('OCR_IMAGES '+$n)}
}}finally{$writer.Dispose()}
Write-Output ('OCR_COMPLETED_NEW_IMAGES '+$n)
