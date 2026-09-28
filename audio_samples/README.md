# Matched audio samples

Every condition contains the same eight source stems, so audio may be compared across folders by matching its filename. The set has five FakeAVCeleb clips (one from each descent group), two LibriSpeech clips, and one ASVspoof 2021 clip. `manifest.json` records the exact stems and condition coverage.

## Folder guide

| Folder | What it represents |
| --- | --- |
| `clean_bonafide/` | Original, unprotected bona fide source recordings. |
| `clean_synthesize/<synthesizer>/` | Speech synthesized from each clean recording by `SV2TTS`, `F5-TTS`, or `Seed-VC`. |
| `cloaked_bonafide/<cloaking method>/` | A bona fide recording after the named voice-cloaking method is applied. |
| `cloaked_synthesize/<cloaking method>/<synthesizer>/` | Speech synthesized from the corresponding cloaked recording. |
| `restoration_techniques/<restoration method>/<cloaking method>/` | A cloaked bona fide recording after the named restoration/decloaking method; this is not newly synthesized speech. |
| `restored_synthesize/<restoration method>/<cloaking method>/<synthesizer>/` | Speech synthesized from the corresponding restored/decloaked recording. |

The cloaking-method directory names use the paper titles, with a short label in parentheses: AntiFake, attack-vc, POP, and ProtectYourAudio.

The ten restoration methods are Adaptive Frequency Filtering, Downsampling, Ensemble Averaging, High-Pass Filtering, Low-Pass Filtering, Mel-Spectrogram Inversion, Quantization, Simulated Re-Recording, Spectral Subtraction, and Upsampling.
