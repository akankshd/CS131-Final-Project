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

camera = jetson.utils.videoSource("v4l2:///dev/video0")
display = jetson.utils.videoOutput("display://0")

ctx = zmq.Context()
pub = ctx.socket(zmq.PUB)
pub.connect(f"tcp://{FOG_IP}:{PORT}")

last_sent_time = {}
last_log_time = 0


def frame_to_bgr(img_np):
    if img_np.shape[2] == 4:
        return cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)


def scan_qr(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    codes = pyzbar.decode(gray)
    for code in codes:
        raw = code.data.decode("utf-8").strip()
        if not raw:
            continue
        print(f"[EDGE] decoded: type={code.type} data={raw!r}")
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("sid"):
                return {
                    "card_id": payload["sid"],
                    "name":    payload.get("name", ""),
                    "sid":     payload["sid"],
                    "class":   payload.get("class", ""),
                }
        except (json.JSONDecodeError, ValueError):
            pass
    return None


while display.IsStreaming():
    img = camera.Capture()
    detections = net.Detect(img, overlay="none")

    now = time.time()
    bgr = frame_to_bgr(jetson.utils.cudaToNumpy(img))
    decoded = scan_qr(bgr)

    if decoded:
        card_id = decoded["card_id"]
        if now - last_sent_time.get(card_id, 0) > SCAN_COOLDOWN:
            last_sent_time[card_id] = now
            event = {
                "ts":        datetime.utcnow().isoformat() + "Z",
                "camera_id": "nano-door-1",
                "track_id":  0,
                "card_id":   decoded["card_id"],
                "name":      decoded["name"],
                "sid":       decoded["sid"],
                "class":     decoded["class"],
                "source":    "qr",
            }
            pub.send_multipart([
                TOPIC.encode(),
                json.dumps(event).encode(),
                b"",
            ])
            print(f"[EDGE] SENT: name={decoded['name']}  sid={decoded['sid']}")
    elif now - last_log_time > 5:
        last_log_time = now
        print(f"[EDGE] scanning... persons={len(detections)}  no QR found")

    display.Render(img)
    display.SetStatus("Hold QR code toward camera")
