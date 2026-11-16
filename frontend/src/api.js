// Two modes:
//  * live   (default)       -> FastAPI backend under /api
//  * static (VITE_STATIC=1) -> precomputed JSON under ./data (GitHub Pages demo)
export const STATIC = import.meta.env.VITE_STATIC === "1";
const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

const live = {
  fleet: () => request("/fleet"),
  model: () => request("/model"),
  sensors: () => request("/sensors"),
  engine: (id) => request(`/engines/${id}`),
  predictions: (id) => request(`/engines/${id}/predictions`),
  sensorSeries: (id, list) => request(`/engines/${id}/sensors?sensors=${list.join(",")}`),
  explain: (id, cycle) => request(`/engines/${id}/explain${cycle ? `?cycle=${cycle}` : ""}`),
  alerts: (params = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null));
    return request(`/alerts?${q}`);
  },
  ack: (id) => request(`/alerts/${id}/ack`, { method: "PATCH" }),
};

// ---------------------------------------------------------------------------
const cache = new Map();
function json(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(`${import.meta.env.BASE_URL}data/${path}`).then((r) => {
      if (!r.ok) throw new Error(`${r.status} data/${path}`);
      return r.json();
    }));
  }
  return cache.get(path);
}
const acked = new Set(); // acknowledgements live in the visitor's browser only

const withAck = (a) => (acked.has(a.id) ? { ...a, acknowledged: true } : a);

const staticApi = {
  fleet: async () => {
    const f = await json("fleet.json");
    const open = {};
    (await json("alerts.json")).forEach((a) => {
      if (!a.acknowledged && !acked.has(a.id)) open[a.engine_id] = (open[a.engine_id] || 0) + 1;
    });
    return { ...f, engines: f.engines.map((e) => ({ ...e, open_alerts: open[e.id] || 0 })) };
  },
  model: () => json("model.json"),
  sensors: () => json("sensors.json"),
  engine: (id) => json(`engines/${id}/detail.json`),
  predictions: (id) => json(`engines/${id}/predictions.json`),
  sensorSeries: async (id, list) => {
    const s = await json(`engines/${id}/sensors.json`);
    return { cycles: s.cycles, series: Object.fromEntries(list.map((k) => [k, s.series[k]])) };
  },
  explain: async (id, cycle) => {
    const cycles = await json(`engines/${id}/explain/index.json`);
    const target = cycle ?? cycles[cycles.length - 1];
    const nearest = cycles.reduce((a, b) => (Math.abs(b - target) < Math.abs(a - target) ? b : a));
    return json(`engines/${id}/explain/${nearest}.json`);
  },
  alerts: async ({ engine_id, level, kind, open_only, limit } = {}) => {
    let a = (await json("alerts.json")).map(withAck);
    if (engine_id) a = a.filter((x) => String(x.engine_id) === String(engine_id));
    if (level) a = a.filter((x) => x.level === level.toUpperCase());
    if (kind) a = a.filter((x) => x.kind === kind.toUpperCase());
    if (open_only) a = a.filter((x) => !x.acknowledged);
    return a.slice(0, limit || 200);
  },
  ack: async (id) => {
    acked.add(id);
    return withAck((await json("alerts.json")).find((x) => x.id === id));
  },
};

export const api = STATIC ? staticApi : live;
