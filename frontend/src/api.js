const BASE = (import.meta.env.VITE_API_URL || "") + "/api";

async function req(path, opts = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
  } catch {
    throw new Error("서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    if (res.status === 503) {
      throw new Error(typeof err.detail === "string" ? err.detail : "서버가 일시적으로 사용 불가 상태입니다. 잠시 후 다시 시도해 주세요.");
    }
    const detail = Array.isArray(err.detail)
      ? err.detail.map((e) => e.msg || JSON.stringify(e)).join(", ")
      : (err.detail || `HTTP ${res.status}`);
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  news: (category = "it", count = 8) => req(`/news?category=${category}&count=${count}`),
  question: (news) => req("/question", { method: "POST", body: JSON.stringify(news) }),
  submit: (session_id, answer) =>
    req("/submit", { method: "POST", body: JSON.stringify({ session_id, answer }) }),
  history: () => req("/history"),
  historyDelete: (id) => req(`/history/${id}`, { method: "DELETE" }),
};
