# Voice analysis: STT (Whisper or Vosk) + basic prosody via librosa.
from pydub import AudioSegment
import numpy as np
import librosa
import io
from faster_whisper import WhisperModel

class STTResult(dict):
    text: str

def convert_to_wav_bytes(file_bytes: bytes, mime_type: str) -> bytes:
    audio = AudioSegment.from_file(io.BytesIO(file_bytes), format=mime_type.split("/")[-1])
    buf = io.BytesIO()
    audio.set_channels(1).set_frame_rate(16000).export(buf, format="wav")
    return buf.getvalue()

def transcribe_bytes(wav_bytes: bytes, engine: str = "whisper") -> STTResult:
    try:
        if engine == "vosk":
            from vosk import Model, KaldiRecognizer
            import json, wave
            # Expecting a local Vosk model at ./models/vosk (change path if needed)
            model = Model("models/vosk")
            wf = wave.open(io.BytesIO(wav_bytes), "rb")
            rec = KaldiRecognizer(model, wf.getframerate())
            res_text = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    pass
            final = rec.FinalResult()
            res = json.loads(final)
            return {"text": res.get("text", "").strip()}
        else:
            from faster_whisper import WhisperModel
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            y, sr = librosa.load(io.BytesIO(wav_bytes), sr=16000)
            segments, _ = model.transcribe(y, language="en")
            text = " ".join([seg.text for seg in segments])
            return {"text": text.strip()}
    except Exception as e:
        return {"text": "", "error": str(e)}

def prosody_features(wav_bytes: bytes) -> dict:
    try:
        y, sr = librosa.load(io.BytesIO(wav_bytes), sr=16000)
        # Energy
        rms = float(librosa.feature.rms(y=y).mean())
        # Pitch estimation via librosa.yin
        f0 = librosa.yin(y, fmin=50, fmax=500, sr=sr)
        pitch_hz = float(np.nanmedian(f0)) if np.isfinite(f0).any() else 0.0
        # Speech rate proxy via zero-crossing rate
        zcr = float(librosa.feature.zero_crossing_rate(y).mean())
        return {
            "energy_rms": rms,
            "pitch_hz": pitch_hz,
            "zcr": zcr,
        }
    except Exception as e:
        return {"error": str(e)}
