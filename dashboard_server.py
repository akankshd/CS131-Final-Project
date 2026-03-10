#!/usr/bin/env python3
from flask import Flask, jsonify, request
from flask_cors import CORS
from google.cloud import bigquery
import os
import re

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.path.dirname(__file__), "service_account.json")

app = Flask(__name__)
CORS(app)

bq_client = bigquery.Client()
TABLE_ID = "krave-466820.attendance_dataset.attendance_events"


@app.route("/api/attendance")
def get_attendance():
    date_str = request.args.get("date")  # optional YYYY-MM-DD

    if date_str and re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        where = f"WHERE DATE(ts) = '{date_str}' AND name IS NOT NULL AND name != ''"
    else:
        where = "WHERE name IS NOT NULL AND name != ''"

    query = f"""
        SELECT ts, camera_id, event, name, sid, class, card_id
        FROM `{TABLE_ID}`
        {where}
        ORDER BY ts DESC
        LIMIT 500
    """
    rows = list(bq_client.query(query).result())
    data = []
    for row in rows:
        data.append({
            "ts":        row.ts.isoformat() if row.ts else None,
            "camera_id": row.camera_id,
            "event":     row.event,
            "name":      row.name,
            "sid":       row.sid,
            "class":     row["class"],
            "card_id":   row.card_id,
        })
    return jsonify(data)


if __name__ == "__main__":
    app.run(port=3001, debug=True)
