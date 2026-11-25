"""OCR line checks (after the frozen extractor) and local speech-to-text."""

import io
import shutil
import wave

import numpy as np
import pytest

from backend.document_checks import check_items

PDF_TEXT = """CITY DIAGNOSTICS LABORATORY
Test                 Result   Units    Reference
Hemoglobin           11.2     g/dL     13.0-17.0
Platelet Count       95000    /uL      150000-450000
Fasting Glucose      108      mg/dL    70-100"""


def item(name, value, unit, rng):
    return {"concept_name_en": name, "normalized_value": value, "unit": unit, "reference_range": rng,
            "unit_status": "NORMALIZED", "requires_confirmation": False}


def test_unit_and_range_are_taken_from_the_values_own_line():
    # what the frozen extractor produced in a real test: platelets with the glucose range and a x10^9/L unit
    out = check_items([item("Platelet Count", "95000", "x10^9/L", "70-100"),
                       item("Hemoglobin (blood test)", "11.2", "g/dL", "13.0-17.0"),
                       item("Fasting Blood Sugar", "108", "mg/dL", "70-100")], PDF_TEXT)
    plt, hb, glu = out
    assert (plt["unit"], plt["reference_range"], plt["line_check"]) == ("/uL", "150000-450000", "corrected")
    assert plt["requires_confirmation"] and "corrected" in plt["confirmation_reason"]
    assert hb["line_check"] == "verified" and glu["line_check"] == "verified"      # synonyms: sugar ~ glucose


def test_values_paired_with_the_wrong_test_are_flagged():
    # photo OCR returned cells out of order: "Hemoglobin = 95000" has no line containing both
    [hb] = check_items([item("Hemoglobin (blood test)", "95000", None, None)], PDF_TEXT)
    assert hb["line_check"] == "line_not_found" and hb["requires_confirmation"]


def test_medications_are_left_alone():
    med = {"medication_name": "Paracetamol", "normalized_value": None}
    assert check_items([med], PDF_TEXT) == [med]


# ------------------------------------------------------------------ speech
def _wav(seconds=1.0, rate=16000):
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    pcm = (0.2 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm.tobytes())
    return buf.getvalue()


def test_audio_is_decoded_to_16k_mono_with_ffmpeg():
    from backend import speech
    try:
        speech._ffmpeg()
    except speech.SpeechUnavailable:
        pytest.skip("ffmpeg not installed")
    samples = speech.decode(_wav(1.0, rate=44100))
    assert samples.dtype == np.float32 and abs(len(samples) - 16000) < 200
    with pytest.raises(ValueError):
        speech.decode(b"not audio at all")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.patient_memory import db as dbmod
    import backend.api.auth as auth
    dbmod.get_engine(f"sqlite:///{(tmp_path / 'sp.db').as_posix()}")
    monkeypatch.setattr(auth, "_failed", {})
    from backend.main import app
    yield TestClient(app)
    dbmod._engine = None


def test_speech_route_requires_login_and_valid_audio(client, monkeypatch):
    from backend import speech
    monkeypatch.setattr(speech, "transcribe", lambda data, language=None: {"text": "I have a cough", "language": "en"})
    assert client.post("/api/v2/speech/transcribe", files={"audio": ("q.webm", _wav(), "audio/webm")}).status_code == 401
    tok = client.post("/api/v2/auth/register", json={"email": "v@example.org", "password": "correct-horse-1",
                                                       "given_name": "V"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/api/v2/speech/transcribe", files={"audio": ("q.webm", _wav(), "audio/webm")}, headers=h)
    assert r.status_code == 200 and r.json()["text"] == "I have a cough"
    assert client.post("/api/v2/speech/transcribe", files={"audio": ("q.webm", b"", "audio/webm")}, headers=h).status_code == 400
    big = b"0" * (10 * 1024 * 1024 + 1)
    assert client.post("/api/v2/speech/transcribe", files={"audio": ("q.webm", big, "audio/webm")}, headers=h).status_code == 413
