// Export an on-screen chart SVG to PNG/PDF. The chart SVGs use CSS custom
// properties (var(--saffron) …) for fills/strokes, which don't resolve once the
// SVG is detached for serialization — so we copy the *computed* paint/text styles
// from the live element onto the clone before rasterizing.

const STYLE_PROPS = [
  "fill",
  "stroke",
  "stroke-width",
  "stroke-linecap",
  "stroke-linejoin",
  "color",
  "stop-color",
  "stop-opacity",
  "opacity",
  "fill-opacity",
  "stroke-opacity",
  "font-size",
  "font-family",
  "font-weight",
  "text-anchor",
  "dominant-baseline",
];

function inlineComputedStyles(src, clone) {
  const cs = window.getComputedStyle(src);
  let style = clone.getAttribute("style") || "";
  STYLE_PROPS.forEach((p) => {
    const v = cs.getPropertyValue(p);
    if (v) style += `${p}:${v};`;
  });
  clone.setAttribute("style", style);
  const sc = src.children;
  const cc = clone.children;
  for (let i = 0; i < sc.length; i++) {
    if (cc[i]) inlineComputedStyles(sc[i], cc[i]);
  }
}

export async function svgToPngBlob(svgEl, scale = 2) {
  const vb = svgEl.viewBox && svgEl.viewBox.baseVal;
  const w = (vb && vb.width) || svgEl.clientWidth || 600;
  const h = (vb && vb.height) || svgEl.clientHeight || 600;

  const clone = svgEl.cloneNode(true);
  inlineComputedStyles(svgEl, clone);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", w);
  clone.setAttribute("height", h);

  const data = new XMLSerializer().serializeToString(clone);
  const url = URL.createObjectURL(new Blob([data], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const img = new Image();
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = reject;
      img.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  } finally {
    URL.revokeObjectURL(url);
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const slug = (s) =>
  (s || "chart")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

// Rasterize a chart to a PNG blob. `el` may be the <svg> itself or a container
// element. SVG charts (North Indian) use the precise serializer; DOM-grid charts
// (South Indian) fall back to html2canvas (loaded on demand).
async function elementToPngBlob(el, scale = 2) {
  if (!el) return null;
  const svg = el.tagName && el.tagName.toLowerCase() === "svg" ? el : el.querySelector("svg");
  if (svg) return svgToPngBlob(svg, scale);
  const { default: html2canvas } = await import("html2canvas");
  const canvas = await html2canvas(el, { backgroundColor: "#ffffff", scale });
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

export async function exportChartPng(el, title = "chart") {
  const blob = await elementToPngBlob(el, 2);
  if (blob) downloadBlob(blob, `${slug(title)}.png`);
}

export async function exportChartPdf(el, title = "chart") {
  const blob = await elementToPngBlob(el, 2);
  if (!blob) return;
  const dataUrl = await new Promise((resolve) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.readAsDataURL(blob);
  });
  // jsPDF is loaded on demand so it stays out of the main bundle.
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ unit: "pt", format: "a4" });
  const pageW = pdf.internal.pageSize.getWidth();
  const margin = 40;
  const imgW = pageW - margin * 2;
  pdf.setFontSize(16);
  pdf.text(title, margin, margin);
  pdf.addImage(dataUrl, "PNG", margin, margin + 16, imgW, imgW); // square chart
  pdf.save(`${slug(title)}.pdf`);
}
