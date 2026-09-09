#!/usr/bin/env python3
"""
Voice Scribe: Production Speech-to-GCode Motion Controller Orchestrator
Translates spoken natural language into physical handwriting on paper,
with dual Voice & Keyboard confirmation support.
"""

import os
import sys
import json
import time

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

from grbl_controller import GrblMotionStreamer
from vector_compiler import VectorLayoutCompiler
from voice_engine import VoiceEngine


def load_config():
    """Loads configuration parameters from config.json with robust fallbacks."""
    default_config = {
        "serial": {
            "port": "COM8",
            "auto_detect": True,
            "baud_rate": 115200,
            "boot_delay_seconds": 2.5,
            "timeout": 12.0
        },
        "motion": {
            "cmd_pen_up": "M03 S90",
            "cmd_pen_down": "M03 S0",
            "servo_dwell": 0.35,
            "rapid_feed": 1800,
            "draw_feed": 800
        },
        "geometry": {
            "page_width": 170.0,
            "page_height": 290.0,
            "margin_left": 15.0,
            "start_y": 270.0,
            "line_spacing": 9.5,
            "font_scale": 0.28
        },
        "speech": {
            "ambient_duration": 1.0,
            "phrase_timeout": 8.0
        }
    }

    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for section in default_config:
                    if section in loaded:
                        default_config[section].update(loaded[section])
        except Exception as e:
            print(f"[!] Warning reading config.json: {e}. Using default values.")

    return default_config


def check_keyboard_trigger() -> str:
    """Checks for non-blocking keyboard presses on Windows."""
    if not HAS_MSVCRT:
        return ""
    if msvcrt.kbhit():
        ch = msvcrt.getch()
        # Handle Enter (\r or \n) or Space
        if ch in [b"\r", b"\n", b" "]:
            return "CONFIRM"
        elif ch in [b"\x08", b"c", b"C"]:  # Backspace or 'c'
            return "CLEAR"
        elif ch in [b"n", b"N"]:
            return "NEW_LINE"
        elif ch == b"\x1b":  # ESC
            return "EXIT"
    return ""


def run_orchestrator():
    """Main execution orchestrator for Voice Scribe."""
    cfg = load_config()

    print("==================================================================")
    print("  VOICE SCRIBE :: AUTONOMOUS ROBOTIC PHYSICAL WRITING PLATFORM    ")
    print("==================================================================")

    # 1. Initialize Hardware Motion Streamer
    s_cfg = cfg["serial"]
    m_cfg = cfg["motion"]
    g_cfg = cfg["geometry"]

    streamer = GrblMotionStreamer(
        port=s_cfg.get("port", "COM8"),
        baud_rate=s_cfg.get("baud_rate", 115200),
        auto_detect=s_cfg.get("auto_detect", True),
        boot_delay=s_cfg.get("boot_delay_seconds", 2.5),
        cmd_pen_up=m_cfg.get("cmd_pen_up", "M03 S90"),
        cmd_pen_down=m_cfg.get("cmd_pen_down", "M03 S0"),
        servo_dwell=m_cfg.get("servo_dwell", 0.35),
        rapid_feed=m_cfg.get("rapid_feed", 1800),
        draw_feed=m_cfg.get("draw_feed", 800),
        timeout=s_cfg.get("timeout", 12.0),
    )

    try:
        streamer.connect()
    except Exception as e:
        print(f"\n[!] Motion controller could not connect: {e}")
        print("[!] Check hardware.log for details.")
        return

    # 2. Initialize Vector Compiler & Layout Engine
    compiler = VectorLayoutCompiler(
        streamer=streamer,
        page_width=g_cfg.get("page_width", 170.0),
        page_height=g_cfg.get("page_height", 290.0),
        margin_left=g_cfg.get("margin_left", 15.0),
        start_y=g_cfg.get("start_y", 270.0),
        line_spacing=g_cfg.get("line_spacing", 9.5),
        font_scale=g_cfg.get("font_scale", 0.28),
    )
    compiler.reset_origin()

    # 3. Initialize Audio Ingestion Engine
    sp_cfg = cfg["speech"]
    voice = VoiceEngine(
        ambient_duration=sp_cfg.get("ambient_duration", 1.0),
        phrase_timeout=sp_cfg.get("phrase_timeout", 8.0),
    )
    voice.calibrate()

    print("\n[OK] ALL SUBSYSTEMS ONLINE & AWAITING INPUT")
    print("------------------------------------------------------------------")
    print(" Voice Commands:")
    print("  - DICTATION  : Speak sentence -> Stages text in preview.")
    print("  - CONFIRM    : Say 'OK', 'WRITE', or 'YES' (or press ENTER key).")
    print("  - FAST WRITE : Say sentence ending with 'OK' (e.g. 'Hydrogen OK').")
    print("  - PREFIX     : Say 'Write <sentence>' (e.g. 'Write Nitrogen').")
    print("  - NEW LINE   : Say 'NEW LINE' (or press 'n' key).")
    print("  - DISCARD    : Say 'CLEAR' (or press BACKSPACE key).")
    print("  - EXIT       : Press Ctrl+C or ESC key.")
    print("------------------------------------------------------------------\n")

    staged_text = ""

    try:
        while True:
            # Check keyboard first
            kb = check_keyboard_trigger()
            if kb == "CONFIRM" and staged_text:
                print(f"\n[KEYBOARD ENTER] Confirmed! Executing plot: \"{staged_text}\"")
                compiler.plot_phrase(staged_text)
                staged_text = ""
                print("[ACTION] Writing complete. Ready for next sentence.\n")
                continue
            elif kb == "CLEAR" and staged_text:
                staged_text = ""
                print("[KEYBOARD BACKSPACE] Staging preview buffer cleared.\n")
                continue
            elif kb == "NEW_LINE":
                compiler.newline()
                staged_text = ""
                print("[KEYBOARD 'N'] Carriage advanced to next line.\n")
                continue
            elif kb == "EXIT":
                print("[*] Exit key received.")
                break

            # Listen for speech with 3.5s timeout (loops so keyboard stays responsive)
            action, payload = voice.listen_and_classify(listen_timeout=3.5)

            if action in ["TIMEOUT", "EMPTY"]:
                continue

            elif action == "ERROR":
                print(f"[!] Audio error: {payload}. Resuming listen...")
                continue

            elif action == "NEW_LINE":
                compiler.newline()
                staged_text = ""
                print("[*] Carriage advanced to next ruled line.\n")

            elif action == "CLEAR":
                staged_text = ""
                print("[*] Staged preview buffer discarded. Pen remained idle.\n")

            elif action == "CONFIRM":
                if staged_text:
                    print(f"\n[ACTION] Confirmed! Executing physical plot: \"{staged_text}\"")
                    compiler.plot_phrase(staged_text)
                    staged_text = ""
                    print("[ACTION] Writing complete. Ready for next sentence.\n")
                else:
                    print("[!] Staging buffer empty. Dictate a sentence first.\n")

            elif action == "INLINE_CONFIRM":
                text_to_draw = payload
                print(f"\n[ACTION] Fast Confirmation! Executing physical plot: \"{text_to_draw}\"")
                compiler.plot_phrase(text_to_draw)
                staged_text = ""
                print("[ACTION] Writing complete. Ready for next sentence.\n")

            elif action == "TEXT":
                staged_text = payload
                print("\n=======================================================")
                print(f" STAGED TEXT: \"{staged_text}\"")
                print(" -> Say 'OK' / 'WRITE' (or press ENTER key) to draw,")
                print(" -> Say 'CLEAR' (or press BACKSPACE) to discard,")
                print(" -> Or speak again to replace.")
                print("=======================================================\n")

    except KeyboardInterrupt:
        print("\n[*] Operator interrupt detected (Ctrl+C). Parking carriage...")
    finally:
        streamer.close()
        print("[*] Voice Scribe shutdown complete.")


if __name__ == "__main__":
    run_orchestrator()
