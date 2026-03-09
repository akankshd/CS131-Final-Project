#!/usr/bin/env python3
import jetson.inference
import jetson.utils
import zmq
import json
import cv2
import numpy as np
import time
from datetime import datetime
from pyzbar import pyzbar

FOG_IP = "10.13.202.140"
PORT = 5555
TOPIC = "attendance"

SCAN_ZONE_X_MIN = 300
SCAN_ZONE_X_MAX = 600

SCAN_COOLDOWN = 2.0

net = jetson.inference.detectNet("ssd-mobilenet-v2", threshold=0.5)
net.SetTrackingEnabled(True)
net.SetTrackingParams(minFrames=3, dropFrames=15, overlapThreshold=0.5)

camera = jetson.utils.videoSource("v4l2:///dev/video0")
display = jetson.utils.videoOutput("display://0")

ctx = zmq.Context()
pub = ctx.socket(zmq.PUB)
pub.connect(f"tcp://{FOG_IP}:{PORT}")

last_scan_time = {}


def frame_to_bgr(img_np: np.ndarray) -> np.ndarray:
    if img_np.shape[2] == 4:
        return cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)


def scan_code(bgr: np.ndarray) -> dict | None:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    codes = pyzbar.decode(gray)
    for code in codes:
        raw = code.data.decode("utf-8").strip()
        if not raw:
            continue
        print(f"[EDGE] decoded: type={code.type}  raw={raw!r}")

        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                return {
                    "card_id": payload.get("sid") or raw,
                    "name":    payload.get("name"),
                    "sid":     payload.get("sid"),
                    "class":   payload.get("class"),
                    "source":  "qr",
                }
        except (json.JSONDecodeError, ValueError):
            pass

        return {
            "card_id": raw,
            "name":    None,
            "sid":     None,
            "class":   None,
            "source":  "barcode",
        }
    return None


def encode_jpeg(bgr: np.ndarray) -> bytes:
    _, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


while display.IsStreaming():
    img = camera.Capture()
    detections = net.Detect(img)

    for det in detections:
        if net.GetClassDesc(det.ClassID) != "person":
            continue

        track_id = det.TrackID
        if track_id < 0:
            continue

        center_x = int((det.Left + det.Right) / 2)
        now = time.time()

        in_scan_zone = SCAN_ZONE_X_MIN <= center_x <= SCAN_ZONE_X_MAX
        time_since_last = now - last_scan_time.get(track_id, 0)

        if in_scan_zone and time_since_last > SCAN_COOLDOWN:
            last_scan_time[track_id] = now

            try:
                img_np = jetson.utils.cudaToNumpy(img)
                bgr = frame_to_bgr(img_np)
            except Exception as e:
                print(f"[EDGE] frame convert error: {e}")
                continue

            decoded = scan_code(bgr)

            if decoded:
                event = {
                    "ts":        datetime.utcnow().isoformat() + "Z",
                    "camera_id": "nano-door-1",
                    "track_id":  int(track_id),
                    **decoded,
                }
                img_payload = b"" if decoded["source"] == "qr" else encode_jpeg(bgr)
                pub.send_multipart([
                    TOPIC.encode(),
                    json.dumps(event).encode(),
                    img_payload,
                ])
                print(f"[EDGE] {decoded['source']} event sent: {decoded}")
            else:
                event = {
                    "ts":        datetime.utcnow().isoformat() + "Z",
                    "camera_id": "nano-door-1",
                    "track_id":  int(track_id),
                    "card_id":   None,
                    "name":      None,
                    "sid":       None,
                    "class":     None,
                    "source":    "ocr",
                }
                pub.send_multipart([
                    TOPIC.encode(),
                    json.dumps(event).encode(),
                    encode_jpeg(bgr),
                ])
                print(f"[EDGE] no code found, sending frame to fog for OCR")

    jetson.utils.cudaDrawLine(img, (SCAN_ZONE_X_MIN, 0), (SCAN_ZONE_X_MIN, 720), (0, 255, 0, 255))
    jetson.utils.cudaDrawLine(img, (SCAN_ZONE_X_MAX, 0), (SCAN_ZONE_X_MAX, 720), (0, 255, 0, 255))
    display.Render(img)
    display.SetStatus("Hold ID card toward camera to check in / check out")
