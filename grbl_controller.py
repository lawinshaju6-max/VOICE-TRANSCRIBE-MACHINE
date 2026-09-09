"""
Voice Scribe - GRBL Motion Controller Module
Manages robust USB serial communication with GRBL microcontroller,
implementing strict ping-pong flow control, LF line termination,
G54 offset reset, and comprehensive hardware logging.
"""

import sys
import time
import logging
from typing import Optional, List, Dict
import serial
import serial.tools.list_ports

# Configure persistent file logging
logging.basicConfig(
    filename="hardware.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("VoiceScribeHardware")


class GrblMotionStreamer:
    """Manages synchronous USB serial communication with the GRBL microcontroller."""

    def __init__(
        self,
        port: str = "COM8",
        baud_rate: int = 115200,
        auto_detect: bool = True,
        boot_delay: float = 2.5,
        cmd_pen_up: str = "M03 S90",
        cmd_pen_down: str = "M03 S0",
        servo_dwell: float = 0.35,
        rapid_feed: int = 1800,
        draw_feed: int = 800,
        timeout: float = 12.0,
    ):
        self.requested_port = port
        self.baud_rate = baud_rate
        self.auto_detect = auto_detect
        self.boot_delay = boot_delay
        self.cmd_pen_up = cmd_pen_up
        self.cmd_pen_down = cmd_pen_down
        self.servo_dwell = servo_dwell
        self.rapid_feed = rapid_feed
        self.draw_feed = draw_feed
        self.timeout = timeout

        self.port_name: Optional[str] = None
        self.ser: Optional[serial.Serial] = None
        self.is_connected = False

    @staticmethod
    def list_available_ports() -> List[Dict[str, str]]:
        """Returns a list of all detected serial ports and their descriptions."""
        return [
            {"device": p.device, "description": p.description, "hwid": p.hwid}
            for p in serial.tools.list_ports.comports()
        ]

    def detect_port(self) -> str:
        """Finds a plausible Arduino/GRBL port or falls back to the configured port."""
        ports = serial.tools.list_ports.comports()
        if not ports:
            logger.warning(f"No active COM ports detected. Defaulting to {self.requested_port}.")
            return self.requested_port

        # 1. Check if the requested port specifically exists
        for p in ports:
            if p.device.upper() == self.requested_port.upper():
                logger.info(f"Using requested port {p.device} ({p.description})")
                return p.device

        # 2. Check for known USB-serial adapters
        if self.auto_detect:
            for p in ports:
                desc = (p.description or "").lower()
                hwid = (p.hwid or "").lower()
                if any(sig in desc or sig in hwid for sig in ["arduino", "ch340", "cp210", "ftdi", "usb-serial"]):
                    logger.info(f"Auto-detected GRBL controller on {p.device} ({p.description})")
                    return p.device

            return ports[0].device

        return self.requested_port

    def connect(self):
        """Establishes connection to the GRBL controller with proper DTR settling."""
        self.port_name = self.detect_port()
        msg = f"Connecting to GRBL on {self.port_name} ({self.baud_rate} baud)..."
        print(f"[*] {msg}")
        logger.info(msg)

        try:
            self.ser = serial.Serial(self.port_name, self.baud_rate, timeout=self.timeout)
            self.is_connected = True
        except serial.SerialException as err:
            self.is_connected = False
            err_msg = f"Failed to open serial port {self.port_name}: {err}"
            print(f"[!] FATAL: {err_msg}")
            logger.error(err_msg)
            raise

        # Allow Arduino hardware DTR bootloader reset to conclude
        print(f"[*] Port open. Waiting {self.boot_delay:.1f}s for ATmega328P boot cycle...")
        logger.info(f"Waiting {self.boot_delay}s for DTR reset cycle...")
        time.sleep(self.boot_delay)

        # Flush startup banner lines emitted by GRBL
        banners = []
        while self.ser.in_waiting:
            line = self.ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                banners.append(line)
                print(f"    << {line}")
                logger.info(f"GRBL Banner: {line}")

        self.initialize_motion_state()

    def initialize_motion_state(self):
        """Initializes GRBL modal state: clears alarm, clears work offset, sets metric and absolute mode."""
        print("[*] Unlocking safety alarm ($X) and resetting coordinate systems...")
        logger.info("Initializing GRBL motion state...")

        self.send_blocking("$X")                   # Kill safety alarm
        self.send_blocking("G10 L2 P1 X0 Y0 Z0")   # Clear stray G54 work offset
        self.send_blocking("G21")                  # Metric units (mm)
        self.send_blocking("G90")                  # Absolute positioning
        self.send_blocking("G92 X0 Y0")            # Set current pen position as origin (0, 0)
        self.pen_up()
        print("[OK] Hardware motion state initialized (Work Origin set to current pen position).")
        logger.info("Hardware motion state initialized successfully.")

    def send_blocking(self, gcode_line: str) -> str:
        """
        Dispatches a single G-code line terminated strictly with LF (\\n).
        Blocks until GRBL emits an 'ok' or 'error' acknowledgment.
        CRLF (\\r\\n) is strictly avoided to prevent duplicate 'ok' responses.
        """
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("Serial port is not open.")

        clean_cmd = gcode_line.strip()
        if not clean_cmd:
            return "ok"

        # Strictly terminate with '\n' (GRBL interprets '\r' + '\n' as two commands)
        raw_cmd = clean_cmd.encode("utf-8") + b"\n"

        logger.debug(f"TX -> [{clean_cmd}]")
        self.ser.write(raw_cmd)

        start_time = time.time()
        while True:
            raw_response = self.ser.readline()
            if not raw_response:
                elapsed = time.time() - start_time
                err = f"GRBL timeout ({elapsed:.1f}s) awaiting response for: '{clean_cmd}'"
                logger.error(err)
                raise TimeoutError(err)

            response = raw_response.decode("utf-8", errors="ignore").strip()
            logger.debug(f"RX <- [{response}]")

            if response == "ok":
                return "ok"
            elif response.startswith("error:"):
                msg = f"GRBL REJECTED [{clean_cmd}]: {response}"
                print(f"[!] {msg}")
                logger.warning(msg)
                return response
            elif response:
                # Informational lines like status, parameters, etc.
                logger.info(f"GRBL MSG: {response}")

    def get_status(self) -> str:
        """Sends real-time query '?' and returns current machine status string."""
        if not self.ser or not self.ser.is_open:
            return "Not connected"
        self.ser.write(b"?")
        time.sleep(0.05)
        resp = ""
        while self.ser.in_waiting:
            resp += self.ser.readline().decode("utf-8", errors="ignore").strip() + " "
        return resp.strip()

    def pen_up(self):
        """Lifts pen clear of the writing surface and pauses for servo settling."""
        self.send_blocking(self.cmd_pen_up)
        self.send_blocking(f"G4 P{self.servo_dwell:.2f}")

    def pen_down(self):
        """Lowers pen onto paper and pauses for mechanical contact settling."""
        self.send_blocking(self.cmd_pen_down)
        self.send_blocking(f"G4 P{self.servo_dwell:.2f}")

    def rapid_move(self, x: float, y: float):
        """Executes a rapid positioning move (G0) with pen up."""
        self.send_blocking(f"G0 X{x:.2f} Y{y:.2f}")

    def linear_draw(self, x: float, y: float, feed: Optional[int] = None):
        """Executes a controlled drawing motion (G1) at specified feed rate with pen down."""
        f = feed or self.draw_feed
        self.send_blocking(f"G1 X{x:.2f} Y{y:.2f} F{f}")

    def close(self):
        """Safely lifts the pen, parks carriage, and closes port cleanly."""
        if self.ser and self.ser.is_open:
            try:
                self.pen_up()
                self.rapid_move(0.0, 0.0)
            except Exception as e:
                logger.warning(f"Error during shutdown park: {e}")
            finally:
                self.ser.close()
                self.is_connected = False
                logger.info("Serial link closed.")
                print("[*] Serial link closed cleanly.")
