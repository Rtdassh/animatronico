param([string]$TextFile, [string]$OutputFile)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voice = $speaker.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name.StartsWith('es') } | Select-Object -First 1
    if ($voice) { $speaker.SelectVoice($voice.VoiceInfo.Name) }
    $speaker.SetOutputToWaveFile($OutputFile)
    $speaker.Speak([System.IO.File]::ReadAllText($TextFile))
} finally { $speaker.Dispose() }
