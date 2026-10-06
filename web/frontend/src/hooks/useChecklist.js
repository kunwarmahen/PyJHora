import { useCallback, useMemo, useRef } from "react";
import { useSettings } from "../contexts/SettingsContext";
import { checklistVisible, parseChecklist, serializeChecklist } from "../config/checklist";

const DISMISSED = "dismissed";

/**
 * The first-week checklist as a hook (§76.4). The rules — items, parsing, when
 * it shows — are pure, in config/checklist.js; this only binds them to the
 * synced `onboardingChecklist` preference.
 */
export const useChecklist = () => {
  const { settings, updateSetting } = useSettings();
  const done = useMemo(
    () => parseChecklist(settings.onboardingChecklist),
    [settings.onboardingChecklist]
  );

  // Read the latest value at call time, not the one this render closed over:
  // pages call `mark` from effects that run once, and a stale list written back
  // would erase what another device (or another tab of this one) just ticked.
  const latest = useRef(settings.onboardingChecklist);
  latest.current = settings.onboardingChecklist;

  const write = useCallback(
    (key) => {
      const next = parseChecklist(latest.current);
      if (next.has(key)) return; // already there — don't churn the synced pref
      next.add(key);
      latest.current = serializeChecklist(next);
      updateSetting("onboardingChecklist", latest.current);
    },
    [updateSetting]
  );

  return {
    done,
    visible: checklistVisible(done),
    mark: write,
    dismiss: () => write(DISMISSED),
  };
};
