import React from "react";
import ReactMarkdown from "react-markdown";

/**
 * Renders an assistant message body: markdown content, a blinking stream cursor
 * while tokens are still arriving, and a muted "thinking…" placeholder before the
 * first token. Shared by the Ask Astrologer page and the Transit chat so both
 * render streamed answers identically.
 */
export const StreamingMarkdown = ({ content, streaming, thinkingLabel }) => {
  if (!content) {
    return <span className="chat-thinking">{thinkingLabel}</span>;
  }
  return (
    <>
      <ReactMarkdown>{content}</ReactMarkdown>
      {streaming && <span className="stream-cursor">▍</span>}
    </>
  );
};

export default StreamingMarkdown;
