import { useState, useEffect, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";

const BASE_API = "http://localhost:3001/api/attendance";
const REFRESH_MS = 8000;

function toDateStr(date) {
  return date.toISOString().slice(0, 10);
}
function todayStr() {
  return toDateStr(new Date());
}
function addDays(dateStr, n) {
  const d = new Date(dateStr + "T12:00:00");
  d.setDate(d.getDate() + n);
  return toDateStr(d);
}
function fmtDate(dateStr) {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  });
}
function fmt(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return d.toLocaleString("en-US", {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}
function fmtDuration(mins) {
  if (mins == null) return "—";
  if (mins < 60) return `${Math.round(mins)}m`;
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  return `${h}h ${m}m`;
}

function getCheckedIn(events) {
  const state = {};
  const byTime = [...events].sort((a, b) => new Date(a.ts) - new Date(b.ts));
  for (const e of byTime) {
    if (e.event === "checkin") state[e.sid] = e;
    else if (e.event === "checkout") delete state[e.sid];
  }
  return Object.values(state);
}

function getAvgDuration(events) {
  const byTime = [...events].sort((a, b) => new Date(a.ts) - new Date(b.ts));
  const lastCheckin = {};
  const durations = [];
  for (const e of byTime) {
    if (e.event === "checkin") {
      lastCheckin[e.sid] = new Date(e.ts);
    } else if (e.event === "checkout" && lastCheckin[e.sid]) {
      const dur = (new Date(e.ts) - lastCheckin[e.sid]) / 60000;
      if (dur > 0 && dur < 600) durations.push(dur);
      delete lastCheckin[e.sid];
    }
  }
  if (!durations.length) return null;
  return durations.reduce((a, b) => a + b, 0) / durations.length;
}

function getHourlyData(events) {
  const counts = Array.from({ length: 24 }, (_, i) => ({
    hour: i, checkins: 0, checkouts: 0,
  }));
  for (const e of events) {
    if (!e.ts) continue;
    const h = new Date(e.ts).getHours();
    if (e.event === "checkin") counts[h].checkins++;
    else counts[h].checkouts++;
  }
  let first = counts.findIndex(c => c.checkins + c.checkouts > 0);
  let last = counts.length - 1;
  while (last > first && counts[last].checkins + counts[last].checkouts === 0) last--;
  if (first === -1) return counts.slice(8, 22);
  return counts.slice(Math.max(0, first - 1), Math.min(24, last + 2));
}

function getSectionData(events) {
  const map = {};
  for (const e of events) {
    if (e.event !== "checkin") continue;
    const sec = e.class || "Unknown";
    map[sec] = (map[sec] || 0) + 1;
  }
  return Object.entries(map)
    .map(([name, count]) => ({ name: name.replace("CS131 — ", "§"), count }))
    .sort((a, b) => b.count - a.count);
}

function getTopVisitors(events) {
  const map = {};
  const byTime = [...events].sort((a, b) => new Date(a.ts) - new Date(b.ts));

  // Build per-sid entry with visit count
  for (const e of byTime) {
    if (e.event !== "checkin" || !e.name) continue;
    if (!map[e.sid]) map[e.sid] = { name: e.name, sid: e.sid, class: e.class, count: 0, totalMins: null };
    map[e.sid].count++;
  }

  // Compute total duration per visitor from checkin/checkout pairs
  const lastCheckin = {};
  for (const e of byTime) {
    if (e.event === "checkin") {
      lastCheckin[e.sid] = new Date(e.ts);
    } else if (e.event === "checkout" && lastCheckin[e.sid]) {
      const dur = (new Date(e.ts) - lastCheckin[e.sid]) / 60000;
      if (dur > 0 && dur < 600 && map[e.sid]) {
        map[e.sid].totalMins = (map[e.sid].totalMins ?? 0) + dur;
      }
      delete lastCheckin[e.sid];
    }
  }

  return Object.values(map).sort((a, b) => b.count - a.count).slice(0, 5);
}

const SECTION_COLORS = ["#003DA5", "#2563eb", "#60a5fa", "#34d399", "#a78bfa"];

export default function Dashboard({ onBack }) {
  const [selectedDate, setSelectedDate] = useState(todayStr());
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);

  const isToday = selectedDate === todayStr();

  const fetchData = useCallback(async (date) => {
    try {
      const res = await fetch(`${BASE_API}?date=${date}`);
      if (!res.ok) throw new Error("Server error " + res.status);
      const data = await res.json();
      setEvents(data);
      setLastRefresh(new Date());
      setError("");
    } catch {
      setError("Could not reach dashboard server. Is dashboard_server.py running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setEvents([]);
    fetchData(selectedDate);
    if (isToday) {
      const id = setInterval(() => fetchData(selectedDate), REFRESH_MS);
      return () => clearInterval(id);
    }
  }, [selectedDate, fetchData, isToday]);

  function changeDate(d) {
    if (d > todayStr()) return;
    setSelectedDate(d);
  }

  const checkedIn    = getCheckedIn(events);
  const checkins     = events.filter(e => e.event === "checkin");
  const uniqueCount  = new Set(events.map(e => e.sid).filter(Boolean)).size;
  const avgDuration  = getAvgDuration(events);
  const hourlyData   = getHourlyData(events);
  const sectionData  = getSectionData(events);
  const topVisitors  = getTopVisitors(events);
  const sortedEvents = [...events].sort((a, b) => new Date(b.ts) - new Date(a.ts));

  return (
    <div className="dash-page">

      {/* ── Header ── */}
      <div className="dash-header">
        <div className="dash-brand">
          <span className="logo-dot" />
          <span className="logo-text">UC Riverside · Lab Attendance</span>
          <button className="tab-switch" style={{ marginLeft: 16 }} onClick={onBack}>
            ← Generate QR
          </button>
        </div>

        <div className="dash-date-nav">
          <button className="btn-nav" onClick={() => changeDate(addDays(selectedDate, -1))}>‹</button>
          <div className="date-display">
            <span className="date-label">{fmtDate(selectedDate)}</span>
            {isToday && <span className="badge-live">LIVE</span>}
          </div>
          <button
            className="btn-nav"
            onClick={() => changeDate(addDays(selectedDate, 1))}
            disabled={isToday}
          >›</button>
          {!isToday && (
            <button className="btn-today" onClick={() => changeDate(todayStr())}>Today</button>
          )}
          <input
            type="date"
            className="date-input"
            value={selectedDate}
            max={todayStr()}
            onChange={e => changeDate(e.target.value)}
          />
        </div>

        <div className="dash-refresh">
          {lastRefresh && (
            <span className="refresh-time">Updated {lastRefresh.toLocaleTimeString()}</span>
          )}
          <button className="btn-refresh" onClick={() => fetchData(selectedDate)}>Refresh</button>
        </div>
      </div>

      {error && <div className="dash-error">{error}</div>}

      {/* ── Stats ── */}
      <div className="dash-stats">
        {isToday && (
          <div className="stat-card">
            <div className="stat-value">{checkedIn.length}</div>
            <div className="stat-label">Currently In Lab</div>
          </div>
        )}
        <div className="stat-card">
          <div className="stat-value">{loading ? "…" : checkins.length}</div>
          <div className="stat-label">Check-ins</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{loading ? "…" : uniqueCount || "—"}</div>
          <div className="stat-label">Unique Students</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{loading ? "…" : fmtDuration(avgDuration)}</div>
          <div className="stat-label">Avg Time in Lab</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{loading ? "…" : events.length}</div>
          <div className="stat-label">Total Events</div>
        </div>
      </div>

      {/* ── Charts ── */}
      <div className="dash-charts">

        {/* Activity by Hour */}
        <div className="dash-section">
          <h2 className="dash-section-title">Activity by Hour</h2>
          {loading ? (
            <p className="dash-empty">Loading…</p>
          ) : events.length === 0 ? (
            <p className="dash-empty">No events on this date.</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={hourlyData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="hour"
                    tickFormatter={h => `${h % 12 || 12}${h < 12 ? "a" : "p"}`}
                    tick={{ fontSize: 11, fill: "#9ca3af" }}
                  />
                  <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} allowDecimals={false} />
                  <Tooltip
                    formatter={(val, name) => [val, name === "checkins" ? "Check Ins" : "Check Outs"]}
                    labelFormatter={h => {
                      const suffix = h < 12 ? "AM" : "PM";
                      return `${h % 12 || 12}:00 ${suffix}`;
                    }}
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                  />
                  <Bar dataKey="checkins" fill="#003DA5" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="checkouts" fill="#fbbf24" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="chart-legend">
                <span className="legend-dot" style={{ background: "#003DA5" }} /> Check In
                <span className="legend-dot" style={{ background: "#fbbf24", marginLeft: 16 }} /> Check Out
              </div>
            </>
          )}
        </div>

        {/* Section Breakdown */}
        <div className="dash-section">
          <h2 className="dash-section-title">Section Breakdown</h2>
          {loading ? (
            <p className="dash-empty">Loading…</p>
          ) : sectionData.length === 0 ? (
            <p className="dash-empty">No check-in data.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={sectionData}
                layout="vertical"
                margin={{ top: 4, right: 24, left: 16, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#9ca3af" }} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fontSize: 11, fill: "#374151" }}
                  width={72}
                />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Bar dataKey="count" name="Check-ins" radius={[0, 4, 4, 0]}>
                  {sectionData.map((_, i) => (
                    <Cell key={i} fill={SECTION_COLORS[i % SECTION_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── Currently In Lab (today only) ── */}
      {isToday && (
        <div className="dash-section">
          <h2 className="dash-section-title">Currently In Lab</h2>
          {loading ? (
            <p className="dash-empty">Loading…</p>
          ) : checkedIn.length === 0 ? (
            <p className="dash-empty">No students currently checked in.</p>
          ) : (
            <div className="student-grid">
              {checkedIn.map(s => (
                <div className="student-card" key={s.sid}>
                  <div className="student-avatar">{s.name ? s.name[0].toUpperCase() : "?"}</div>
                  <div className="student-info">
                    <div className="student-name">{s.name}</div>
                    <div className="student-meta">SID: {s.sid}</div>
                    <div className="student-meta">{s.class}</div>
                    <div className="student-meta checked-in-time">In since {fmt(s.ts)}</div>
                  </div>
                  <span className="badge-in">IN</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Top Visitors ── */}
      {!loading && topVisitors.length > 0 && (
        <div className="dash-section">
          <h2 className="dash-section-title">
            {isToday ? "Most Frequent Visitors Today" : "Visitors on This Day"}
          </h2>
          <div className="top-visitors">
            {topVisitors.map((v, i) => (
              <div className="visitor-row" key={v.sid}>
                <span className="visitor-rank">#{i + 1}</span>
                <div className="student-avatar" style={{ width: 32, height: 32, fontSize: 14, flexShrink: 0 }}>
                  {v.name[0].toUpperCase()}
                </div>
                <div className="visitor-info">
                  <span className="visitor-name">{v.name}</span>
                  <span className="visitor-meta">{v.class}</span>
                </div>
                <div className="visitor-stats">
                  <span className="visitor-count">{v.count} visit{v.count !== 1 ? "s" : ""}</span>
                  {v.totalMins != null && (
                    <span className="visitor-duration">{fmtDuration(v.totalMins)} in lab</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Activity Log ── */}
      <div className="dash-section">
        <h2 className="dash-section-title">Activity Log</h2>
        {loading ? (
          <p className="dash-empty">Loading…</p>
        ) : sortedEvents.length === 0 ? (
          <p className="dash-empty">No events on this date.</p>
        ) : (
          <div className="table-wrap">
            <table className="event-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Name</th>
                  <th>SID</th>
                  <th>Class</th>
                  <th>Event</th>
                  <th>Camera</th>
                </tr>
              </thead>
              <tbody>
                {sortedEvents.map((e, i) => (
                  <tr key={i}>
                    <td className="td-mono">{fmt(e.ts)}</td>
                    <td>{e.name || "—"}</td>
                    <td className="td-mono">{e.sid || "—"}</td>
                    <td>{e.class || "—"}</td>
                    <td>
                      <span className={e.event === "checkin" ? "badge-checkin" : "badge-checkout"}>
                        {e.event === "checkin" ? "Check In" : "Check Out"}
                      </span>
                    </td>
                    <td className="td-mono">{e.camera_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
