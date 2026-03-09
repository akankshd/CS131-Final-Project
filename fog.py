#!/usr/bin/env python3
import zmq
import json
import csv
import os
from google.cloud import bigquery

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.path.dirname(__file__), "service_account.json")

bq_client = bigquery.Client()

TABLE_ID = "krave-466820.attendance_dataset.attendance_events"

BIND_PORT = 5555
TOPIC = "attendance"
CSV_FILE = "attendance_events.csv"
CSV_FIELDS = ["ts", "camera_id", "event", "track_id", "card_id", "name", "sid", "class"]

checked_in = set()


def write_csv(row):
    try:
        with open(CSV_FILE, "x", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()
    except FileExistsError:
        pass
    with open(CSV_FILE, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(row)


def insert_bigquery(row):
    errors = bq_client.insert_rows_json(TABLE_ID, [row])
    if errors:
        print("[FOG] BigQuery errors:", errors)


def main():
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.bind(f"tcp://*:{BIND_PORT}")
    sub.setsockopt_string(zmq.SUBSCRIBE, TOPIC)

    print(f"[FOG] Listening on tcp://*:{BIND_PORT}")

    while True:
        parts = sub.recv_multipart()
        event = json.loads(parts[1].decode())

        card_id = event.get("card_id", "")
        if not card_id:
            print("[FOG] No card_id, skipping.")
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
            "track_id":  event.get("track_id", -1),
            "card_id":   card_id,
            "name":      event.get("name", ""),
            "sid":       event.get("sid", ""),
            "class":     event.get("class", ""),
        }

        print(f"[FOG] {event_type.upper()} — name={row['name']!r}  sid={row['sid']!r}  class={row['class']!r}")
        print(f"[FOG] checked in: {checked_in}")
        write_csv(row)
        insert_bigquery(row)


if __name__ == "__main__":
    main()
