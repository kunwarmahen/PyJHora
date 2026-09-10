import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "../styles/Markdown.css";

/**
 * The one place the app turns model output into HTML.
 *
 * Plain `react-markdown` speaks CommonMark only, which has no tables — so an
 * answer that laid out a dasha timeline as a table used to land on the page as
 * raw `| Period | Theme |` pipes. `remark-gfm` adds the GitHub extensions the
 * models actually write: tables, strikethrough, task lists and bare autolinks.
 *
 * Tables are wrapped in their own scroll container because a six-column
 * timeline must never widen the page on a phone.
 *
 * The output is wrapped in `.md`, which owns the reading typography (see
 * `styles/Markdown.css`) — one rhythm for chat turns, page panels and saved
 * readings alike. The wrapper also earns its keep by resetting `white-space`:
 * chat bubbles are `pre-wrap` so plain-text turns keep their line breaks, and
 * inherited into markdown that turned the newline between every block into a
 * literal blank line, leaving cavernous, uneven gaps down the whole answer.
 *
 * Import this instead of `react-markdown` anywhere AI prose is displayed, so a
 * fix here reaches every reading, chat turn and panel at once.
 */
const components = {
  table: ({ node, ...props }) => (
    <div className="md-table-wrap">
      <table className="md-table" {...props} />
    </div>
  ),
};

export const Markdown = ({ children }) => (
  <div className="md">
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  </div>
);

export default Markdown;
