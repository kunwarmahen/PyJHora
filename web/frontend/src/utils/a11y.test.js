/**
 * §68.8 — the keyboard contract for controls that cannot be a <button>.
 */
import { clickable } from "./a11y";

it("gives a non-button the whole button contract", () => {
  const onActivate = jest.fn();
  const props = clickable(onActivate, { label: "Open reading" });
  expect(props.role).toBe("button");
  expect(props.tabIndex).toBe(0);
  expect(props["aria-label"]).toBe("Open reading");
});

it.each(["Enter", " ", "Spacebar"])("activates on %s", (key) => {
  const onActivate = jest.fn();
  const preventDefault = jest.fn();
  clickable(onActivate).onKeyDown({ key, preventDefault });
  expect(onActivate).toHaveBeenCalledTimes(1);
  // Space would otherwise scroll the page out from under the user.
  expect(preventDefault).toHaveBeenCalled();
});

it("ignores other keys", () => {
  const onActivate = jest.fn();
  clickable(onActivate).onKeyDown({ key: "a", preventDefault: () => {} });
  expect(onActivate).not.toHaveBeenCalled();
});

it("adds nothing at all when there is no handler", () => {
  // A row that isn't expandable must not advertise itself as a control.
  expect(clickable(null)).toEqual({});
  expect(clickable(() => {}, { disabled: true })).toEqual({});
});

it("reports expanded state when it has one", () => {
  expect(clickable(() => {}, { expanded: false })["aria-expanded"]).toBe(false);
  expect(clickable(() => {})["aria-expanded"]).toBeUndefined();
});
