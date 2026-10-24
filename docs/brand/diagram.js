// Small SVG helpers for the diagrams: boxes, cylinders, arrows, ledger rows.
// check() logs any text that spills out of its box (render.cjs prints the log).
const D = (() => {
  const NS = "http://www.w3.org/2000/svg";
  let svg;
  const owned = [];

  function el(tag, attrs = {}, parent = svg) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    parent.appendChild(node);
    return node;
  }

  function text(x, y, str, cls = "b", anchor = "start", parent = svg) {
    const node = el("text", { x, y, class: cls, "text-anchor": anchor }, parent);
    node.textContent = str;
    return node;
  }

  function marker(id, cls) {
    const defs = svg.querySelector("defs");
    const m = el("marker", {
      id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 14, markerHeight: 14,
      markerUnits: "userSpaceOnUse", orient: "auto-start-reverse",
    }, defs);
    el("path", { d: "M0 0L10 5L0 10Z", class: cls }, m);
  }

  function start(width, height, title, subtitle) {
    svg = document.createElementNS(NS, "svg");
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    document.body.appendChild(svg);
    const defs = el("defs");
    const rows = el("pattern", { id: "rows", width, height: 40, patternUnits: "userSpaceOnUse" }, defs);
    el("rect", { class: "rule", y: 39, width, height: 1 }, rows);
    for (const c of ["muted", "accent", "warn", "bar", "text"]) marker(`arrow-${c}`, `head-${c}`);
    el("rect", { class: "bg", width, height });
    el("rect", { width, height, fill: "url(#rows)" });
    el("rect", { class: "margin", x: 40, width: 1, height });
    if (title) text(72, 66, title, "title");
    if (subtitle) text(72, 104, subtitle, "subtitle");
    return svg;
  }

  // lines: strings (body text) or [string, cls] pairs; align "start" or "middle".
  function box(x, y, w, h, opts = {}) {
    const { title, lines = [], cls = "", align = "start", pad = 22, top = 40, gap = 32 } = opts;
    const g = el("g");
    el("rect", { x, y, width: w, height: h, rx: 10, class: `box ${cls}` }, g);
    const tx = align === "middle" ? x + w / 2 : x + pad;
    let ty = y + top;
    const texts = [];
    if (title) {
      texts.push(text(tx, ty, title, opts.titleCls || "h", align, g));
      ty += opts.afterTitle || 34;
    }
    for (const line of lines) {
      const [str, c] = Array.isArray(line) ? line : [line, "b"];
      texts.push(text(tx, ty, str, c, align, g));
      ty += gap;
    }
    const b = { x, y, w, h, cx: x + w / 2, cy: y + h / 2, r: x + w, b: y + h };
    owned.push([b, texts]);
    return b;
  }

  function cyl(x, y, w, h, title, sub) {
    const ry = 16;
    const g = el("g");
    el("path", {
      d: `M${x} ${y + ry}A${w / 2} ${ry} 0 0 0 ${x + w} ${y + ry}V${y + h - ry}A${w / 2} ${ry} 0 0 1 ${x} ${y + h - ry}Z`,
      class: "box store",
    }, g);
    el("ellipse", { cx: x + w / 2, cy: y + ry, rx: w / 2, ry, class: "box store lid" }, g);
    const texts = [text(x + w / 2, y + h / 2 + 18, title, "h", "middle", g)];
    if (sub) texts.push(text(x + w / 2, y + h / 2 + 50, sub, "m", "middle", g));
    const b = { x, y, w, h, cx: x + w / 2, cy: y + h / 2, r: x + w, b: y + h };
    owned.push([b, texts]);
    return b;
  }

  // points: [[x, y], ...]; label: {text, x, y, cls, anchor}; color: muted|accent|warn|bar.
  function arrow(points, opts = {}) {
    const { color = "muted", dashed = false, head = true, label, both = false } = opts;
    const d = points.map((p, i) => `${i ? "L" : "M"}${p[0]} ${p[1]}`).join("");
    const attrs = { d, class: `edge edge-${color}${dashed ? " dashed" : ""}` };
    if (head) attrs["marker-end"] = `url(#arrow-${color})`;
    if (both) attrs["marker-start"] = `url(#arrow-${color})`;
    el("path", attrs);
    if (label) {
      const items = Array.isArray(label) ? label : [label];
      for (const l of items) text(l.x, l.y, l.text, l.cls || "m", l.anchor || "start");
    }
  }

  function check() {
    for (const [b, texts] of owned) {
      for (const t of texts) {
        const r = t.getBBox();
        if (r.x < b.x + 4 || r.x + r.width > b.x + b.w - 4 || r.y < b.y || r.y + r.height > b.y + b.h) {
          console.log(`overflow: "${t.textContent}" (${Math.round(r.x + r.width - b.x - b.w)} px past the right edge)`);
        }
      }
    }
  }

  return { el, text, start, box, cyl, arrow, check };
})();
