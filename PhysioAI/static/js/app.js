// app.js — PhysioAI Frontend

const EX = {};
let selEx = null, running = false, pollId = null;
let usingRealCam = false, animId = null, frameCount = 0;
let lastSpokenRep = 0, lastFb = '', speaking = false, speechQ = [];

// ── Boot ─────────────────────────────────────────────────────
async function boot() {
  try {
    const r = await fetch('/api/exercises');
    const data = await r.json();

    Object.assign(EX, data);

    console.log("Exercises loaded:", EX);

    renderExGrid();
    checkCamStatus();
    loadHistory();
    loadStats();
  } catch (err) {
    console.error("Failed to load exercises:", err);
  }
}

// ── Camera status ────────────────────────────────────────────
async function checkCamStatus() {
  try {
    const r = await fetch('/api/cam_status');
    const d = await r.json();

    const el = document.getElementById('poseEngine');
    if (!el) return;

    if (d.mediapipe) {
      el.textContent = 'MediaPipe + OpenCV';
      el.className = 'ai-v live';
    }
    else if (d.cv2) {
      el.textContent = 'OpenCV (no pose)';
      el.className = 'ai-v';
    }
    else {
      el.textContent = 'Demo mode';
      el.className = 'ai-v';
    }
  } catch(e) {
    console.log("Camera status error");
  }
}

// ── Exercise grid ────────────────────────────────────────────
function renderExGrid() {
  const g = document.getElementById('exGrid');
  if (!g) return;

  g.innerHTML = '';

  Object.entries(EX).forEach(([k, ex]) => {
    const c = document.createElement('div');

    c.className = 'ex-card';
    c.dataset.k = k;

    c.innerHTML = `
      <div class="ex-icon">${ex.icon}</div>
      <div class="ex-name">${ex.name}</div>
      <div class="ex-desc">${ex.description}</div>
    `;

    c.onclick = () => pickEx(k, c);

    g.appendChild(c);
  });
}

// ── Select exercise ──────────────────────────────────────────
function pickEx(k, el) {
  if (running) return;

  selEx = k;

  document.querySelectorAll('.ex-card')
    .forEach(c => c.classList.remove('active'));

  el.classList.add('active');

  const ex = EX[k];

  document.getElementById('exBadge').textContent =
    ex.name.toUpperCase();

  document.getElementById('repSlider').value =
    ex.target_reps;

  document.getElementById('repN').textContent =
    ex.target_reps;

  document.getElementById('tgtDisp').textContent =
    ex.target_reps;

  document.getElementById('remDisp').textContent =
    ex.target_reps;
}

// ── Start / Stop Workout ─────────────────────────────────────
async function toggleWorkout() {
  running ? stopWorkout() : startWorkout();
}

async function startWorkout() {

  const pat = document.getElementById('patName').value.trim();

  if (!pat) {
    alert("Enter patient name");
    return;
  }

  if (!selEx) {
    alert("Select an exercise");
    return;
  }

  const target =
    parseInt(document.getElementById('repSlider').value);

  await fetch('/api/start', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      patient: pat,
      exercise: selEx,
      target_reps: target
    })
  });

  running = true;

  document.getElementById('mainBtn').textContent =
    '⏹ STOP SESSION';

  startLoop();
}

// ── Stop workout ─────────────────────────────────────────────
async function stopWorkout() {

  running = false;

  cancelAnimationFrame(animId);

  await fetch('/api/stop', { method:'POST' });

  document.getElementById('mainBtn').textContent =
    '▶ START SESSION';
}

// ── Animation loop ───────────────────────────────────────────
function startLoop() {

  async function loop() {

    if (!running) return;

    animId = requestAnimationFrame(loop);

    frameCount++;

    if (frameCount % 8 === 0) {
      try {
        const r = await fetch('/api/status');
        updateUI(await r.json());
      } catch(e) {}
    }
  }

  requestAnimationFrame(loop);
}

// ── Update UI ────────────────────────────────────────────────
function updateUI(d) {

  const reps = d.reps || 0;
  const target = d.target_reps || 10;

  const remain = Math.max(0, target - reps);

  document.getElementById('repDisp').textContent = reps;
  document.getElementById('tgtDisp').textContent = target;
  document.getElementById('remDisp').textContent = remain;

  const pct = Math.min(100,
    Math.round(reps / target * 100));

  document.getElementById('progFill').style.width =
    pct + '%';

  document.getElementById('progPct').textContent =
    pct + '%';

  const dur = d.duration || 0;

  document.getElementById('durDisp').textContent =
    String(Math.floor(dur/60)).padStart(2,'0')
    + ':'
    + String(dur%60).padStart(2,'0');

  document.getElementById('calDisp').textContent =
    (d.calories || 0).toFixed(1);
}

// ── History ──────────────────────────────────────────────────
async function loadHistory() {

  try {
    const r = await fetch('/api/history');
    const d = await r.json();

    const list = document.getElementById('histList');

    if (!list) return;

    if (!d.length) {
      list.innerHTML =
      '<div class="empty">No sessions yet</div>';
      return;
    }

    list.innerHTML = d.map(s => `
      <div class="hi">
        <div>${s.exercise}</div>
        <div>${s.reps} reps</div>
      </div>
    `).join('');
  } catch(e){}
}

// ── Stats ────────────────────────────────────────────────────
async function loadStats() {

  try {
    const r = await fetch('/api/stats');
    const d = await r.json();

    document.getElementById('totReps').textContent =
      d.total_reps;

    document.getElementById('totCal').textContent =
      Math.round(d.total_calories);

    document.getElementById('totSess').textContent =
      d.total_sessions;
  } catch(e){}
}

// ── Voice ────────────────────────────────────────────────────
function speak(txt) {

  if (!window.speechSynthesis) return;

  const u = new SpeechSynthesisUtterance(txt);

  u.rate = 1.1;

  speechSynthesis.speak(u);
}

// ── Toast ────────────────────────────────────────────────────
function showToast(msg) {

  const t = document.getElementById('toast');

  if (!t) return;

  t.textContent = msg;

  t.className = 'show';

  setTimeout(() => t.className = '', 3500);
}

// ── Start after DOM loads ────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  boot();
});
