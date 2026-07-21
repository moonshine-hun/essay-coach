import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "./api";
import "./App.css";

const CATEGORIES = [
  { id: "it", label: "💻 IT" },
  { id: "sisa", label: "🌐 시사" },
];

function formatElapsed(sec) {
  const m = String(Math.floor(sec / 60)).padStart(2, "0");
  const s = String(sec % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function HistoryView({ onBack }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const data = await api.history();
      setItems(data.sessions || []);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  async function remove(id) {
    if (!confirm("이 기록을 삭제할까요?")) return;
    await api.historyDelete(id);
    load();
  }

  return (
    <div className="essay-history">
      <div className="essay-history-top">
        <button className="btn-ghost" onClick={onBack}>← 논술로</button>
        <span className="muted">총 {items.length}개</span>
      </div>
      {loading ? (
        <p className="muted">로딩 중…</p>
      ) : items.length === 0 ? (
        <p className="muted">아직 작성한 논술이 없습니다.</p>
      ) : (
        items.map((it) => (
          <div key={it.id} className="card history-item">
            <div className="history-meta">
              <span className="muted">{it.created_at}</span>
              {it.news_source && <span className="tag">{it.news_source}</span>}
              <button className="btn-link-danger" onClick={() => remove(it.id)}>삭제</button>
            </div>
            <div className="history-title">{it.news_title}</div>
            <div className="history-question">{it.question}</div>
            {it.feedback ? (
              <button className="btn-ghost" style={{ marginTop: 8 }}
                onClick={() => setOpenId(openId === it.id ? null : it.id)}>
                {openId === it.id ? "첨삭 접기" : "첨삭 보기"}
              </button>
            ) : (
              <span className="tag" style={{ marginTop: 8 }}>미제출</span>
            )}
            {openId === it.id && (
              <div className="essay-feedback md-note" style={{ marginTop: 10 }}>
                {it.user_answer && (
                  <div className="history-answer">
                    <strong>내 답안</strong>
                    <p>{it.user_answer}</p>
                  </div>
                )}
                <ReactMarkdown>{it.feedback}</ReactMarkdown>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("write");
  const [category, setCategory] = useState("it");
  const [newsList, setNewsList] = useState([]);
  const [loadingNews, setLoadingNews] = useState(false);
  const [selectedNews, setSelectedNews] = useState(null);

  const [session, setSession] = useState(null);
  const [loadingQuestion, setLoadingQuestion] = useState(false);

  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);

  const [error, setError] = useState("");

  async function loadNews(cat) {
    setLoadingNews(true);
    setError("");
    setSelectedNews(null);
    try {
      const data = await api.news(cat, 8);
      setNewsList(data.news || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingNews(false);
    }
  }

  useEffect(() => { loadNews(category); }, [category]);

  useEffect(() => {
    if (session && !feedback) {
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => timerRef.current && clearInterval(timerRef.current);
  }, [session, feedback]);

  async function generateQuestion() {
    if (!selectedNews) return;
    setLoadingQuestion(true);
    setError("");
    setFeedback("");
    setAnswer("");
    setElapsed(0);
    try {
      const data = await api.question({
        news_title: selectedNews.title,
        news_summary: selectedNews.description,
        news_source: selectedNews.source,
        news_url: selectedNews.link,
      });
      setSession(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingQuestion(false);
    }
  }

  async function submitAnswer() {
    if (!session || !answer.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const data = await api.submit(session.id, answer.trim());
      setFeedback(data.feedback);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  function resetAll() {
    setSession(null);
    setSelectedNews(null);
    setAnswer("");
    setFeedback("");
    setElapsed(0);
  }

  if (view === "history") {
    return (
      <div className="app-shell">
        <div className="essay-page">
          <HistoryView onBack={() => setView("write")} />
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="essay-page">
        <div className="card essay-header">
          <div className="essay-header-row">
            <h1 className="section-title">📝 논술 코치</h1>
            <button className="btn-ghost" onClick={() => setView("history")}>📜 작성 기록</button>
          </div>
          <p className="muted" style={{ margin: "0.3rem 0 0" }}>
            IT/시사 뉴스를 스크랩해 논제를 출제하고, 직접 작성한 답안을 AI가 첨삭해줍니다.
          </p>
        </div>

        {error && <p className="error-msg">{error}</p>}

        {!session && (
          <div className="card">
            <div className="essay-cat-row">
              {CATEGORIES.map((c) => (
                <button
                  key={c.id}
                  className={`btn-quick ${category === c.id ? "btn-quick--active" : ""}`}
                  onClick={() => setCategory(c.id)}
                >
                  {c.label}
                </button>
              ))}
              <button className="btn-ghost" onClick={() => loadNews(category)} disabled={loadingNews}>
                🔄 새 뉴스 불러오기
              </button>
            </div>

            {loadingNews ? (
              <div className="spinner" />
            ) : newsList.length === 0 ? (
              <p className="muted">뉴스를 불러오지 못했습니다. 다시 시도해주세요.</p>
            ) : (
              <div className="news-list">
                {newsList.map((n, i) => (
                  <div
                    key={i}
                    className={`news-item ${selectedNews === n ? "news-item--selected" : ""}`}
                    onClick={() => setSelectedNews(n)}
                  >
                    <div className="news-title">{n.title}</div>
                    <div className="news-meta">
                      {n.source && <span className="tag">{n.source}</span>}
                      {n.pub_date && <span className="muted">{n.pub_date}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <button
              className="btn-primary"
              style={{ marginTop: 14 }}
              onClick={generateQuestion}
              disabled={!selectedNews || loadingQuestion}
            >
              {loadingQuestion ? "논제 생성 중…" : "선택한 뉴스로 논제 출제"}
            </button>
          </div>
        )}

        {session && (
          <div className="card essay-question-card">
            <div className="essay-question-top">
              <span className="tag">{selectedNews?.source || "뉴스"}</span>
              <button className="btn-link-danger" onClick={resetAll}>다른 뉴스로 다시 시작</button>
            </div>
            <div className="essay-news-title">{selectedNews?.title}</div>
            <div className="essay-question-box">
              <strong>📝 논제</strong>
              <p>{session.question}</p>
            </div>
            <div className="essay-limits">
              <span className="tag">글자 수 제한 {session.char_limit}자</span>
              <span className="tag">권장 시간 {session.time_limit_min}분</span>
              <span className="tag">⏱ 경과 {formatElapsed(elapsed)}</span>
            </div>

            {!feedback ? (
              <>
                <textarea
                  className="essay-textarea"
                  rows={12}
                  placeholder="답안을 작성하세요…"
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  disabled={submitting}
                />
                <div className="essay-submit-row">
                  <span className={`muted ${answer.length > session.char_limit ? "essay-over" : ""}`}>
                    {answer.length} / {session.char_limit}자
                  </span>
                  <button className="btn-primary" onClick={submitAnswer} disabled={submitting || !answer.trim()}>
                    {submitting ? "첨삭 중…" : "제출하고 첨삭받기"}
                  </button>
                </div>
              </>
            ) : (
              <div className="essay-feedback md-note">
                <ReactMarkdown>{feedback}</ReactMarkdown>
                <button className="btn-ghost" style={{ marginTop: 12 }} onClick={resetAll}>
                  다른 뉴스로 새 논술 쓰기
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
