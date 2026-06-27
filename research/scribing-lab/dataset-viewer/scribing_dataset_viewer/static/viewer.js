const SVG_NS = "http://www.w3.org/2000/svg";

const state = {
  datasets: [],
  active: null,
  samples: [],
  filterChar: null,
  selectedIndex: null,
  thumb: 110,
};

const els = {
  datasetList: document.getElementById("datasetList"),
  activeName: document.getElementById("activeName"),
  activeStats: document.getElementById("activeStats"),
  charFilter: document.getElementById("charFilter"),
  grid: document.getElementById("grid"),
  empty: document.getElementById("empty"),
  detail: document.getElementById("detail"),
  detailChar: document.getElementById("detailChar"),
  detailSvg: document.getElementById("detailSvg"),
  detailMeta: document.getElementById("detailMeta"),
};

async function loadDatasets() {
  const res = await fetch("/api/datasets");
  const payload = await res.json();
  state.datasets = payload.datasets;
  renderDatasetList();
  if (!state.active && state.datasets.length) {
    selectDataset(state.datasets[0].name);
  }
}

function renderDatasetList() {
  els.datasetList.replaceChildren();
  for (const ds of state.datasets) {
    const btn = document.createElement("button");
    btn.className = `dataset-item${state.active === ds.name ? " active" : ""}`;
    const sub = [ds.writer, ds.charset, `${ds.sample_count} samples`].filter(Boolean).join(" / ");
    btn.innerHTML = `<div class="name"></div><div class="sub"></div>`;
    btn.querySelector(".name").textContent = ds.name;
    btn.querySelector(".sub").textContent = sub;
    btn.addEventListener("click", () => selectDataset(ds.name));
    els.datasetList.appendChild(btn);
  }
}

async function selectDataset(name) {
  const ds = state.datasets.find((d) => d.name === name);
  if (!ds) return;
  state.active = name;
  state.filterChar = null;
  state.selectedIndex = null;
  closeDetail();
  renderDatasetList();
  els.activeName.textContent = name;
  els.activeStats.textContent = "読み込み中…";
  els.empty.style.display = "none";
  els.grid.replaceChildren();

  const res = await fetch(ds.data_url);
  const text = await res.text();
  state.samples = parseJsonl(text);

  const chars = new Set(state.samples.map((s) => s.char));
  els.activeStats.textContent = `${state.samples.length} samples / ${chars.size} chars`;
  renderCharFilter();
  renderGrid();
}

function parseJsonl(text) {
  const out = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      out.push(JSON.parse(trimmed));
    } catch {
      // 壊れた行はスキップ
    }
  }
  return out;
}

function charCounts() {
  const counts = new Map();
  for (const s of state.samples) {
    counts.set(s.char, (counts.get(s.char) ?? 0) + 1);
  }
  return counts;
}

function renderCharFilter() {
  els.charFilter.replaceChildren();
  const counts = charCounts();
  if (counts.size <= 1) return;

  const all = document.createElement("button");
  all.className = `chip${state.filterChar === null ? " active" : ""}`;
  all.innerHTML = `すべて<span class="n">${state.samples.length}</span>`;
  all.addEventListener("click", () => setFilter(null));
  els.charFilter.appendChild(all);

  for (const ch of [...counts.keys()].sort()) {
    const chip = document.createElement("button");
    chip.className = `chip${state.filterChar === ch ? " active" : ""}`;
    chip.innerHTML = `${escapeHtml(ch)}<span class="n">${counts.get(ch)}</span>`;
    chip.addEventListener("click", () => setFilter(ch));
    els.charFilter.appendChild(chip);
  }
}

function setFilter(ch) {
  state.filterChar = ch;
  renderCharFilter();
  renderGrid();
}

function visibleSamples() {
  if (state.filterChar === null) return state.samples.map((s, i) => [s, i]);
  return state.samples
    .map((s, i) => [s, i])
    .filter(([s]) => s.char === state.filterChar);
}

function renderGrid() {
  els.grid.style.setProperty("--thumb", `${state.thumb}px`);
  els.grid.replaceChildren();
  const frag = document.createDocumentFragment();
  for (const [sample, index] of visibleSamples()) {
    const cell = document.createElement("div");
    cell.className = `thumb${state.selectedIndex === index ? " selected" : ""}`;
    cell.appendChild(buildSvg(sample, state.thumb - 16));
    const label = document.createElement("div");
    label.className = "label";
    label.textContent = sample.char;
    cell.appendChild(label);
    cell.addEventListener("click", () => openDetail(index));
    frag.appendChild(cell);
  }
  els.grid.appendChild(frag);
}

function buildSvg(sample, px) {
  const cw = sample.canvas?.width || 100;
  const ch = sample.canvas?.height || 100;
  const scale = px / Math.max(cw, ch);
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${cw} ${ch}`);
  svg.setAttribute("width", (cw * scale).toFixed(1));
  svg.setAttribute("height", (ch * scale).toFixed(1));

  const bg = document.createElementNS(SVG_NS, "rect");
  bg.setAttribute("width", cw);
  bg.setAttribute("height", ch);
  bg.setAttribute("fill", "#ffffff");
  svg.appendChild(bg);

  const cell = sample.guide?.cell;
  if (cell) {
    const rect = document.createElementNS(SVG_NS, "rect");
    rect.setAttribute("x", cell.x);
    rect.setAttribute("y", cell.y);
    rect.setAttribute("width", cell.width);
    rect.setAttribute("height", cell.height);
    rect.setAttribute("fill", "none");
    rect.setAttribute("stroke", "#e2e0d6");
    rect.setAttribute("stroke-dasharray", "4 4");
    svg.appendChild(rect);
  }

  const strokeWidth = Math.max(0.8, 1.6 / scale);
  for (const stroke of sample.strokes ?? []) {
    const pts = stroke.points ?? [];
    if (pts.length < 2) continue;
    const d = pts
      .map((p, i) => `${i ? "L" : "M"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
      .join(" ");
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "#1f2937");
    path.setAttribute("stroke-width", strokeWidth.toFixed(2));
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    svg.appendChild(path);
  }
  return svg;
}

function openDetail(index) {
  const sample = state.samples[index];
  if (!sample) return;
  state.selectedIndex = index;
  renderGrid();
  els.detail.hidden = false;
  els.detailChar.textContent = sample.char;
  els.detailSvg.replaceChildren(buildSvg(sample, 280));
  els.detailMeta.textContent = describe(sample);
}

function describe(sample) {
  const points = (sample.strokes ?? []).flatMap((s) => s.points ?? []);
  const ts = points.map((p) => p.t).filter((v) => typeof v === "number");
  const pr = points.map((p) => p.pressure).filter((v) => typeof v === "number");
  const range = (a) => (a.length ? `${Math.min(...a).toFixed(2)} – ${Math.max(...a).toFixed(2)}` : "-");
  const lines = [
    `char: ${sample.char}  (${sample.charCode ?? ""})`,
    `sampleId: ${sample.sampleId ?? ""}`,
    `writer: ${sample.writerId ?? ""}`,
    `strokes: ${(sample.strokes ?? []).length}`,
    `points: ${points.length}`,
    `t(ms): ${ts.length ? `${Math.round(Math.min(...ts))} – ${Math.round(Math.max(...ts))}` : "-"}`,
    `pressure: ${range(pr)}`,
    `canvas: ${sample.canvas?.width ?? "?"}×${sample.canvas?.height ?? "?"}`,
  ];
  if (sample.guide?.cell) {
    const c = sample.guide.cell;
    lines.push(`guide.cell: x${c.x} y${c.y} ${c.width}×${c.height}`);
  }
  return lines.join("\n");
}

function closeDetail() {
  els.detail.hidden = true;
  state.selectedIndex = null;
}

function setThumb(delta) {
  state.thumb = Math.max(70, Math.min(260, state.thumb + delta));
  renderGrid();
}

function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
}

document.getElementById("reload").addEventListener("click", loadDatasets);
document.getElementById("zoomIn").addEventListener("click", () => setThumb(20));
document.getElementById("zoomOut").addEventListener("click", () => setThumb(-20));
document.getElementById("detailClose").addEventListener("click", closeDetail);

loadDatasets();
