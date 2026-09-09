#!/usr/bin/env python3
"""
Voice Scribe - Interactive Hardware Diagnostic & Calibration Suite
Tests COM communication, servo angles, stepper motors, calibration square,
and real-time machine status with full file logging in hardware.log.
"""

import sys
import time
from grbl_controller import GrblMotionStreamer
from vector_compiler import VectorLayoutCompiler
from voice_scribe_engine import load_config


def print_menu():
    print("\n------------------------------------------------------------------")
    print("           VOICE SCRIBE HARDWARE DIAGNOSTIC MENU                  ")
    print("------------------------------------------------------------------")
    print(" [1] Test Pen Lift / Lower (Toggle Servo S90 <-> S0)")
    print(" [2] Jog X-Axis (+10 mm / -10 mm)")
    print(" [3] Jog Y-Axis (+10 mm / -10 mm)")
    print(" [4] Draw 20mm x 20mm Calibration Square (Verifies Steps/mm)")
    print(" [5] Plot Test Phrase ('TEST 123')")
    print(" [6] Read All GRBL Settings ($$)")
    print(" [7] Reset Work Origin to Current Position (G92 X0 Y0)")
    print(" [8] Query Real-Time Machine Status (?)")
    print(" [0] Park Carriage & Exit")
    print("------------------------------------------------------------------")


def run_diagnostics():
    cfg = load_config()
    s_cfg = cfg["serial"]
    m_cfg = cfg["motion"]
    g_cfg = cfg["geometry"]

    print("==================================================================")
    print("           VOICE SCRIBE HARDWARE TEST & CALIBRATION               ")
    print("==================================================================")

    # 1. Scan and report serial ports
    print("[*] Scanning system for available COM ports...")
    ports = GrblMotionStreamer.list_available_ports()
    if not ports:
        print("[!] No active COM ports found. Connect Arduino USB cable first.")
    else:
        for p in ports:
            print(f"    - {p['device']}: {p['description']} [{p['hwid']}]")

    print(f"\n[*] Connecting to port: {s_cfg.get('port', 'COM8')} (Auto-detect: {s_cfg.get('auto_detect', True)})")

    try:
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
        streamer.connect()
    except Exception as e:
        print(f"\n[!] Connection failed: {e}")
        print("[!] Check hardware.log for detailed failure traces.")
        return

    compiler = VectorLayoutCompiler(
        streamer=streamer,
        page_width=g_cfg.get("page_width", 170.0),
        page_height=g_cfg.get("page_height", 290.0),
        margin_left=g_cfg.get("margin_left", 15.0),
        start_y=g_cfg.get("start_y", 270.0),
        line_spacing=g_cfg.get("line_spacing", 9.5),
        font_scale=g_cfg.get("font_scale", 0.28),
    )

    pen_is_up = True
    curr_x, curr_y = 0.0, 0.0

    try:
        while True:
            print_menu()
            choice = input("Select an option [0-8]: ").strip()

            if choice == "1":
                if pen_is_up:
                    print("[*] Lowering pen onto paper (S0)...")
                    streamer.pen_down()
                    pen_is_up = False
                else:
                    print("[*] Raising pen clear of paper (S90)...")
                    streamer.pen_up()
                    pen_is_up = True
                print(f"[OK] Servo state: {'PEN UP (S90)' if pen_is_up else 'PEN DOWN (S0)'}")

            elif choice == "2":
                direction = input("Enter X delta in mm (+10 or -10) [default: +10]: ").strip()
                delta = -10.0 if direction.startswith("-") else 10.0
                curr_x += delta
                print(f"[*] Jogging X to {curr_x:.2f} mm...")
                streamer.rapid_move(curr_x, curr_y)
                print(f"[OK] Current position: X={curr_x:.2f}, Y={curr_y:.2f}")

            elif choice == "3":
                direction = input("Enter Y delta in mm (+10 or -10) [default: +10]: ").strip()
                delta = -10.0 if direction.startswith("-") else 10.0
                curr_y += delta
                print(f"[*] Jogging Y to {curr_y:.2f} mm...")
                streamer.rapid_move(curr_x, curr_y)
                print(f"[OK] Current position: X={curr_x:.2f}, Y={curr_y:.2f}")

            elif choice == "4":
                print(f"[*] Drawing 20mm x 20mm calibration square starting at ({curr_x:.2f}, {curr_y:.2f})...")
                # Side 1: Bottom edge (left -> right)
                streamer.pen_up()
                streamer.rapid_move(curr_x, curr_y)
                streamer.pen_down()
                streamer.linear_draw(curr_x + 20.0, curr_y)
                # Side 2: Right edge (bottom -> top)
                streamer.linear_draw(curr_x + 20.0, curr_y + 20.0)
                # Side 3: Top edge (right -> left)
                streamer.linear_draw(curr_x, curr_y + 20.0)
                # Side 4: Left edge (top -> bottom to close square)
                streamer.linear_draw(curr_x, curr_y)
                streamer.pen_up()
                print("[OK] Square complete (all 4 sides drawn).")
                print("    -> Measure the physical drawn square with a ruler.")
                print("    -> If each side is exactly 20.0 mm, your steps/mm setting is perfect!")

            elif choice == "5":
                loc_choice = input("Plot at [C]urrent position or [H]ome margin (15, 270)? [default: C]: ").strip().upper()
                phrase = "TEST 123"
                if loc_choice == "H":
                    print(f"[*] Resetting to Home and plotting '{phrase}'...")
                    compiler.reset_origin()
                    compiler.plot_phrase(phrase)
                    curr_x = compiler.cursor_x
                    curr_y = compiler.cursor_y
                else:
                    print(f"[*] Plotting '{phrase}' starting at current position ({curr_x:.2f}, {curr_y:.2f})...")
                    compiler.cursor_x = curr_x
                    compiler.cursor_y = curr_y
                    compiler.plot_phrase(phrase)
                    curr_x = compiler.cursor_x
                    curr_y = compiler.cursor_y
                print("[OK] Plot complete.")

            elif choice == "6":
                print("[*] Querying all GRBL settings ($$)...")
                # Send $$ strictly with \n
                streamer.ser.write(b"$$\n")
                time.sleep(0.4)
                while streamer.ser.in_waiting:
                    line = streamer.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        print(f"    {line}")

            elif choice == "7":
                print("[*] Setting current position as Work Origin (G92 X0 Y0)...")
                streamer.send_blocking("G92 X0 Y0")
                curr_x, curr_y = 0.0, 0.0
                print("[OK] Origin set: X=0.00, Y=0.00")

            elif choice == "8":
                status = streamer.get_status()
                print(f"[*] Machine Status: {status}")

            elif choice == "0":
                print("[*] Parking carriage and exiting...")
                break

            else:
                print("[!] Invalid option. Enter a number 0 through 8.")

    except KeyboardInterrupt:
        print("\n[*] Interrupted by user.")
    finally:
        streamer.close()


if __name__ == "__main__":
    run_diagnostics()
