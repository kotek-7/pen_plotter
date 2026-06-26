const state = {
  runs: [],
  active: null,
  scale: 1,
  x: 0,
  y: 0,
  dragging: false,
  dragStart: null,
};

const runList = document.getElementById('runList');
const activeRun = document.getElementById('activeRun');
const activeInput = document.getElementById('activeInput');
const viewport = document.getElementById('viewport');
const preview = document.getElementById('preview');
const empty = document.getElementById('empty');
const memo = document.getElementById('memo');

function applyTransform() {
  preview.style.transform = `translate(${state.x}px, ${state.y}px) scale(${state.scale})`;
}

function setScale(nextScale, originX = viewport.clientWidth / 2, originY = viewport.clientHeight / 2) {
  const clamped = Math.max(0.05, Math.min(20, nextScale));
  const beforeX = (originX - state.x) / state.scale;
  const beforeY = (originY - state.y) / state.scale;
  state.scale = clamped;
  state.x = originX - beforeX * state.scale;
  state.y = originY - beforeY * state.scale;
  applyTransform();
}

function fitPreview() {
  if (!preview.naturalWidth || !preview.naturalHeight) return;
  const padding = 28;
  const sx = (viewport.clientWidth - padding * 2) / preview.naturalWidth;
  const sy = (viewport.clientHeight - padding * 2) / preview.naturalHeight;
  state.scale = Math.max(0.05, Math.min(sx, sy));
  state.x = (viewport.clientWidth - preview.naturalWidth * state.scale) / 2;
  state.y = (viewport.clientHeight - preview.naturalHeight * state.scale) / 2;
  applyTransform();
}

function resetPreview() {
  state.scale = 1;
  state.x = 24;
  state.y = 24;
  applyTransform();
}

async function loadRuns() {
  const response = await fetch('/api/runs');
  const payload = await response.json();
  state.runs = payload.runs.toSorted((a, b) => b.name.localeCompare(a.name, "en", { sensitivity: "base" }));
  renderRuns();
  if (!state.active && state.runs.length) {
    selectRun(state.runs[0].name);
  }
  if (!state.runs.length) {
    activeRun.textContent = '';
    activeInput.textContent = '';
    empty.style.display = 'grid';
    memo.textContent = '';
  }
}

function renderRuns() {
  runList.replaceChildren();
  for (const run of state.runs) {
    const button = document.createElement('button');
    button.className = `run-item${state.active === run.name ? ' active' : ''}`;
    button.textContent = run.name;
    button.title = run.name;
    button.addEventListener('click', () => selectRun(run.name));
    runList.appendChild(button);
  }
}

async function selectRun(name) {
  const run = state.runs.find(item => item.name === name);
  if (!run) return;
  state.active = run.name;
  activeRun.textContent = run.name;
  activeRun.title = run.name;
  activeInput.textContent = '';
  renderRuns();
  empty.style.display = 'none';
  preview.src = `${run.preview_url}?t=${Date.now()}`;
  memo.textContent = '';
  if (run.has_input) {
    const response = await fetch(run.input_url);
    if (response.ok) activeInput.textContent = (await response.text()).trim();
  }
  if (run.has_memo) {
    const response = await fetch(run.memo_url);
    if (response.ok) memo.textContent = await response.text();
  }
}

preview.addEventListener('load', fitPreview);
document.getElementById('reload').addEventListener('click', loadRuns);
document.getElementById('zoomOut').addEventListener('click', () => setScale(state.scale / 1.2));
document.getElementById('zoomIn').addEventListener('click', () => setScale(state.scale * 1.2));
document.getElementById('fit').addEventListener('click', fitPreview);
document.getElementById('reset').addEventListener('click', resetPreview);

viewport.addEventListener('wheel', event => {
  event.preventDefault();
  const rect = viewport.getBoundingClientRect();
  const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
  setScale(state.scale * factor, event.clientX - rect.left, event.clientY - rect.top);
}, { passive: false });

viewport.addEventListener('pointerdown', event => {
  state.dragging = true;
  state.dragStart = { pointerX: event.clientX, pointerY: event.clientY, x: state.x, y: state.y };
  viewport.classList.add('dragging');
  viewport.setPointerCapture(event.pointerId);
});

viewport.addEventListener('pointermove', event => {
  if (!state.dragging || !state.dragStart) return;
  state.x = state.dragStart.x + event.clientX - state.dragStart.pointerX;
  state.y = state.dragStart.y + event.clientY - state.dragStart.pointerY;
  applyTransform();
});

viewport.addEventListener('pointerup', event => {
  state.dragging = false;
  state.dragStart = null;
  viewport.classList.remove('dragging');
  viewport.releasePointerCapture(event.pointerId);
});

window.addEventListener('resize', fitPreview);
loadRuns();
