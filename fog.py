#!/usr/bin/env python3
import zmq
import json
import csv
import re
import cv2
import numpy as np
from datetime import datetime
from typing import Optional
from google.cloud import bigquery
import os
import easyocr

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.path.dirname(__file__), "service_account.json")

bq_client = bigquery.Client()

TABLE_ID = "krave-466820.attendance_dataset.attendance_events"

BIND_PORT = 5555
TOPIC = "attendance"
CSV_FILE = "attendance_events.csv"
CSV_FIELDS = ["ts", "camera_id", "event", "track_id", "card_id", "name", "sid", "class", "source"]

print("[FOG] Loading EasyOCR model (first run downloads ~100 MB)…")
reader = easyocr.Reader(["en"], gpu=False)
print("[FOG] EasyOCR ready.")

checked_in = set()  # type: set


def extract_name(image_bytes: bytes) -> Optional[str]:
    if not image_bytes:
        return None

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    results = reader.readtext(img)
    print(f"[FOG] OCR results: {[(r[1], round(r[2], 2)) for r in results]}")

    for result in results:
        text = result[1].strip()
        confidence = result[2]

        if confidence < 0.5:
            continue

        if re.match(r"^[A-Z][A-Z\s.\-]{4,40}$", text) and len(text.split()) >= 2:
            print(f"[FOG] Name candidate: {text!r} (conf={confidence:.2f})")
            return text

    print("[FOG] No name found in OCR output.")
    return None


def write_csv(row: dict):
    try:
        with open(CSV_FILE, "x", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()
    except FileExistsError:
        pass
    with open(CSV_FILE, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(row)


def insert_bigquery(row: dict):
    errors = bq_client.insert_rows_json(TABLE_ID, [row])
    if errors:
        print("[FOG] BigQuery insert errors:", errors)


def main():
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.bind(f"tcp://*:{BIND_PORT}")
    sub.setsockopt_string(zmq.SUBSCRIBE, TOPIC)

    print(f"[FOG] Listening on tcp://*:{BIND_PORT} topic='{TOPIC}'")

    while True:
        parts = sub.recv_multipart()
        event = json.loads(parts[1].decode())
        image_bytes = parts[2] if len(parts) > 2 else b""
        track_id = event.get("track_id", -1)

        card_id = event.get("card_id")
        source  = event.get("source", "ocr")
        name    = event.get("name") or ""
        sid     = event.get("sid")  or ""
        course  = event.get("class") or ""

        if source == "qr":
            if not card_id:
                print("[FOG] QR event missing card_id, skipping.")
                continue

        elif source == "barcode":
            name = extract_name(image_bytes) or ""

        else:
            name = extract_name(image_bytes) or ""
            if not name:
                print("[FOG] OCR found nothing, skipping event.")
                continue
            card_id = name

        if not card_id:
            print("[FOG] No identifier resolved, skipping.")
            continue

        if card_id not in checked_in:
            event_type = "checkin"
            checked_in.add(card_id)
        else:
            event_type = "checkout"
            checked_in.remove(card_id)

        row = {
            "ts":        event["ts"],
            "camera_id": event["camera_id"],
            "event":     event_type,
            "track_id":  track_id,
            "card_id":   card_id,
            "name":      name,
            "sid":       sid,
            "class":     course,
            "source":    source,
        }

        print(f"[FOG] {event_type.upper()} — name={name!r}  sid={sid!r}  class={course!r}  source={source}")
        print(f"[FOG] Currently checked in: {checked_in}")
        write_csv(row)
        insert_bigquery(row)


if __name__ == "__main__":
    main()
