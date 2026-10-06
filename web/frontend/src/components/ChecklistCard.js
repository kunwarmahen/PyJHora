import React from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Circle, X } from "lucide-react";
import { CHECKLIST, isNewcomer } from "../config/checklist";
import { useChecklist } from "../hooks/useChecklist";
import { useAuth } from "../contexts/AuthContext";
import "../styles/ChecklistCard.css";

/**
 * "Your first week" (§76.4) — a dismissable dashboard card in place of a product
 * tour. Hides itself when everything is done or when dismissed; both are synced
 * preferences, so it stays gone on every device. See config/checklist.js for
 * what ticks each item.
 */
export const ChecklistCard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { done, visible, dismiss } = useChecklist();
  if (!visible || !isNewcomer(user?.created_at)) return null;
  const count = CHECKLIST.filter((i) => done.has(i.key)).length;

  return (
    <section className="checklist-card fade-in" aria-labelledby="checklist-title">
      <div className="checklist-card__head">
        <div>
          <h2 id="checklist-title">{t("checklist.title")}</h2>
          <p>{t("checklist.progress", { done: count, total: CHECKLIST.length })}</p>
        </div>
        <button
          type="button"
          className="checklist-card__close"
          onClick={dismiss}
          aria-label={t("checklist.dismiss")}
          title={t("checklist.dismiss")}
        >
          <X size={18} />
        </button>
      </div>
      <ul className="checklist-card__items">
        {CHECKLIST.map(({ key, to }) => {
          const isDone = done.has(key);
          return (
            <li key={key} className={isDone ? "is-done" : undefined}>
              {isDone ? (
                <CheckCircle2 size={18} aria-hidden="true" />
              ) : (
                <Circle size={18} aria-hidden="true" />
              )}
              <Link to={to}>
                {t(`checklist.items.${key}`)}
                <span className="visually-hidden">
                  {" "}
                  — {isDone ? t("checklist.done") : t("checklist.todo")}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
};

export default ChecklistCard;
