import React from "react";
import { StreamingMarkdown } from "./StreamingMarkdown";

/**
 * A single left/right chat bubble. User turns are plain text aligned right; AI
 * turns render streamed markdown (with cursor / thinking placeholder) aligned
 * left, with an optional meta footer (e.g. "answered by <model>"). The AI bubble
 * reuses the `.message-content` markdown styling shared with the Ask page.
 */
export const ChatBubble = ({ role, content, streaming, error, thinkingLabel, meta }) => {
  if (role === "user") {
    return <div className="chat-bubble chat-bubble--user">{content}</div>;
  }
  return (
    <div
      className={`chat-bubble chat-bubble--ai message-content${error ? " chat-bubble--error" : ""}`}
    >
      <StreamingMarkdown content={content} streaming={streaming} thinkingLabel={thinkingLabel} />
      {meta && <div className="chat-bubble__meta">{meta}</div>}
    </div>
  );
};

export default ChatBubble;
