import { useState, useRef } from "react";
import { QRCodeCanvas } from "qrcode.react";

const COURSES = [
  "CS131 — Section 021",
  "CS131 — Section 022",
  "CS131 — Section 023",
  "CS131 — Section 024",
];

export default function App() {
  const [form, setForm] = useState({ name: "", sid: "", course: "" });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const qrRef = useRef(null);

  const qrPayload = JSON.stringify({
    name: form.name.trim(),
    sid: form.sid.trim(),
    class: form.course,
  });

  function handleChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError("");
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.sid.trim() || !form.course) {
      setError("Please fill in all fields.");
      return;
    }
    if (!/^\d{7,10}$/.test(form.sid.trim())) {
      setError("SID must be 7–10 digits.");
      return;
    }
    setSubmitted(true);
  }

  function handleDownload() {
    const canvas = qrRef.current?.querySelector("canvas");
    if (!canvas) return;
    const link = document.createElement("a");
    link.download = `UCR-checkin-${form.sid.trim()}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
  }

  function handleReset() {
    setForm({ name: "", sid: "", course: "" });
    setSubmitted(false);
    setError("");
  }

  return (
    <div className="page">
      <div className="card">
        <div className="logo-row">
          <span className="logo-dot" />
          <span className="logo-text">UC Riverside · Lab Attendance</span>
        </div>

        {!submitted ? (
          <>
            <h1>Generate Your Check-In QR Code</h1>
            <p className="subtitle">
              Fill in your details once. Save the QR code to your phone and hold
              it toward the camera when entering or leaving the lab.
            </p>

            <form onSubmit={handleSubmit} noValidate>
              <div className="field">
                <label htmlFor="name">Full Name</label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  placeholder="e.g. Susie A. Bear"
                  value={form.name}
                  onChange={handleChange}
                  autoComplete="name"
                  required
                />
              </div>

              <div className="field">
                <label htmlFor="sid">Student ID (SID)</label>
                <input
                  id="sid"
                  name="sid"
                  type="text"
                  placeholder="9-digit R number"
                  value={form.sid}
                  onChange={handleChange}
                  inputMode="numeric"
                  required
                />
              </div>

              <div className="field">
                <label htmlFor="course">Course / Lab Section</label>
                <select
                  id="course"
                  name="course"
                  value={form.course}
                  onChange={handleChange}
                  required
                >
                  <option value="">Select your section…</option>
                  {COURSES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              {error && <p className="error">{error}</p>}

              <button type="submit">Generate QR Code</button>
            </form>
          </>
        ) : (
          <>
            <h1>Your QR Code is Ready</h1>
            <p className="subtitle">
              Screenshot this page or tap <strong>Download</strong> and save it
              to your Photos. Show it to the camera to check in or out.
            </p>

            <div className="instructions">
              <strong>How to use:</strong> Open this image on your phone, stand
              in front of the lab camera, and hold your screen toward it. The
              system checks you in automatically. Hold it again to check out.
            </div>

            <div className="qr-wrapper" ref={qrRef}>
              <QRCodeCanvas
                value={qrPayload}
                size={220}
                marginSize={2}
                level="M"
                fgColor="#1a1a2e"
                bgColor="#ffffff"
              />
            </div>

            <div className="info-box">
              <div className="info-row">
                <span className="info-label">Name</span>
                <span className="info-value">{form.name}</span>
              </div>
              <div className="info-row">
                <span className="info-label">SID</span>
                <span className="info-value">{form.sid}</span>
              </div>
              <div className="info-row">
                <span className="info-label">Course</span>
                <span className="info-value">{form.course}</span>
              </div>
            </div>

            <button className="btn-green" onClick={handleDownload}>
              Download QR Code
            </button>
            <button className="btn-ghost" onClick={handleReset}>
              Generate a different code
            </button>
          </>
        )}
      </div>
    </div>
  );
}
