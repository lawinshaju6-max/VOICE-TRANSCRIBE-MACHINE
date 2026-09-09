#!/usr/bin/env python3
"""
Voice Scribe - Microphone & Audio Ingestion Diagnostic Tool
Tests microphone connectivity, noise profile calibration, and speech recognition
without needing any hardware or serial ports connected.
"""

import sys
import speech_recognition as sr
from voice_engine import VoiceEngine


def run_audio_diagnostic():
    print("==================================================================")
    print("           VOICE SCRIBE AUDIO & MICROPHONE TEST                   ")
    print("==================================================================")

    # 1. Enumerate available audio input devices
    print("\n[*] Detected Audio Input Devices:")
    mics = VoiceEngine.list_microphones()
    if not mics:
        print("[!] No microphone devices detected on this system.")
        print("[!] Please plug in your USB microphone headset and re-run.")
        return

    for idx, name in enumerate(mics):
        print(f"    [{idx}] {name}")

    # 2. Test default microphone capture
    print("\n[*] Testing default microphone...")
    voice = VoiceEngine(ambient_duration=1.5, phrase_timeout=6.0)

    try:
        voice.calibrate()
    except Exception as e:
        print(f"[!] Failed to access microphone: {e}")
        print("[!] Verify microphone permissions in Windows Settings -> Privacy -> Microphone.")
        return

    print("\n------------------------------------------------------------------")
    print(" TEST PROMPT: Speak a short phrase clearly now (e.g. 'Hello Voice Scribe')")
    print("------------------------------------------------------------------")

    action, text = voice.listen_and_classify()

    print("\n------------------------------------------------------------------")
    print(f" RESULT ACTION     : {action}")
    print(f" TRANSCRIBED TEXT  : '{text}'")
    print("------------------------------------------------------------------")

    if action == "TEXT":
        print("[OK] Audio capture and speech recognition are working properly!")
    elif action in ["NEW_LINE", "CONFIRM", "CLEAR"]:
        print(f"[OK] Successfully recognized voice control command: '{action}'!")
    elif action == "EMPTY":
        print("[!] Nothing audible detected. Speak closer to the microphone and try again.")
    elif action == "ERROR":
        print(f"[!] Recognition error: {text}")


if __name__ == "__main__":
    run_audio_diagnostic()
