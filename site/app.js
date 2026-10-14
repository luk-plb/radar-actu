/* Radar de l'actu : lit les JSON produits par le pipeline (site/data/) et dessine
   le réseau de mots (D3 force) et les tendances. */

const CATEGORIES = [
  ["politique", "Politique", "--cat-politique"],
  ["international", "International", "--cat-international"],
  ["économie", "Économie", "--cat-economie"],
  ["société", "Société", "--cat-societe"],
  ["sport", "Sport", "--cat-sport"],
  ["culture", "Culture", "--cat-culture"],
  ["sciences", "Sciences & santé", "--cat-sciences"],
  ["général", "Autres", "--cat-general"],
];
const CAT = Object.fromEntries(CATEGORIES.map(([id, label, token]) => [id, { label, token }]));
const SERIES_TOKENS = ["--s1", "--s2", "--s3"];

const state = {
  view: "network",
  window: "24h",
  category: null,
  selected: null,
  focused: false,       // le voisinage du mot n'est mis en avant qu'après un clic
  graphs: {},
  trends: null,
  meta: null,
  compare: [],          // [{word, slot}] : la couleur suit le mot, pas son rang
};

const $ = (sel) => document.querySelector(sel);
const css = (token) => getComputedStyle(document.documentElement).getPropertyValue(token).trim();
const catColor = (c) => css((CAT[c] || CAT["général"]).token);
const fmtInt = new Intl.NumberFormat("fr-FR");
const fmtPct = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
const isMobile = () => window.matchMedia("(max-width: 900px)").matches;
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function relativeTime(iso) {
  const minutes = Math.round((Date.now() - new Date(iso)) / 60000);
  if (minutes < 60) return `il y a ${Math.max(minutes, 1)} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `il y a ${hours} h`;
  return `il y a ${Math.round(hours / 24)} j`;
}

function trendBadge(score) {
  if (score == null || Math.abs(score) < 0.5) return "";
  const ratio = Math.pow(2, Math.abs(score));
  const up = score > 0;
  const label = ratio >= 10 ? "×10+" : `×${fmtPct.format(ratio)}`;
  return `<span class="badge ${up ? "up" : "down"}" title="${up ? "Plus" : "Moins"} cité qu'à l'habitude">${up ? "▲" : "▼"} ${label}</span>`;
}

/* ---------- Tooltip ---------- */
const tooltip = $("#tooltip");
function showTooltip(html, event) {
  tooltip.innerHTML = html;
  tooltip.hidden = false;
  const pad = 14;
  const { innerWidth: w, innerHeight: h } = window;
  const rect = tooltip.getBoundingClientRect();
  let x = event.clientX + pad, y = event.clientY + pad;
  if (x + rect.width > w - 8) x = event.clientX - rect.width - pad;
  if (y + rect.height > h - 8) y = event.clientY - rect.height - pad;
  tooltip.style.left = `${Math.max(8, x)}px`;
  tooltip.style.top = `${Math.max(8, y)}px`;
}
const hideTooltip = () => { tooltip.hidden = true; };

/* ---------- Données ---------- */
async function loadJson(name) {
  const res = await fetch(`data/${name}.json`, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${name}.json : ${res.status}`);
  return res.json();
}

async function init() {
  setupTheme();
  try {
    const [g24, g7, trends, meta] = await Promise.all(
      ["graph-24h", "graph-7d", "trends", "meta"].map(loadJson));
    Object.assign(state, { graphs: { "24h": g24, "7d": g7 }, trends, meta });
  } catch (err) {
    $("#updated").textContent = "Données indisponibles pour le moment.";
    console.error(err);
    return;
  }
  renderMeta();
  setupControls();
  renderNetworkView();
  renderTrendsView();
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (state.view === "network") drawNetwork(); else drawLineChart();
    }, 200);
  });
}

function renderMeta() {
  const { meta } = state;
  const date = new Date(meta.generated_at);
  $("#updated").textContent = `Mis à jour ${date.toLocaleString("fr-FR", { weekday: "long", hour: "2-digit", minute: "2-digit" })} · ${fmtInt.format(meta.articles_24h)} titres sur 24 h`;
  const ok = meta.sources.filter((s) => s.ok).length;
  $("#n-sources").textContent = meta.sources.length || 20;
  $("#sources").innerHTML = meta.sources.map((s) =>
    `<li class="${s.ok ? "" : "ko"}">${escapeHtml(s.name)} — ${s.ok ? `${s.entries} titres récents` : "indisponible"}</li>`).join("")
    + (meta.sources.length ? "" : "<li>Statut inconnu</li>");
  $("#sources").closest("details").querySelector("summary").textContent = `État des flux (${ok}/${meta.sources.length} disponibles)`;
}

/* ---------- Contrôles ---------- */
function setupTheme() {
  const btn = $("#theme-toggle");
  const order = ["auto", "light", "dark"];
  const labels = { auto: "auto", light: "clair", dark: "sombre" };
  let current = document.documentElement.dataset.theme || "auto";
  const apply = () => {
    if (current === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = current;
    btn.textContent = `Thème : ${labels[current]}`;
    try { current === "auto" ? localStorage.removeItem("theme") : localStorage.setItem("theme", current); } catch (e) {}
  };
  btn.addEventListener("click", () => {
    current = order[(order.indexOf(current) + 1) % order.length];
    apply();
    if (state.meta) { drawNetwork(); renderDetail(); renderRanking(); renderMovers(); drawLineChart(); }
  });
  apply();
}

function setupControls() {
  document.querySelectorAll("[data-view]").forEach((btn) => btn.addEventListener("click", () => {
    state.view = btn.dataset.view;
    document.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-selected", b === btn));
    $("#view-network").hidden = state.view !== "network";
    $("#view-trends").hidden = state.view !== "trends";
    $("#window-switch").style.visibility = state.view === "network" ? "visible" : "hidden";
    if (state.view === "network") drawNetwork(); else drawLineChart();
  }));
  document.querySelectorAll("[data-window]").forEach((btn) => btn.addEventListener("click", () => {
    state.window = btn.dataset.window;
    document.querySelectorAll("[data-window]").forEach((b) => b.setAttribute("aria-pressed", b === btn));
    state.selected = null;
    state.focused = false;
    renderNetworkView();
  }));
  $("#compare-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#compare-input");
    const word = matchTerm(input.value);
    if (word) { addCompare(word); input.value = ""; }
    else input.setCustomValidity("Mot absent de l'historique"), input.reportValidity(), input.setCustomValidity("");
  });
}

/* ---------- Vue réseau ---------- */
const graph = () => state.graphs[state.window];

function renderNetworkView() {
  const g = graph();
  if (!state.selected || !g.nodes.some((n) => n.id === state.selected)) state.selected = g.nodes[0]?.id ?? null;
  renderChips();
  renderRanking();
  drawNetwork();
  renderDetail();
}

function renderChips() {
  const present = new Set(graph().nodes.map((n) => n.category));
  const chips = [[null, "Tous les thèmes", null], ...CATEGORIES.filter(([id]) => present.has(id))];
  const box = $("#category-chips");
  box.innerHTML = chips.map(([id, label]) =>
    `<button class="chip" data-cat="${id ?? ""}" aria-pressed="${state.category === id}">${id ? `<span class="dot" style="background:${catColor(id)}"></span>` : ""}${label}</button>`).join("");
  box.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    state.category = b.dataset.cat || null;
    renderChips();
    applyHighlight();
    renderRanking();
  }));
}

function renderRanking() {
  const g = graph();
  const nodes = g.nodes.filter((n) => !state.category || n.category === state.category);
  $("#ranking-caption").textContent =
    `${state.window === "24h" ? "Dernières 24 h" : "7 derniers jours"} · nombre de titres citant le mot, sur ${fmtInt.format(g.articles)} titres`;
  const list = $("#ranking");
  list.innerHTML = nodes.map((n) =>
    `<li><button data-word="${escapeHtml(n.id)}" aria-current="${n.id === state.selected}">
      <span class="dot" style="background:${catColor(n.category)}" title="${CAT[n.category].label}"></span>
      <span>${escapeHtml(n.id)}</span><span class="n">${n.count}</span></button></li>`).join("");
  list.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => select(b.dataset.word, true)));
  let more = $("#ranking-more");
  if (!more) {
    more = document.createElement("button");
    more.id = "ranking-more";
    more.className = "ghost";
    more.type = "button";
    more.style.marginTop = "8px";
    list.after(more);
    more.addEventListener("click", () => { list.classList.toggle("expanded"); renderMoreLabel(); });
  }
  const renderMoreLabel = () => {
    more.textContent = list.classList.contains("expanded") ? "Réduire" : `Voir les ${nodes.length} mots`;
  };
  more.hidden = !isMobile() || nodes.length <= 10;
  renderMoreLabel();
}

function select(word, scroll = false) {
  state.selected = word;
  state.focused = true;
  applyHighlight();
  renderDetail();
  document.querySelectorAll("#ranking button").forEach((b) => b.setAttribute("aria-current", b.dataset.word === word));
  if (scroll && isMobile()) $("#detail").scrollIntoView({ behavior: "smooth", block: "start" });
}

let net = null;   // éléments D3 du réseau courant

function drawNetwork() {
  const container = $("#network");
  if (!container.offsetWidth) return;
  container.innerHTML = "";
  const g = graph();
  const mobile = isMobile();
  const maxNodes = mobile ? 30 : g.nodes.length;
  const nodes = g.nodes.slice(0, maxNodes).map((n) => ({ ...n }));
  const keep = new Set(nodes.map((n) => n.id));
  const links = g.links.filter((l) => keep.has(l.source) && keep.has(l.target)).map((l) => ({ ...l }));
  const width = container.offsetWidth, height = container.offsetHeight;

  const r = d3.scaleSqrt().domain([0, d3.max(nodes, (d) => d.count) || 1]).range([0, isMobile() ? 22 : 30]);
  const maxW = d3.max(links, (d) => d.weight) || 1;
  const w = d3.scaleLinear().domain([1, maxW]).range([1, 6]);

  const svg = d3.select(container).append("svg").attr("viewBox", [0, 0, width, height]);
  const root = svg.append("g");
  const linkSel = root.append("g").selectAll("line").data(links).join("line")
    .attr("class", "link").attr("stroke-width", (d) => w(d.weight)).attr("stroke-opacity", 0.45);
  const nodeSel = root.append("g").selectAll("g").data(nodes, (d) => d.id).join("g").attr("class", "node");
  nodeSel.append("circle").attr("r", (d) => Math.max(4, r(d.count))).attr("fill", (d) => catColor(d.category));
  nodeSel.append("text")
    .text((d) => d.id)
    .attr("text-anchor", "middle")
    .attr("dy", (d) => Math.max(4, r(d.count)) + 13)
    .style("font-size", (d) => `${Math.round(11 + Math.min(5, r(d.count) / 6))}px`);

  const sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((d) => d.id).distance(70).strength((d) => 0.15 + 0.6 * d.weight / maxW))
    .force("charge", d3.forceManyBody().strength(mobile ? -170 : -190))
    .force("collide", d3.forceCollide().radius((d) => Math.max(4, r(d.count)) + 14))
    // Écran étroit et haut : on retient fort en largeur, peu en hauteur.
    .force("x", d3.forceX(width / 2).strength(mobile ? 0.1 : 0.09))
    .force("y", d3.forceY(height / 2).strength(mobile ? 0.05 : 0.12))
    .stop();
  const margin = 24;
  // Demi-largeur approximative de l'étiquette, pour ne pas la couper au bord.
  nodes.forEach((d) => { d.half = Math.max(margin, d.id.length * (11 + Math.min(5, r(d.count) / 6)) * 0.3 + 4); });
  const clamp = () => nodes.forEach((d) => {
    d.x = Math.max(d.half, Math.min(width - d.half, d.x));
    d.y = Math.max(margin, Math.min(height - margin - 14, d.y));
  });
  // Mise en place hors écran (pas de « danse » à l'ouverture), bornée à chaque pas.
  for (let i = 0; i < 260; i++) { sim.tick(); clamp(); }
  const ticked = () => {
    clamp();
    linkSel.attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
    nodeSel.attr("transform", (d) => `translate(${d.x},${d.y})`);
  };
  ticked();
  sim.on("tick", ticked);
  $(".hint").textContent = mobile
    ? "Touchez un mot pour voir ses titres · pincez pour zoomer."
    : "Survolez ou cliquez un mot · molette pour zoomer · glisser pour déplacer.";

  nodeSel
    .on("mousemove", (event, d) => showTooltip(
      `<strong>${escapeHtml(d.id)}</strong><span class="row"><span class="dot" style="background:${catColor(d.category)}"></span>${CAT[d.category].label}</span>
       ${d.count} titres · ${Object.keys(d.sources).length} médias ${trendBadge(d.trend)}`, event))
    .on("mouseleave", hideTooltip)
    .on("click", (event, d) => { event.stopPropagation(); select(d.id); });
  nodeSel.call(d3.drag()
    .on("start", (event, d) => { if (!event.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
    .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; hideTooltip(); })
    .on("end", (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
  svg.call(d3.zoom().scaleExtent([0.5, 4]).on("zoom", (event) => root.attr("transform", event.transform)));
  svg.on("click", () => { state.focused = false; applyHighlight(); });

  const neighbors = new Map(nodes.map((n) => [n.id, new Set([n.id])]));
  links.forEach((l) => { neighbors.get(l.source.id).add(l.target.id); neighbors.get(l.target.id).add(l.source.id); });
  net = { nodeSel, linkSel, neighbors };
  applyHighlight();
}

function applyHighlight() {
  if (!net) return;
  const focus = state.focused ? state.selected : null;
  const near = focus && net.neighbors.get(focus);
  net.nodeSel
    .classed("selected", (d) => d.id === state.selected)
    .classed("dim", (d) => (state.category && d.category !== state.category) || (near && !near.has(d.id)));
  net.linkSel.classed("dim", (d) => (state.category && (d.source.category !== state.category || d.target.category !== state.category))
    || (focus && d.source.id !== focus && d.target.id !== focus));
}

function renderDetail() {
  const box = $("#detail");
  const g = graph();
  const node = g.nodes.find((n) => n.id === state.selected);
  if (!node) { box.innerHTML = `<p class="muted">Cliquez sur un mot pour voir les titres qui le citent.</p>`; return; }
  const sources = Object.entries(node.sources).slice(0, 8);
  const max = sources[0]?.[1] || 1;
  const headlines = g.headlines[node.id] || [];
  const inSeries = state.trends.series[node.id];
  box.innerHTML = `
    <h3>${escapeHtml(node.id)}</h3>
    <div class="meta">
      <span class="row"><span class="dot" style="background:${catColor(node.category)}"></span> ${CAT[node.category].label}</span>
      <span>${node.count} titres · ${state.window === "24h" ? "24 h" : "7 jours"}</span>
      ${trendBadge(node.trend)}
    </div>
    ${inSeries ? `<button class="ghost" id="detail-trend" type="button">Voir l'évolution sur 30 jours</button>` : ""}
    <h4>Médias qui en parlent</h4>
    <ul class="bars">${sources.map(([name, n]) => `
      <li><span class="name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
      <span class="track"><span class="fill" style="width:${(n / max) * 100}%"></span></span><span class="n">${n}</span></li>`).join("")}
    </ul>
    <h4>Titres récents</h4>
    <ul class="headlines">${headlines.map((h) => `
      <li><a href="${escapeHtml(h.link)}" target="_blank" rel="noopener">${escapeHtml(h.title)}</a>
      <span class="src">${escapeHtml(h.source)} · ${relativeTime(h.published)}</span></li>`).join("")}
    </ul>`;
  $("#detail-trend")?.addEventListener("click", () => {
    addCompare(node.id, true);
    document.querySelector('[data-view="trends"]').click();
  });
}

/* ---------- Vue tendances ---------- */
const MIN_DAY_TITLES = 50;   // en dessous (jour de démarrage, panne), la part n'a pas de sens

function shareSeries(word) {
  const { series, totals } = state.trends;
  return (series[word] || []).map((c, i) => (totals[i] >= MIN_DAY_TITLES ? (c / totals[i]) * 100 : null));
}

function matchTerm(text) {
  const q = text.trim().toLowerCase();
  if (!q) return null;
  const terms = Object.keys(state.trends.series);
  return terms.find((t) => t.toLowerCase() === q) || terms.find((t) => t.toLowerCase().startsWith(q)) || null;
}

function renderTrendsView() {
  const t = state.trends;
  const note = $("#history-note");
  if (t.history_days < 7) {
    note.hidden = false;
    note.textContent = t.history_days < 2
      ? "Le radar vient de démarrer : il faut quelques jours d'historique pour repérer les mots en hausse ou en baisse. Les courbes se rempliront au fil des jours."
      : `Historique encore partiel (${t.history_days} jours sur 7) : les tendances sont à prendre avec prudence.`;
  }
  $("#term-list").innerHTML = Object.keys(t.series).map((w) => `<option value="${escapeHtml(w)}">`).join("");
  renderMovers();
  const first = t.rising[0]?.word || state.graphs["24h"].nodes[0]?.id;
  if (first && !state.compare.length) addCompare(first);
}

function renderMovers() {
  const t = state.trends;
  const fill = (el, items, emptyText) => {
    el.innerHTML = items.length ? items.map((m) => `
      <li><button data-word="${escapeHtml(m.word)}">
        <span class="dot" style="background:${catColor(m.category)}" title="${CAT[m.category].label}"></span>
        <span class="word">${escapeHtml(m.word)}<small>${m.recent} titres sur 24 h${m.new ? " · nouveau" : ` · ${fmtPct.format(m.baseline_per_day)}/jour avant`}</small></span>
        ${sparkline(m.word)}
        ${trendBadge(m.score)}
      </button></li>`).join("") : `<li class="empty">${emptyText}</li>`;
    el.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => addCompare(b.dataset.word, true)));
  };
  const waiting = t.history_days ? "Rien de marquant pour l'instant." : "Disponible après quelques jours de collecte.";
  fill($("#rising"), t.rising, waiting);
  fill($("#falling"), t.falling, waiting);
}

function sparkline(word, width = 96, height = 26) {
  const values = shareSeries(word).slice(-14);
  if (!values.length) return "<span></span>";
  const x = d3.scaleLinear().domain([0, values.length - 1]).range([1, width - 1]);
  const y = d3.scaleLinear().domain([0, d3.max(values) || 1]).range([height - 2, 2]);
  const line = d3.line().defined((v) => v != null).x((_, i) => x(i)).y((v) => y(v));
  return `<svg width="${width}" height="${height}" aria-hidden="true"><path class="spark" d="${line(values)}"/></svg>`;
}

function addCompare(word, replaceLast = false) {
  if (!state.trends.series[word]) return;
  if (state.compare.some((c) => c.word === word)) { drawLineChart(); return; }
  if (state.compare.length >= 3) {
    if (!replaceLast) return;
    state.compare.pop();
  }
  const used = new Set(state.compare.map((c) => c.slot));
  const slot = [0, 1, 2].find((s) => !used.has(s));
  state.compare.push({ word, slot });
  drawLineChart();
}

function drawLineChart() {
  const container = $("#line-chart");
  const legend = $("#line-legend");
  legend.innerHTML = state.compare.map((c) => `
    <span class="chip"><span class="dot" style="background:${css(SERIES_TOKENS[c.slot])}"></span>${escapeHtml(c.word)}
    <button type="button" aria-label="Retirer ${escapeHtml(c.word)}" data-word="${escapeHtml(c.word)}">×</button></span>`).join("");
  legend.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    state.compare = state.compare.filter((c) => c.word !== b.dataset.word);
    drawLineChart();
  }));
  if (!container.offsetWidth) return;
  container.innerHTML = "";
  if (!state.compare.length) {
    container.innerHTML = `<p class="empty">Ajoutez un mot pour voir son évolution.</p>`;
    return;
  }

  const days = state.trends.days.map((d) => new Date(`${d}T12:00:00`));
  const lines = state.compare.map((c) => ({ ...c, values: shareSeries(c.word), color: css(SERIES_TOKENS[c.slot]) }));
  const width = container.offsetWidth, height = container.offsetHeight;
  const m = { top: 12, right: isMobile() ? 12 : 110, bottom: 28, left: 44 };
  const x = d3.scaleTime().domain(d3.extent(days)).range([m.left, width - m.right]);
  const ymax = d3.max(lines, (l) => d3.max(l.values)) || 1;
  const y = d3.scaleLinear().domain([0, ymax * 1.1]).nice().range([height - m.bottom, m.top]);

  const svg = d3.select(container).append("svg").attr("viewBox", [0, 0, width, height])
    .attr("role", "img").attr("aria-label", `Part des titres citant ${state.compare.map((c) => c.word).join(", ")} sur 30 jours`);
  svg.append("g").attr("class", "grid").attr("transform", `translate(${m.left},0)`)
    .call(d3.axisLeft(y).ticks(5).tickSize(-(width - m.left - m.right)).tickFormat(""));
  svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - m.bottom})`)
    .call(d3.axisBottom(x).ticks(isMobile() ? 4 : 8).tickFormat(d3.timeFormat("%d/%m")));
  svg.append("g").attr("class", "axis").attr("transform", `translate(${m.left},0)`)
    .call(d3.axisLeft(y).ticks(5).tickFormat((v) => `${fmtPct.format(v)} %`)).call((g) => g.select(".domain").remove());

  const line = d3.line().defined((v) => v != null).x((_, i) => x(days[i])).y((v) => y(v));
  lines.forEach((l) => {
    svg.append("path").attr("class", "series").attr("stroke", l.color).attr("d", line(l.values));
    const last = l.values.map((v, i) => [v, i]).filter(([v]) => v != null).pop();
    if (last && !isMobile()) {
      svg.append("text").attr("class", "end-label").attr("x", x(days[last[1]]) + 8).attr("y", y(last[0]) + 4).text(l.word);
    }
  });

  const cross = svg.append("line").attr("class", "crosshair").attr("y1", m.top).attr("y2", height - m.bottom).style("display", "none");
  const dots = svg.append("g").selectAll("circle").data(lines).join("circle")
    .attr("r", 4).attr("fill", (l) => l.color).attr("stroke", css("--surface")).attr("stroke-width", 2).style("display", "none");
  svg.append("rect").attr("x", m.left).attr("y", m.top).attr("width", width - m.left - m.right)
    .attr("height", height - m.top - m.bottom).attr("fill", "transparent")
    .on("mousemove", (event) => {
      const [px] = d3.pointer(event);
      const i = d3.bisectCenter(days.map((d) => +d), +x.invert(px));
      const cx = x(days[i]);
      cross.attr("x1", cx).attr("x2", cx).style("display", null);
      dots.attr("cx", cx).attr("cy", (l) => (l.values[i] == null ? -99 : y(l.values[i]))).style("display", null);
      const total = state.trends.totals[i];
      showTooltip(`<strong>${days[i].toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "long" })}</strong>
        ${lines.map((l) => `<span class="row"><span class="dot" style="background:${l.color}"></span>${escapeHtml(l.word)} : ${l.values[i] == null ? "—" : `${fmtPct.format(l.values[i])} %`}</span>`).join("")}
        <span class="muted small">${fmtInt.format(total)} titres ce jour-là</span>`, event);
    })
    .on("mouseleave", () => { cross.style("display", "none"); dots.style("display", "none"); hideTooltip(); });
}

init();
