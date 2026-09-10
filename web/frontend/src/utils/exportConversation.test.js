/**
 * The PDF export lays out lines, not tables, so model-written GFM has to be
 * flattened to plain text. These cover the constructs that used to survive into
 * the export as punctuation: the pipes of a table and its `| :--- |` alignment
 * row, plus strikethrough.
 */
import { stripMarkdown } from "./exportConversation";

describe("stripMarkdown", () => {
  const TABLE = [
    "| Period | Primary Theme |",
    "| :--- | :--- |",
    "| Sept - Oct 2026 | Transformation |",
  ].join("\n");

  test("drops a table's alignment row", () => {
    expect(stripMarkdown(TABLE)).not.toMatch(/:---/);
  });

  test("keeps a table's cells, without the outer pipes", () => {
    const out = stripMarkdown(TABLE).split("\n");
    expect(out).toEqual(["Period | Primary Theme", "Sept - Oct 2026 | Transformation"]);
  });

  test("strips strikethrough", () => {
    expect(stripMarkdown("~~gone~~ kept")).toBe("gone kept");
  });

  test("leaves an ordinary sentence containing a pipe alone", () => {
    expect(stripMarkdown("Use a | b to pipe")).toBe("Use a | b to pipe");
  });

  test("still handles the pre-existing constructs", () => {
    expect(stripMarkdown("## Heading")).toBe("Heading");
    expect(stripMarkdown("- one\n- two")).toBe("• one\n• two");
    expect(stripMarkdown("**bold** and *italic*")).toBe("bold and italic");
    expect(stripMarkdown("[site](http://x.y)")).toBe("site (http://x.y)");
  });

  test("a task list survives as readable ASCII", () => {
    expect(stripMarkdown("- [x] done\n- [ ] todo")).toBe("• [x] done\n• [ ] todo");
  });
});
