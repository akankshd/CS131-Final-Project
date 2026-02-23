#!/usr/bin/env python3
import zmq
import json
import csv
from datetime import datetime
from google.cloud import bigquery
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service_account.json"

bq_client = bigquery.Client()

TABLE_ID = "krave-466820.attendance_dataset.attendance_events"

BIND_PORT = 5555
TOPIC = "attendance"
CSV_FILE = "attendance_events.csv"

def main():
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.bind(f"tcp://*:{BIND_PORT}")
    sub.setsockopt_string(zmq.SUBSCRIBE, TOPIC)

    print(f"[FOG] Listening on tcp://*:{BIND_PORT} topic='{TOPIC}'")
    print(f"[FOG] Writing events to {CSV_FILE}")

    try:
        with open(CSV_FILE, "x", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "ts",
                    "camera_id",
                    "event",
                    "track_id",
                    "total_entries_total",
                ],
            )
            writer.writeheader()
    except FileExistsError:
        pass

    while True:
        msg = sub.recv_string()
        _, payload = msg.split(" ", 1)
        event = json.loads(payload)

        print("[FOG] got:", event)

        with open(CSV_FILE, "a", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "ts",
                    "camera_id",
                    "event",
                    "track_id",
                    "total_entries_total",
                ],
            )
            writer.writerow(event)

        # Cloud functionality: streaming event to Google BigQuery
        errors = bq_client.insert_rows_json(TABLE_ID, [event])
        if errors:
            print("[FOG] BigQuery insert errors:", errors)

if __name__ == "__main__":
    main()
