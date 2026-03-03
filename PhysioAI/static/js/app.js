// app.js — PhysioAI Frontend

const EX = {};
let selEx = null, running = false, pollId = null;
let usingRealCam = false, animId = null, frameCount = 0, lastFt = 0;
let lastSpokenRep = 0, lastFb = '', speaking = false, speechQ = [];

// ── Boot ──────────────────────────────────────────────────────────────────
async function boot() {
  const r = await fetch('/api/exercises');
  Object.assign(EX, await r.json());
  renderExGrid();
  checkCamStatus();
  loadHistory();
  loadStats();
}

async function checkCamStatus() {
  const r = await fetch('/api/cam_status');
  const d = await r.json();
  const el = document.getElementById('poseEngine');
  if (d.mediapipe)  { el.textContent = 'MediaPipe + OpenCV'; el.className = 'ai-v live'; }
  else if (d.cv2)   { el.textContent = 'OpenCV (no pose)';   el.className = 'ai-v'; }
  else              { el.textContent = 'Demo mode';           el.className = 'ai-v'; }
}

// ── Exercise grid ─────────────────────────────────────────────────────────
function renderExGrid() {
  const g = document.getElementById('exGrid');
  g.innerHTML = '';
  Object.entries(EX).forEach(([k, ex]) => {
    const c = document.createElement('div');
    c.className = 'ex-card'; c.dataset.k = k;
    c.innerHTML = `<div class="ex-icon">${ex.icon}</div><div class="ex-name">${ex.name}</div><div class="ex-desc">${ex.description}</div>`;
    c.onclick = () => pickEx(k, c);
    g.appendChild(c);
  });
}

function pickEx(k, el) {
  if (running) return;
  selEx = k;
  document.querySelectorAll('.ex-card').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  const ex = EX[k];
  document.getElementById('exBadge').textContent = ex.name.toUpperCase();
  document.getElementById('repSlider').value = ex.target_reps;
  document.getElementById('repN').textContent = ex.target_reps;
  document.getElementById('tgtDisp').textContent = ex.target_reps;
  document.getElementById('remDisp').textContent = ex.target_reps;
}

// ── Workout ───────────────────────────────────────────────────────────────
async function toggleWorkout() {
  running ? await stopWorkout() : await startWorkout();
}

async function startWorkout() {
  const pat = document.getElementById('patName').value.trim();
  if (!pat)  { alert('Please enter a patient name.'); return; }
  if (!selEx){ alert('Please select an exercise.'); return; }
  const target = parseInt(document.getElementById('repSlider').value);

  await fetch('/api/start', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ patient:pat, exercise:selEx, target_reps:target })
  });

  running = true; lastSpokenRep = 0; lastFb = '';
  document.getElementById('mainBtn').textContent = '⏹ STOP SESSION';
  document.getElementById('mainBtn').classList.add('stop');
  document.getElementById('camPh').classList.add('hidden');
  document.getElementById('hud').classList.add('on');
  document.getElementById('confWrap').classList.add('on');
  document.getElementById('liveDot').style.opacity = '1';
  document.getElementById('hudEx').textContent = EX[selEx]?.name || '—';

  speak('Starting ' + EX[selEx].name + '. Get ready!');
  await startCam();
  startLoop();
  pollId = setInterval(() => { loadHistory(); loadStats(); }, 3000);
}

async function stopWorkout() {
  running = false;
  clearInterval(pollId);
  cancelAnimationFrame(animId);
  await fetch('/api/stop', { method:'POST' });
  stopCam();
  document.getElementById('mainBtn').textContent = '▶ START SESSION';
  document.getElementById('mainBtn').classList.remove('stop');
  document.getElementById('camPh').classList.remove('hidden');
  document.getElementById('hud').classList.remove('on');
  document.getElementById('confWrap').classList.remove('on');
  document.getElementById('liveDot').style.opacity = '0.3';
  setTimeout(() => { loadHistory(); loadStats(); }, 500);
}

// ── Camera ────────────────────────────────────────────────────────────────
async function startCam() {
  try {
    const r = await fetch('/api/cam_start', { method:'POST' });
    const d = await r.json();
    if (d.ok) {
      const img = document.getElementById('camStream');
      img.src = '/video_feed?' + Date.now();
      img.style.display = 'block';
      img.onerror = () => { img.style.display = 'none'; usingRealCam = false; };
      document.getElementById('demoCanvas').style.display = 'none';
      document.getElementById('camBadge').style.display = 'block';
      usingRealCam = true;
      showToast('📷 Live webcam active', 'ok');
    } else {
      usingRealCam = false;
      showToast('Demo mode — no webcam found', 'warn');
    }
  } catch(e) {
    usingRealCam = false;
  }
}

function stopCam() {
  fetch('/api/cam_stop', { method:'POST' }).catch(()=>{});
  const img = document.getElementById('camStream');
  img.src = ''; img.style.display = 'none';
  document.getElementById('demoCanvas').style.display = 'block';
  document.getElementById('demoCanvas').getContext('2d').clearRect(0, 0, 9999, 9999);
  document.getElementById('camBadge').style.display = 'none';
  usingRealCam = false;
}

// ── Animation loop ────────────────────────────────────────────────────────
function startLoop() {
  async function loop(ts) {
    if (!running) return;
    animId = requestAnimationFrame(loop);
    frameCount++;

    if (usingRealCam) {
      // Python handles everything — just poll status
      if (frameCount % 8 === 0) {
        try {
          const r = await fetch('/api/status');
          updateUI(await r.json());
        } catch(e) {}
      }
      return;
    }

    // Demo mode — animated skeleton + simulated reps
    const canvas = document.getElementById('demoCanvas');
    const ctx = canvas.getContext('2d');
    canvas.width  = canvas.offsetWidth  || 640;
    canvas.height = canvas.offsetHeight || 480;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawDemoSkeleton(ctx, canvas.width, canvas.height, ts);

    if (frameCount % 5 === 0) {
      try {
        const r = await fetch('/api/landmarks', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ landmarks: [] })
        });
        updateUI(await r.json());
      } catch(e) {}
    }

    ctx.font = "500 11px 'DM Mono',monospace";
    ctx.fillStyle = 'rgba(96,165,250,.55)';
    ctx.fillText('DEMO MODE', 12, canvas.height - 12);
  }
  requestAnimationFrame(loop);
}

// ── Exercise-specific demo skeletons ──────────────────────────────────────
function drawDemoSkeleton(ctx, W, H, ts) {
  const sw = (Math.sin(ts * 0.0018) + 1) / 2;

  let p = {
    nose:[.50,.09], lSh:[.38,.26], rSh:[.62,.26],
    lEl:[.30,.42],  rEl:[.70,.42],
    lWr:[.26,.58],  rWr:[.74,.58],
    lHi:[.41,.54],  rHi:[.59,.54],
    lKn:[.40,.72],  rKn:[.60,.72],
    lAn:[.39,.90],  rAn:[.61,.90]
  };

  switch(selEx) {
    case 'bicep_curl':
      p.lEl=[.30-sw*.03, .42-sw*.05]; p.lWr=[.28-sw*.04, .58-sw*.22]; break;
    case 'squat':
      const d=sw*.13;
      p.lHi=[.41,.54+d]; p.rHi=[.59,.54+d];
      p.lKn=[.38,.72+d*.5]; p.rKn=[.62,.72+d*.5];
      p.lSh=[.38,.26+d]; p.rSh=[.62,.26+d]; p.nose=[.50,.09+d]; break;
    case 'lateral_raise':
      const ra=sw*.18;
      p.lEl=[.30-ra,.42-ra*.8]; p.lWr=[.22-ra,.46-ra*1.4];
      p.rEl=[.70+ra,.42-ra*.8]; p.rWr=[.78+ra,.46-ra*1.4]; break;
    case 'bench_press':
      const bp=sw*.16;
      p.lEl=[.32,.42-bp]; p.lWr=[.30,.30-bp];
      p.rEl=[.68,.42-bp]; p.rWr=[.70,.30-bp]; break;
    case 'leg_raise':
      const lr=sw*.20;
      p.lKn=[.40+lr*.4,.72-lr]; p.rKn=[.60-lr*.4,.72-lr];
      p.lAn=[.42+lr*.5,.90-lr*1.5]; p.rAn=[.58-lr*.5,.90-lr*1.5]; break;
    case 'shoulder_press':
      const sp=sw*.22;
      p.lEl=[.34,.42-sp*.6]; p.lWr=[.36,.26-sp];
      p.rEl=[.66,.42-sp*.6]; p.rWr=[.64,.26-sp]; break;
  }

  const conn=[['lSh','rSh'],['lSh','lEl'],['lEl','lWr'],['rSh','rEl'],['rEl','rWr'],
    ['lSh','lHi'],['rSh','rHi'],['lHi','rHi'],['lHi','lKn'],['lKn','lAn'],
    ['rHi','rKn'],['rKn','rAn'],['nose','lSh'],['nose','rSh']];

  ctx.strokeStyle='rgba(59,130,246,.6)'; ctx.lineWidth=2.5;
  ctx.shadowBlur=8; ctx.shadowColor='rgba(59,130,246,.4)';
  conn.forEach(([a,b])=>{
    if(!p[a]||!p[b])return;
    ctx.beginPath(); ctx.moveTo(p[a][0]*W,p[a][1]*H); ctx.lineTo(p[b][0]*W,p[b][1]*H); ctx.stroke();
  });

  ctx.shadowBlur=11; ctx.shadowColor='rgba(16,217,124,.55)'; ctx.fillStyle='#10d97c';
  Object.values(p).forEach(([x,y])=>{ctx.beginPath();ctx.arc(x*W,y*H,5,0,Math.PI*2);ctx.fill();});

  // Angle arc
  const arcMap={bicep_curl:['lSh','lEl','lWr'],squat:['lHi','lKn','lAn'],
    lateral_raise:['lHi','lSh','lEl'],bench_press:['lSh','lEl','lWr'],
    leg_raise:['lSh','lHi','lKn'],shoulder_press:['lEl','lSh','lHi']};
  const [ja,jb,jc]=(arcMap[selEx]||['lSh','lEl','lWr']);
  if(p[ja]&&p[jb]&&p[jc]){
    const bx=p[jb][0]*W, by=p[jb][1]*H;
    ctx.beginPath();
    ctx.arc(bx,by,26,Math.atan2(p[ja][1]*H-by,p[ja][0]*W-bx),Math.atan2(p[jc][1]*H-by,p[jc][0]*W-bx),false);
    ctx.strokeStyle='rgba(249,115,22,.7)'; ctx.lineWidth=2.5; ctx.shadowBlur=0; ctx.stroke();
  }
  ctx.shadowBlur=0;
}

// ── Update UI from state ──────────────────────────────────────────────────
function updateUI(d) {
  const reps   = d.reps   || 0;
  const target = d.target_reps || 10;
  const remain = Math.max(0, target - reps);

  const rEl = document.getElementById('repDisp');
  if (parseInt(rEl.textContent) !== reps) {
    rEl.textContent = reps; rEl.classList.add('pop');
    setTimeout(() => rEl.classList.remove('pop'), 200);
    if (reps > lastSpokenRep) {
      lastSpokenRep = reps;
      if      (reps === Math.floor(target/2)) speak('Halfway there! Keep going!');
      else if (reps === target - 1)           speak('Last one!');
      else if (reps > 0)                      speak(String(reps));
    }
  }
  document.getElementById('tgtDisp').textContent = target;
  document.getElementById('remDisp').textContent = remain;

  const pct = Math.min(100, Math.round(reps/target*100));
  document.getElementById('progFill').style.width = pct + '%';
  document.getElementById('progPct').textContent  = pct + '%';

  const dur = d.duration || 0;
  document.getElementById('durDisp').textContent =
    String(Math.floor(dur/60)).padStart(2,'0') + ':' + String(dur%60).padStart(2,'0');
  document.getElementById('calDisp').textContent = (d.calories||0).toFixed(1);

  const ang = d.angle || 0;
  document.getElementById('angleV').textContent  = ang + '°';
  document.getElementById('arcTxt').textContent  = ang + '°';
  const ex = EX[d.exercise] || {};
  const frac = Math.max(0, Math.min(1, (ang - (ex.down_threshold||30)) / ((ex.up_threshold||170) - (ex.down_threshold||30))));
  document.getElementById('arcFill').setAttribute('stroke-dashoffset', 157 * (1 - frac));

  const stage = d.stage || 'ready';
  document.getElementById('stageP').textContent = stage.toUpperCase();
  document.getElementById('stageP').className = 'sp' + (stage === 'down' ? ' dn' : '');
  document.getElementById('hudStage').textContent = stage.toUpperCase();

  const conf = Math.round((d.confidence||0)*100);
  document.getElementById('confFill').style.width = conf + '%';
  document.getElementById('confLbl').textContent  = `MODEL CONFIDENCE: ${conf}%`;

  if (d.feedback && d.feedback !== lastFb) {
    lastFb = d.feedback;
    const fb = document.getElementById('fbBand');
    fb.textContent = d.feedback;
    fb.className = 'fb' + (d.feedback.includes('🎉') ? ' ok' : '');
  }

  if (d.stage === 'complete' && running) {
    running = false;
    clearInterval(pollId);
    cancelAnimationFrame(animId);
    stopCam();
    document.getElementById('mainBtn').textContent = '▶ START SESSION';
    document.getElementById('mainBtn').classList.remove('stop');
    document.getElementById('camPh').classList.remove('hidden');
    document.getElementById('hud').classList.remove('on');
    document.getElementById('confWrap').classList.remove('on');
    document.getElementById('liveDot').style.opacity = '0.3';
    showModal(d);
    setTimeout(() => { loadHistory(); loadStats(); }, 500);
  }
}

// ── Modal ─────────────────────────────────────────────────────────────────
function showModal(d) {
  document.getElementById('mReps').textContent = d.reps;
  const dur = d.duration || 0;
  document.getElementById('mTime').textContent =
    String(Math.floor(dur/60)).padStart(2,'0') + ':' + String(dur%60).padStart(2,'0');
  document.getElementById('mCal').textContent = (d.calories||0).toFixed(1);
  document.getElementById('mSub').textContent = `Outstanding work, ${d.patient||'Patient'}!`;
  document.getElementById('modal').classList.add('show');
  speak('Congratulations! Set complete. Excellent work!');
}
function closeModal() {
  document.getElementById('modal').classList.remove('show');
  loadHistory(); loadStats();
}

// ── History & Stats ───────────────────────────────────────────────────────
async function loadHistory() {
  const r = await fetch('/api/history');
  const d = await r.json();
  const list = document.getElementById('histList');
  document.getElementById('histCnt').textContent = d.length;
  if (!d.length) {
    list.innerHTML = '<div class="empty">No sessions yet.<br/>Complete a workout to see history.</div>';
    return;
  }
  list.innerHTML = d.slice(0,20).map(s => `
    <div class="hi">
      <div class="ht"><span class="he">${s.exercise}</span><span class="hsc">${s.score}%</span></div>
      <div class="hm"><span>👤 ${s.patient}</span><span>🔁 ${s.reps} reps</span><span>🔥 ${s.calories} kcal</span><span>🕐 ${s.time}</span></div>
    </div>`).join('');
}

async function loadStats() {
  const r = await fetch('/api/stats');
  const d = await r.json();
  document.getElementById('totReps').textContent = d.total_reps;
  document.getElementById('totCal').textContent  = Math.round(d.total_calories);
  document.getElementById('totSess').textContent = d.total_sessions;
}

// ── Voice ─────────────────────────────────────────────────────────────────
function speak(txt) {
  if (!txt || !window.speechSynthesis) return;
  speechQ.push(txt);
  if (!speaking) nextSpeak();
}
function nextSpeak() {
  if (!speechQ.length) { speaking = false; voiceUI(false); return; }
  speaking = true; voiceUI(true);
  const u = new SpeechSynthesisUtterance(speechQ.shift());
  u.rate = 1.1;
  u.onend = () => setTimeout(nextSpeak, 150);
  speechSynthesis.speak(u);
}
function voiceUI(on) {
  document.getElementById('vInd').classList.toggle('on', on);
  document.getElementById('vLbl').textContent = on ? 'SPEAKING' : 'VOICE READY';
}

// ── Toast ─────────────────────────────────────────────────────────────────
function showToast(msg, type='') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'show' + (type ? ' '+type : '');
  setTimeout(() => t.className = '', 3500);
}

boot();
