# Voice Scribe: Voice-Operated Autonomous Physical Writing Machine

Voice Scribe is an assistive mechatronic platform designed to translate spoken natural language directly into authentic, physical pen-on-paper handwriting on standard paper stationery (e.g., standard A4 examination sheets).

---

## Features
- **Two-Stage Dictation Pipeline**: Captures spoken answers into a staging preview buffer before writing. Physical ink is deposited only upon verbal confirmation (`"OK"` / `"WRITE"`) or pressing Enter.
- **Fast In-Line & Prefix Dictation**: Supports speaking in one breath (e.g., `"Write Hydrogen"` or `"Hydrogen OK"`).
- **Single-Stroke Hershey Vector Engine**: Uses authentic single-stroke centerline Hershey fonts (no hollow double-line TrueType fonts).
- **Automatic Word-Wrapping & Margins**: Calculates kerning and wraps sentences within standard A4 paper boundaries.
- **Strict Flow-Controlled Motion Streaming**: Communicates with Arduino running GRBL at 115200 baud via strict synchronous ping-pong flow control (`send` -> wait for `ok` -> `next`).
- **Servo Dwell Protection**: Injects mechanical settling pauses (`G4 P0.35`) after every pen-lift and pen-drop command to prevent diagonal ink drag.

---

## Hardware Architecture
- **Kinematics**: 2-Axis Cartesian Gantry ($X$ and $Y$) on GT2 timing belts (2mm pitch, 20T/16T pulleys).
- **Controller**: Arduino Uno R3 (ATmega328P) running GRBL 0.9i.
- **Expansion Shield**: Arduino CNC Shield V3.00.
- **Stepper Drivers**: 2x A4988 motor drivers (configured for 1/16 microstepping, MS1-MS3 jumpered).
- **Pen Mechanism**: Vertical spring-loaded sleeve with TowerPro SG90 micro-servo wired to Pin 11 (Z+ PWM / SpnEn).
- **Power**: 12V DC (3A–5A) power brick into CNC Shield terminals.

---

## Project Structure
```
VOICE TRANSCRIBE MACHINE/
├── config.json                     # Hardware, geometry & voice configuration
├── requirements.txt                # Python package dependencies
├── grbl_controller.py              # Hardware communication & ping-pong motion streamer
├── hershey_fonts.py                # Single-stroke Hershey vector glyph database
├── vector_compiler.py              # Kerning, word-wrapping, and trajectory compiler
├── voice_engine.py                 # Microphone capture, noise calibration, and token classification
├── voice_scribe_engine.py          # Main production orchestrator loop
├── test_hardware.py                # Standalone diagnostic tool for COM port, steppers, and servo
├── test_audio.py                   # Standalone diagnostic tool for microphone capture
└── test_unit.py                    # Automated test suite
```

---

## Getting Started

### 1. Installation
```powershell
py -3 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Hardware Diagnostics
```powershell
.\venv\Scripts\python test_hardware.py
```
- Option `[1]`: Toggle pen servo up/down (`M03 S90` / `M03 S0`).
- Option `[2]/[3]`: Jog X / Y axes.
- Option `[4]`: Draw 20mm $\times$ 20mm calibration square.
- Option `[5]`: Plot test phrase (`TEST 123`).
- Option `[6]`: Read GRBL configuration (`$$`).

### 3. Running Voice Scribe
```powershell
.\venv\Scripts\python voice_scribe_engine.py
```
1. Put on your microphone headset.
2. Speak your answer $\rightarrow$ text stages in the console.
3. Say **`"OK"`** or **`"WRITE"`** (or tap **ENTER**) to write in physical ink!
4. Say **`"NEW LINE"`** to feed down one ruled line.
5. Say **`"CLEAR"`** to discard the staged text.

---

## License
MIT License
