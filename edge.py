#!/usr/bin/env python3
import jetson.inference
import jetson.utils
import zmq
import json
import cv2
import numpy as np
import time
from datetime import datetime
from typing import Optional
from pyzbar import pyzbar

FOG_IP = "10.13.202.140"
PORT = 5555
TOPIC = "attendance"

SCAN_COOLDOWN = 3.0

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


def scan_qr(bgr: np.ndarray) -> Optional[dict]:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    for code in pyzbar.decode(gray):
        raw = code.data.decode("utf-8").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("sid"):
                print(f"[EDGE] QR decoded: {payload}")
                return {
                    "card_id": payload["sid"],
                    "name":    payload.get("name", ""),
                    "sid":     payload["sid"],
                    "class":   payload.get("class", ""),
                    "source":  "qr",
                }
        except (json.JSONDecodeError, ValueError):
            pass
    return None


while display.IsStreaming():
    img = camera.Capture()

    detections = net.Detect(img, overlay="none")

    for det in detections:
        if net.GetClassDesc(det.ClassID) != "person":
            continue

        track_id = det.TrackID
        if track_id < 0:
            continue

        now = time.time()
        if now - last_scan_time.get(track_id, 0) < SCAN_COOLDOWN:
            continue

        try:
            bgr = frame_to_bgr(jetson.utils.cudaToNumpy(img))
        except Exception as e:
            print(f"[EDGE] frame error: {e}")
            continue

        decoded = scan_qr(bgr)
        if decoded:
            last_scan_time[track_id] = now
            event = {
                "ts":        datetime.utcnow().isoformat() + "Z",
                "camera_id": "nano-door-1",
                "track_id":  int(track_id),
                **decoded,
            }
            pub.send_multipart([
                TOPIC.encode(),
                json.dumps(event).encode(),
                b"",
            ])
            print(f"[EDGE] sent: {event}")

    display.Render(img)
    display.SetStatus("Hold QR code toward camera to check in / check out")
