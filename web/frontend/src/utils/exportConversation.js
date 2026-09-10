// Export an AI Astrologer conversation. Markdown is built inline by the page;
// this module renders a paginated PDF with jsPDF (loaded on demand so it stays
// out of the main bundle). Answers are markdown, so we strip the lightweight
// markup to readable plain text before laying it out.

const slug = (s) =>
  (s || "conversation")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

// A GFM table row: pipe-delimited, e.g. `| Period | Theme |`.
const isTableRow = (line) => /^\s*\|.*\|\s*$/.test(line);

// The alignment row directly under a table's header (`| :--- | ---: |`). On
// screen it silently controls column alignment; in plain text it is pure noise,
// so it is dropped rather than rendered as a row of dashes.
const isTableDivider = (line) => /^\s*\|[\s:|-]*\|\s*$/.test(line) && line.includes("-");

/**
 * Flatten GFM tables to one readable line per row.
 *
 * jsPDF lays out lines, not tables, so the cells cannot be drawn as a grid —
 * but the outer pipes and the alignment row can go, which is the difference
 * between a legible row and a wall of punctuation.
 */
function flattenTables(md) {
  return md
    .split("\n")
    .filter((line) => !isTableDivider(line))
    .map((line) =>
      isTableRow(line)
        ? line
            .trim()
            .replace(/^\||\|$/g, "")
            .split("|")
            .map((cell) => cell.trim())
            .join(" | ")
        : line
    )
    .join("\n");
}

// Minimal markdown → plain text: enough for headings, emphasis, lists, links,
// inline code, blockquotes and the GFM constructs (tables, strikethrough, task
// lists) that `components/Markdown.js` renders on screen — an answer that shows
// a dasha timeline as a table must not export as a field of raw pipes.
export function stripMarkdown(md) {
  return (
    flattenTables(md || "")
      .replace(/```[\s\S]*?```/g, (m) => m.replace(/```/g, "").trim()) // fenced code
      .replace(/`([^`]+)`/g, "$1") // inline code
      .replace(/^\s{0,3}#{1,6}\s+/gm, "") // headings
      .replace(/^\s{0,3}>\s?/gm, "") // blockquotes
      // Bullet lists. A GFM task list falls through here as "• [x] …", which is
      // both readable and ASCII — jsPDF's helvetica is WinAnsi-encoded, so ballot
      // glyphs (☐/☑) would export as garbage.
      .replace(/^\s*[-*+]\s+/gm, "• ")
      .replace(/~~([^~]+)~~/g, "$1") // strikethrough
      .replace(/\*\*([^*]+)\*\*/g, "$1") // bold
      .replace(/__([^_]+)__/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1") // italic
      .replace(/_([^_]+)_/g, "$1")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)") // links
      .replace(/\n{3,}/g, "\n\n") // collapse blank runs
      .trim()
  );
}

export async function exportConversationPdf(messages, name, meta = {}) {
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ unit: "pt", format: "a4" });
  const pageW = pdf.internal.pageSize.getWidth();
  const pageH = pdf.internal.pageSize.getHeight();
  const margin = 48;
  const maxW = pageW - margin * 2;
  let y = margin;

  const ensureSpace = (h) => {
    if (y + h > pageH - margin) {
      pdf.addPage();
      y = margin;
    }
  };

  // Render a block of wrapped text in a given font, returning after advancing y.
  const writeBlock = (text, { size = 11, style = "normal", color = [40, 40, 40], gap = 6 }) => {
    pdf.setFont("helvetica", style);
    pdf.setFontSize(size);
    pdf.setTextColor(...color);
    const lineH = size * 1.4;
    const lines = pdf.splitTextToSize(text, maxW);
    lines.forEach((line) => {
      ensureSpace(lineH);
      pdf.text(line, margin, y);
      y += lineH;
    });
    y += gap;
  };

  // Title + meta
  writeBlock(`AI Astrologer — ${name}`, { size: 18, style: "bold", color: [33, 33, 70], gap: 4 });
  const stamp = `Exported ${new Date().toLocaleString()}`;
  writeBlock(stamp, { size: 9, color: [120, 120, 120], gap: 4 });
  if (meta.totalTokens) {
    writeBlock(`Total tokens used: ${meta.totalTokens.toLocaleString()}`, {
      size: 9,
      color: [120, 120, 120],
      gap: 4,
    });
  }
  writeBlock(
    "Astrological guidance for reflection only — not medical, financial, or legal advice.",
    { size: 9, style: "italic", color: [150, 110, 60], gap: 12 }
  );

  messages.forEach((m) => {
    if (m.type === "user") {
      writeBlock(`Q:  ${m.content}`, { size: 12, style: "bold", color: [33, 33, 70], gap: 6 });
    } else if (m.type === "ai" && m.content) {
      const bits = [];
      if (m.model) bits.push(m.model);
      if (m.usage && m.usage.total_tokens) bits.push(`${m.usage.total_tokens} tokens`);
      if (bits.length) {
        writeBlock(`Astrologer · ${bits.join(" · ")}`, {
          size: 8,
          style: "italic",
          color: [150, 150, 150],
          gap: 3,
        });
      }
      writeBlock(stripMarkdown(m.content), { size: 11, color: [40, 40, 40], gap: 14 });
    }
  });

  pdf.save(`astrologer-${slug(name)}.pdf`);
}
