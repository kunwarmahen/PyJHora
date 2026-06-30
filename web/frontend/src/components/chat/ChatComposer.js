import React from "react";
import { Send, Square } from "lucide-react";

/**
 * The shared chat input bar: a text field plus a Send button that becomes a Stop
 * button while a stream is in flight. Enter submits (Shift+Enter inserts a newline
 * in multiline mode). Used by both the Ask Astrologer page and the Transit chat.
 *
 * Props:
 *   value, onChange(value)   controlled input
 *   onSubmit()               fire the question (called on Enter / Send click)
 *   onStop()                 abort the in-flight stream (Stop click)
 *   busy                     true while streaming → shows Stop
 *   placeholder, sendTitle, stopTitle
 *   multiline (default true) textarea vs single-line input
 *   stopLabel                optional text shown next to the Stop icon
 */
export const ChatComposer = ({
  value,
  onChange,
  onSubmit,
  onStop,
  busy = false,
  placeholder,
  sendTitle,
  stopTitle,
  multiline = true,
  stopLabel,
}) => {
  const submit = () => {
    if (!busy && value.trim()) onSubmit();
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form
      className="chat-composer"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      {multiline ? (
        <textarea
          className="chat-input chat-input--multiline"
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          disabled={busy}
        />
      ) : (
        <input
          type="text"
          className="chat-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          disabled={busy}
        />
      )}
      {busy ? (
        <button type="button" className="btn-stop" onClick={onStop} title={stopTitle}>
          <Square size={16} fill="currentColor" />
          {stopLabel && <span>{stopLabel}</span>}
        </button>
      ) : (
        <button type="submit" className="btn-send" disabled={!value.trim()} title={sendTitle}>
          <Send size={20} />
        </button>
      )}
    </form>
  );
};

export default ChatComposer;
