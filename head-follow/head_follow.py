"""
Head-tracking boat controller (laptop webcam -> Arduino over serial).

Move your head left/right in front of the webcam and the boat turns to match.
Head centered = forward. No head seen = stop.

Keys (click the video window first so it receives your keypresses):
  T          toggle TRACKING <-> MANUAL mode
  W/A/S/D    drive (manual mode)
  Space / X  stop (any mode)
  1 / 2 / 3  power low / mid / high (any mode)
  Q / Esc    quit (sends stop first)

Install:  pip install pyserial opencv-python
Run:      python head_follow.py               (auto-detects the Arduino)
          python head_follow.py --port COM5   (explicit port)
          python head_follow.py --no-serial   (camera test only, no Arduino)
"""

import argparse
import time

import cv2
import serial
import serial.tools.list_ports

# ---------------- settings you can tune ----------------
BAUD = 9600            # must match Serial.begin(...) in the Arduino sketch
DEADZONE = 0.20        # middle band (fraction of half-width) that counts as "centered"
LOST_TIMEOUT = 0.5     # seconds without a face before sending stop
SMOOTHING = 0.4        # 0..1, higher = follows head faster but jitterier
CENTER_ACTION = "w"    # what to do when head is centered: "w" = forward, "x" = hold still
MIRROR = True          # mirror the webcam so it feels like a mirror

COMMAND_NAMES = {"w": "FORWARD", "a": "LEFT", "s": "BACK", "d": "RIGHT", "x": "STOP"}


# ---------------- serial helpers ----------------
def find_arduino_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    hints = ("arduino", "usbmodem", "usbserial", "ch340", "cp210", "ttyacm", "ttyusb")
    for p in ports:
        text = f"{p.device} {p.description} {p.manufacturer or ''}".lower()
        if any(h in text for h in hints):
            return p.device
    if len(ports) == 1:
        return ports[0].device
    print("Several serial ports found, pick one:")
    for i, p in enumerate(ports):
        print(f"  [{i}] {p.device} - {p.description}")
    return ports[int(input("Number: ").strip())].device


def open_serial(port_arg, no_serial):
    if no_serial:
        print("Running WITHOUT Arduino (camera test mode).")
        return None
    port = port_arg or find_arduino_port()
    if not port:
        print("No Arduino found - running in camera test mode.")
        return None
    try:
        ser = serial.Serial(port, BAUD, timeout=0)
    except serial.SerialException as e:
        print(f"Couldn't open {port}: {e}")
        print("Tip: close the Arduino IDE Serial Monitor. Running in camera test mode.")
        return None
    time.sleep(2)  # Arduino resets when the port opens
    ser.reset_input_buffer()
    print(f"Connected to {port} @ {BAUD} baud")
    return ser


class Link:
    """Sends commands, but only when they change (avoids flooding the port)."""

    def __init__(self, ser):
        self.ser = ser
        self.last_cmd = None

    def send(self, cmd, force=False):
        if cmd == self.last_cmd and not force:
            return
        self.last_cmd = cmd
        if self.ser:
            self.ser.write(cmd.encode())
        print(f"sent '{cmd}' {COMMAND_NAMES.get(cmd, '')}")

    def read_replies(self):
        if self.ser and self.ser.in_waiting:
            for line in self.ser.read(self.ser.in_waiting).decode(errors="ignore").splitlines():
                if line.strip():
                    print(f"  arduino: {line.strip()}")


# ---------------- face tracking ----------------
CASCADE_NAME = "haarcascade_frontalface_default.xml"


def load_face_detector():
    """Find OpenCV's face model file, even on installs where cv2.data is missing."""
    import glob
    import os

    candidates = []
    # 1) a copy sitting next to this script (easiest manual fix)
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), CASCADE_NAME))
    # 2) the normal location
    data = getattr(cv2, "data", None)
    if data is not None and hasattr(data, "haarcascades"):
        candidates.append(os.path.join(data.haarcascades, CASCADE_NAME))
    # 3) search inside the installed cv2 package
    cv2_dir = os.path.dirname(getattr(cv2, "__file__", "") or "")
    if cv2_dir:
        candidates += glob.glob(os.path.join(cv2_dir, "**", CASCADE_NAME), recursive=True)

    for path in candidates:
        if os.path.isfile(path):
            detector = cv2.CascadeClassifier(path)
            if not detector.empty():
                print(f"Face model: {path}")
                return detector

    print("Couldn't find OpenCV's face model file.")
    print(f"OpenCV loaded from: {getattr(cv2, '__file__', 'unknown')}")
    print("Fix: pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless")
    print("     pip install opencv-python")
    print(f"Or download {CASCADE_NAME} from github.com/opencv/opencv (data/haarcascades)")
    print("and put it in the same folder as this script.")
    return None


def detect_head(detector, frame):
    """Return (x, y, w, h) of the biggest face, or None."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)  # helps in uneven lighting
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    return max(faces, key=lambda f: f[2] * f[3])  # closest person = biggest box


def steer_from_offset(offset):
    """offset: -1 (far left) .. 0 (center) .. +1 (far right)"""
    if offset < -DEADZONE:
        return "a"
    if offset > DEADZONE:
        return "d"
    return CENTER_ACTION


def draw_overlay(frame, face, smooth_x, mode, cmd, power_label):
    h, w = frame.shape[:2]
    cx = w // 2
    dz = int(DEADZONE * w / 2)

    # center line + dead zone band
    cv2.line(frame, (cx, 0), (cx, h), (200, 200, 200), 1)
    cv2.line(frame, (cx - dz, 0), (cx - dz, h), (0, 200, 255), 1)
    cv2.line(frame, (cx + dz, 0), (cx + dz, h), (0, 200, 255), 1)

    if face is not None:
        x, y, fw, fh = face
        cv2.rectangle(frame, (x, y), (x + fw, y + fh), (0, 255, 0), 2)
    if smooth_x is not None:
        cv2.circle(frame, (int(smooth_x), h // 2), 8, (0, 0, 255), -1)

    color = (0, 255, 0) if mode == "TRACKING" else (255, 180, 0)
    cv2.putText(frame, f"MODE: {mode}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(frame, f"CMD: {COMMAND_NAMES.get(cmd, '-')}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"POWER: {power_label}", (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(frame, "T: mode  WASD: drive  Space: stop  1-3: power  Q: quit",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)


# ---------------- main loop ----------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="serial port, e.g. COM5 or /dev/cu.usbmodem14101")
    parser.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    parser.add_argument("--no-serial", action="store_true", help="test camera without Arduino")
    args = parser.parse_args()

    detector = load_face_detector()
    if detector is None:
        return
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("Couldn't open the camera. Try --camera 1, or check camera permissions.")
        return

    link = Link(open_serial(args.port, args.no_serial))
    link.send("x", force=True)  # start stopped

    mode = "TRACKING"
    power_label = "LOW (1)"
    smooth_x = None
    last_seen = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Camera frame failed.")
                break
            if MIRROR:
                frame = cv2.flip(frame, 1)

            w = frame.shape[1]
            face = detect_head(detector, frame)
            now = time.time()

            if face is not None:
                x, y, fw, fh = face
                head_x = x + fw / 2
                smooth_x = head_x if smooth_x is None else (
                    SMOOTHING * head_x + (1 - SMOOTHING) * smooth_x)
                last_seen = now

            if mode == "TRACKING":
                if now - last_seen > LOST_TIMEOUT:
                    smooth_x = None
                    link.send("x")  # lost the head -> stop
                elif smooth_x is not None:
                    offset = (smooth_x - w / 2) / (w / 2)
                    link.send(steer_from_offset(offset))

            link.read_replies()
            draw_overlay(frame, face, smooth_x, mode, link.last_cmd, power_label)
            cv2.imshow("Head Follow", frame)

            # ---- keyboard (through the OpenCV window) ----
            key = cv2.waitKey(1) & 0xFF
            if key == 255:          # no key pressed
                continue
            ch = chr(key).lower()

            if ch == "q" or key == 27:          # q or Esc
                break
            elif ch == "t":
                mode = "MANUAL" if mode == "TRACKING" else "TRACKING"
                print(f"--- {mode} mode ---")
                link.send("x", force=True)      # stop whenever switching modes
            elif ch in (" ", "x"):
                link.send("x", force=True)
            elif ch in ("1", "2", "3"):
                link.send(ch, force=True)
                power_label = {"1": "LOW (1)", "2": "MID (2)", "3": "HIGH (3)"}[ch]
            elif mode == "MANUAL" and ch in ("w", "a", "s", "d"):
                link.send(ch, force=True)
    finally:
        link.send("x", force=True)              # always stop on exit
        if link.ser:
            link.ser.close()
        cap.release()
        cv2.destroyAllWindows()
        print("Stopped and closed.")


if __name__ == "__main__":
    main()