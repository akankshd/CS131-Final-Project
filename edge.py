#!/usr/bin/env python3
import jetson.inference
import jetson.utils
import zmq
import json
from datetime import datetime

FOG_IP = "10.13.202.140"
PORT = 5555
TOPIC = "attendance"

LINE_P1 = (640, 0)
LINE_P2 = (640, 720)

ENTRY_DIRECTION = "right"

net = jetson.inference.detectNet("ssd-mobilenet-v2", threshold=0.5)
net.SetTrackingEnabled(True)
net.SetTrackingParams(minFrames=3, dropFrames=15, overlapThreshold=0.5)

camera = jetson.utils.videoSource("v4l2:///dev/video0")
display = jetson.utils.videoOutput("display://0")

ctx = zmq.Context()
pub = ctx.socket(zmq.PUB)
pub.connect(f"tcp://{FOG_IP}:{PORT}")

track_positions = {}
counted_ids = set()
total_entries = 0

def crossed_line(prev_x, curr_x):
    if ENTRY_DIRECTION == "right":
        return prev_x < LINE_P1[0] and curr_x >= LINE_P1[0]
    elif ENTRY_DIRECTION == "left":
        return prev_x > LINE_P1[0] and curr_x <= LINE_P1[0]
    return False

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

        if track_id not in track_positions:
            track_positions[track_id] = center_x
            continue

        prev_x = track_positions[track_id]

        if crossed_line(prev_x, center_x) and track_id not in counted_ids:
            total_entries += 1
            counted_ids.add(track_id)

            event = {
                "ts": datetime.utcnow().isoformat() + "Z",
                "camera_id": "nano-door-1",
                "event": "entry",
                "track_id": int(track_id),
                "total_entries_total": int(total_entries)
            }

            pub.send_string(f"{TOPIC} {json.dumps(event)}")

        track_positions[track_id] = center_x

    jetson.utils.cudaDrawLine(img, LINE_P1, LINE_P2, (255, 0, 0, 255))
    display.Render(img)
    display.SetStatus(f"Total Entries: {total_entries}")
