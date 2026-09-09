"""
Voice Scribe - Speech Recognition & Voice Interaction Engine
Captures acoustic input, manages noise calibration with locked threshold,
and robustly classifies voice tokens with homophone matching.
"""

import re
from typing import Tuple, List, Optional
import speech_recognition as sr


def normalize_speech(text: str) -> str:
    """
    Cleans transcribed text by removing punctuation, extra spaces, and normalizing common tokens.
    Examples:
        'Ok.' -> 'ok'
        'O.K.' -> 'ok'
        'Right' -> 'write' (in confirmation context)
        'New line.' -> 'new line'
    """
    cleaned = re.sub(r"[^\w\s]", "", text).strip().lower()
    # Normalize variants of 'o k' to 'ok'
    cleaned = re.sub(r"\bo\s+k\b", "ok", cleaned)
    return cleaned


class VoiceEngine:
    """Handles microphone capture and token classification for the Voice Scribe interaction loop."""

    def __init__(self, ambient_duration: float = 1.0, phrase_timeout: float = 8.0):
        self.ambient_duration = ambient_duration
        self.phrase_timeout = phrase_timeout
        self.recognizer = sr.Recognizer()
        self.microphone = None

    @staticmethod
    def list_microphones() -> List[str]:
        """Returns the list of available audio input devices detected on the host system."""
        return sr.Microphone.list_microphone_names()

    def calibrate(self, device_index: Optional[int] = None):
        """Initializes the microphone and calibrates energy thresholds with locked sensitivity."""
        print("[*] Initializing audio capture interface...")
        if device_index is not None:
            self.microphone = sr.Microphone(device_index=device_index)
        else:
            self.microphone = sr.Microphone()

        with self.microphone as source:
            print(f"[*] Calibrating microphone for ambient acoustic noise ({self.ambient_duration:.1f}s)...")
            self.recognizer.adjust_for_ambient_noise(source, duration=self.ambient_duration)

            # Clamp energy threshold so it remains sensitive to short words like 'OK'
            calibrated = self.recognizer.energy_threshold
            # Keep threshold responsive between 80 and 220
            clamped = max(80.0, min(calibrated, 220.0))
            self.recognizer.energy_threshold = clamped

            # Lock dynamic threshold to prevent quiet commands from being ignored after loud speech
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.pause_threshold = 0.5
            self.recognizer.phrase_threshold = 0.1
            self.recognizer.non_speaking_duration = 0.25

            print(f"[OK] Sensitivity locked at energy threshold: {self.recognizer.energy_threshold:.1f}")

    def listen_and_classify(self, listen_timeout: float = 4.0) -> Tuple[str, str]:
        """
        Listens for a spoken phrase with a timeout so caller can handle keyboard input.
        Returns:
            (action, payload) where action is one of:
            - 'CONFIRM'
            - 'INLINE_CONFIRM'
            - 'NEW_LINE'
            - 'CLEAR'
            - 'TEXT'
            - 'TIMEOUT' (when silence timed out, safe to loop)
            - 'EMPTY' (when indistinct audio occurred)
            - 'ERROR' (when an API or network error occurs)
        """
        if not self.microphone:
            raise RuntimeError("Microphone has not been calibrated. Call calibrate() first.")

        try:
            with self.microphone as source:
                audio_data = self.recognizer.listen(
                    source,
                    timeout=listen_timeout,
                    phrase_time_limit=self.phrase_timeout
                )

            # Transcribe via Google Speech Recognition
            raw_text = self.recognizer.recognize_google(audio_data).strip()
            norm = normalize_speech(raw_text)
            print(f"    [HEARD]: \"{raw_text}\" (Normalized: \"{norm}\")")

            # --- Extended Token Mappings ---
            # Confirmation words (including speech-to-text homophones like 'right' for 'write')
            confirm_set = {
                "ok", "okay", "confirm", "write it", "write", "right",
                "yes", "yeah", "yep", "go", "proceed", "draw", "done", "plot", "k"
            }

            # Trigger 1: Standalone Confirmation
            if norm in confirm_set:
                return "CONFIRM", raw_text

            # Trigger 2: Carriage Feed / Newline
            if norm in ["new line", "newline", "enter", "next line", "line feed", "line"]:
                return "NEW_LINE", raw_text

            # Trigger 3: Discard Preview Buffer
            if norm in ["clear", "cancel", "discard", "erase", "delete", "no", "reset"]:
                return "CLEAR", raw_text

            # Trigger 4: In-line Confirmation (Spoke a sentence ending with confirmation token)
            for cw in ["ok", "okay", "confirm", "write", "right", "draw"]:
                suffix = " " + cw
                if norm.endswith(suffix):
                    cutoff = len(norm) - len(suffix)
                    actual_text = raw_text[:cutoff].strip()
                    actual_text = re.sub(r"[.,;!?]+$", "", actual_text).strip()
                    if actual_text:
                        return "INLINE_CONFIRM", actual_text

            # Trigger 5: In-line Command prefix (e.g. "write hello world" or "draw hello world")
            for prefix in ["write ", "right ", "draw ", "plot "]:
                if norm.startswith(prefix):
                    actual_text = raw_text[len(prefix):].strip()
                    if actual_text:
                        return "INLINE_CONFIRM", actual_text

            # Default: Dictated text sentence
            return "TEXT", raw_text

        except sr.WaitTimeoutError:
            # Periodic silence timeout; yields control back to orchestrator
            return "TIMEOUT", ""

        except sr.UnknownValueError:
            print("    [!] (Audio heard, but could not transcribe words. Speak clearly.)")
            return "EMPTY", ""

        except sr.RequestError as req_err:
            print(f"[!] Speech API connectivity warning: {req_err}")
            return "ERROR", str(req_err)
