/**
 * The API-token profile picker lists every profile up front, so a user can see
 * they may pick one, two or any subset — not just all-or-nothing.
 */
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react-dom/test-utils";
import "../i18n";
import ApiProfileScope from "./ApiProfileScope";

const PROFILES = [
  { _id: "a", profile_name: "Asha" },
  { _id: "b", profile_name: "Bina" },
  { _id: "c", profile_name: "Chetan" },
];

function mount(value, onChange) {
  const el = document.createElement("div");
  document.body.appendChild(el);
  act(() => {
    createRoot(el).render(
      <ApiProfileScope name="t" value={value} onChange={onChange} profiles={PROFILES} />
    );
  });
  return el;
}

const boxes = (el) => [...el.querySelectorAll('input[type="checkbox"]')];

test("every profile is listed even while 'All' is chosen (the default)", () => {
  const el = mount(null, () => {});
  expect(el.textContent).toContain("Asha");
  expect(el.textContent).toContain("Chetan");
  expect(boxes(el).every((b) => b.checked)).toBe(true);
  expect(el.querySelectorAll('input[type="radio"]')[0].checked).toBe(true);
});

test("ticking one profile while on 'All' narrows to just that one", () => {
  const onChange = jest.fn();
  const el = mount(null, onChange);
  // From All every box is ticked; unticking Bina keeps the other two.
  act(() => boxes(el)[1].click());
  expect(onChange).toHaveBeenLastCalledWith(["a", "c"]);
});

test("a chosen subset can grow and shrink one profile at a time", () => {
  const onChange = jest.fn();
  const el = mount(["a"], onChange);
  expect(boxes(el).map((b) => b.checked)).toEqual([true, false, false]);
  act(() => boxes(el)[2].click());
  expect(onChange).toHaveBeenLastCalledWith(["a", "c"]);
});

test("choosing 'All' again goes back to all-including-future (null)", () => {
  const onChange = jest.fn();
  const el = mount(["a"], onChange);
  act(() => el.querySelectorAll('input[type="radio"]')[0].click());
  expect(onChange).toHaveBeenLastCalledWith(null);
});
