/**
 * Which saved profiles an API / MCP token may see (Settings → API access).
 *
 * `value` is null for "all profiles, including ones added later" (the default)
 * or an array of profile ids. Two radio choices, and the profile list is always
 * on screen, so it's obvious you can pick one, two or any subset; picking a
 * profile while "All" is on switches to "Only these".
 */
import React from "react";
import { useTranslation } from "react-i18next";

export default function ApiProfileScope({ value, onChange, profiles, name }) {
  const { t } = useTranslation();
  const all = value === null || value === undefined;
  const selected = all ? [] : value;
  const list = profiles || [];

  const toggle = (id, on) => {
    const next = on ? [...new Set([...selected, id])] : selected.filter((x) => x !== id);
    onChange(next);
  };

  return (
    <fieldset className="settings-row settings-row--stack settings-token-scope">
      <legend className="settings-label">{t("settings.apiAccess.scopeLabel")}</legend>
      <label className="settings-check">
        <input type="radio" name={name} checked={all} onChange={() => onChange(null)} />
        <span>{t("settings.apiAccess.scopeAll")}</span>
      </label>
      <label className="settings-check">
        <input
          type="radio"
          name={name}
          checked={!all}
          onChange={() => onChange(selected)}
          disabled={list.length === 0}
        />
        <span>{t("settings.apiAccess.scopeOnly")}</span>
      </label>
      <div className="settings-checklist settings-token-scope__list">
        {list.map((p) => (
          <label key={p._id} className="settings-check">
            <input
              type="checkbox"
              checked={all || selected.includes(p._id)}
              onChange={(e) => {
                if (all) {
                  // From "All": the click starts an explicit list. Unticking one
                  // means "everything currently here except this one".
                  onChange(
                    e.target.checked ? [p._id] : list.map((x) => x._id).filter((id) => id !== p._id)
                  );
                } else {
                  toggle(p._id, e.target.checked);
                }
              }}
            />
            <span>{p.profile_name || p.birth_details?.name}</span>
          </label>
        ))}
        {list.length === 0 && (
          <p className="settings-hint">{t("settings.apiAccess.scopeNoProfiles")}</p>
        )}
      </div>
      {!all && selected.length === 0 && list.length > 0 && (
        <p className="settings-hint">{t("settings.apiAccess.scopePickOne")}</p>
      )}
    </fieldset>
  );
}
