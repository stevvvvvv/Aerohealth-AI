const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
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
