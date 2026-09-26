// The AI activity store (§77): what the header pill and History's "In
// progress" card read. Pinned: counts stay right as items are dismissed, a
// signed-out page never polls, and a failed fetch keeps the last good list.

jest.mock("../services/api", () => ({
  aiActivityService: { list: jest.fn(), markSeen: jest.fn() },
}));

const { aiActivityService } = require("../services/api");
const { refreshAiActivity, markAiActivitySeen, __testing } = require("./useAiActivity");

const items = [
  { id: "a", status: "running", kind: "ask", title: "Career?" },
  { id: "b", status: "done", kind: "reading", title: "Kota Chakra", result_id: "r1" },
  { id: "c", status: "failed", kind: "reading", title: "KP", error: "timeout" },
];

beforeEach(() => {
  __testing.reset();
  jest.clearAllMocks();
  localStorage.setItem("access_token", "t");
  aiActivityService.markSeen.mockResolvedValue({});
});

test("counts running separately from finished (ready, failed, stopped)", () => {
  const s = __testing.recount(items);
  expect(s.running).toBe(1);
  expect(s.ready).toBe(2);
  expect(s.loaded).toBe(true);
});

test("dismissing drops the item and tells the server", async () => {
  aiActivityService.list.mockResolvedValue({ data: { items } });
  await refreshAiActivity();
  await markAiActivitySeen("b");
  expect(aiActivityService.markSeen).toHaveBeenCalledWith("b");
  // A second refresh would re-read the server; the local view is already right.
  aiActivityService.list.mockResolvedValue({ data: { items: items.filter((i) => i.id !== "b") } });
  await refreshAiActivity();
  expect(aiActivityService.list).toHaveBeenCalledTimes(2);
});

test("a signed-out page never asks", async () => {
  localStorage.removeItem("access_token");
  await refreshAiActivity();
  expect(aiActivityService.list).not.toHaveBeenCalled();
});

test("a failed fetch is quiet and doesn't throw", async () => {
  aiActivityService.list.mockRejectedValue(new Error("offline"));
  await expect(refreshAiActivity()).resolves.toBeUndefined();
});

test("concurrent refreshes share one request", async () => {
  let resolve;
  aiActivityService.list.mockReturnValue(
    new Promise((r) => {
      resolve = r;
    })
  );
  const p1 = refreshAiActivity();
  const p2 = refreshAiActivity();
  resolve({ data: { items } });
  await Promise.all([p1, p2]);
  expect(aiActivityService.list).toHaveBeenCalledTimes(1);
});
