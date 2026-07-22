import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "./api";
import "./App.css";

const CATEGORIES = [
  { id: "it", label: "IT" },
  { id: "sisa", label: "시사" },
];

const COLS = ["A", "B", "C", "D"];
const COL_WIDTHS = { A: 44, B: 520, C: 130, D: 220 };
const HEADERS = { A: "번호", B: "제목", C: "출처", D: "시간" };

function formatElapsed(sec) {
  const m = String(Math.floor(sec / 60)).padStart(2, "0");
  const s = String(sec % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function HistoryPanel() {
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
    <div className="xl-note-wrap">
      <div className="xl-note-header">
        <span className="xl-note-badge">기록</span>
        <span className="xl-note-hint">총 {items.length}개</span>
      </div>
      <div className="xl-note-body" style={{ maxWidth: 900 }}>
        {loading ? (
          <p className="xl-muted">불러오는 중…</p>
        ) : items.length === 0 ? (
          <p className="xl-muted">저장된 항목이 없습니다.</p>
        ) : (
          items.map((it) => (
            <div key={it.id} className="xl-hist-item">
              <div className="xl-hist-meta">
                <span className="xl-muted">{it.created_at}</span>
                {it.news_source && <span className="xl-tag">{it.news_source}</span>}
                <button className="xl-link-danger" onClick={() => remove(it.id)}>삭제</button>
              </div>
              <div className="xl-hist-title">{it.news_title}</div>
              <div className="xl-hist-q">{it.question}</div>
              {it.feedback ? (
                <button className="xl-rb xl-rb-outline" onClick={() => setOpenId(openId === it.id ? null : it.id)}>
                  {openId === it.id ? "첨삭 접기" : "첨삭 보기"}
                </button>
              ) : (
                <span className="xl-tag">미제출</span>
              )}
              {openId === it.id && (
                <div style={{ marginTop: 10 }}>
                  {it.user_answer && (
                    <div className="xl-hist-answer"><strong>내 답안</strong><p>{it.user_answer}</p></div>
                  )}
                  <ReactMarkdown>{it.feedback}</ReactMarkdown>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [sheet, setSheet] = useState("main"); // "main" | "history"
  const [category, setCategory] = useState("it");
  const [newsList, setNewsList] = useState([]);
  const [loadingNews, setLoadingNews] = useState(false);
  const [selectedRow, setSelectedRow] = useState(null);
  const [selectedCell, setSelectedCell] = useState({ row: -1, col: "A" });

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
    setSelectedRow(null);
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
    if (selectedRow === null) return;
    const news = newsList[selectedRow];
    setLoadingQuestion(true);
    setError("");
    setFeedback("");
    setAnswer("");
    setElapsed(0);
    try {
      const data = await api.question({
        news_title: news.title,
        news_summary: news.description,
        news_source: news.source,
        news_url: news.link,
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
    setSelectedRow(null);
    setAnswer("");
    setFeedback("");
    setElapsed(0);
  }

  const selectedNews = selectedRow !== null ? newsList[selectedRow] : null;

  const formulaContent = (() => {
    if (session) return feedback ? "논술 첨삭 결과" : "논술 답안 작성 중…";
    if (selectedCell.row === -1) return HEADERS[selectedCell.col] || "";
    const n = newsList[selectedCell.row];
    if (!n) return "";
    if (selectedCell.col === "A") return String(selectedCell.row + 1);
    if (selectedCell.col === "B") return n.title;
    if (selectedCell.col === "C") return n.source;
    if (selectedCell.col === "D") return n.pub_date;
    return "";
  })();

  return (
    <div className="xl-root">
      <div className="xl-titlebar">
        <div className="xl-title-left">
          <span className="xl-logo">X</span>
          <div className="xl-quick-access"><span>💾</span><span>↩</span><span>↪</span></div>
        </div>
        <span className="xl-filename">채용_현황분석_2026.xlsx — Excel</span>
        <div className="xl-winctrls"><span>─</span><span>□</span><span>✕</span></div>
      </div>

      <div className="xl-ribbon-tabs">
        {["파일", "홈", "삽입", "페이지 레이아웃", "수식", "데이터", "검토", "보기", "도움말"].map((t) => (
          <span key={t} className={`xl-rtab ${t === "홈" ? "active" : ""}`}>{t}</span>
        ))}
      </div>

      <div className="xl-ribbon">
        <div className="xl-rgroup">
          <div className="xl-rgroup-btns">
            <button className="xl-rb">붙여넣기</button>
            <div className="xl-rgroup-mini">
              <button className="xl-rb-sm">잘라내기</button>
              <button className="xl-rb-sm">복사</button>
            </div>
          </div>
          <div className="xl-rgroup-label">클립보드</div>
        </div>
        <div className="xl-rdivider" />
        <div className="xl-rgroup">
          <div className="xl-rgroup-btns">
            <select className="xl-font-sel"><option>맑은 고딕</option></select>
            <select className="xl-size-sel"><option>11</option></select>
            <div className="xl-rgroup-mini">
              <button className="xl-rb-sm"><strong>B</strong></button>
              <button className="xl-rb-sm"><em>I</em></button>
              <button className="xl-rb-sm"><u>U</u></button>
            </div>
          </div>
          <div className="xl-rgroup-label">글꼴</div>
        </div>
        <div className="xl-rdivider" />
        <div className="xl-rgroup">
          <div className="xl-rgroup-btns">
            {!session ? (
              <>
                <div className="xl-rgroup-mini">
                  {CATEGORIES.map((c) => (
                    <button key={c.id}
                      className={`xl-rb-sm ${category === c.id ? "xl-rb-active" : ""}`}
                      onClick={() => setCategory(c.id)}>{c.label}</button>
                  ))}
                </div>
                <button className="xl-rb" onClick={() => loadNews(category)} disabled={loadingNews}>
                  새로고침
                </button>
              </>
            ) : (
              <button className="xl-rb" onClick={resetAll}>다른 항목 선택</button>
            )}
          </div>
          <div className="xl-rgroup-label">데이터</div>
        </div>
        <div className="xl-rdivider" />
        <div className="xl-rgroup">
          <div className="xl-rgroup-btns">
            {!session && (
              <button className="xl-rb xl-submit-btn" onClick={generateQuestion} disabled={selectedRow === null || loadingQuestion}>
                {loadingQuestion ? "분석 중…" : "선택 항목 분석"}
              </button>
            )}
            {session && !feedback && (
              <button className="xl-rb xl-submit-btn" onClick={submitAnswer} disabled={submitting || !answer.trim()}>
                {submitting ? "제출 중…" : "제출"}
              </button>
            )}
            {session && feedback && (
              <button className="xl-rb xl-submit-btn" onClick={resetAll}>새로 시작</button>
            )}
          </div>
          <div className="xl-rgroup-label">작업</div>
        </div>
      </div>

      <div className="xl-formulabar">
        <div className="xl-cellref">
          {session ? "F1" : `${selectedCell.col}${selectedCell.row + 2}`}
        </div>
        <div className="xl-fb-sep" />
        <div className="xl-formula-icons"><span>✕</span><span>✓</span><span>fx</span></div>
        <div className="xl-formula-content">{formulaContent}</div>
      </div>

      {sheet === "history" ? (
        <HistoryPanel />
      ) : !session ? (
        <div className="xl-sheet-wrap">
          <div className="xl-sheet">
            <div className="xl-col-headers">
              <div className="xl-corner" />
              {COLS.map((c) => (
                <div key={c} className={`xl-col-hdr ${selectedCell.col === c ? "selected" : ""}`}
                  style={{ width: COL_WIDTHS[c], minWidth: COL_WIDTHS[c] }}>{c}</div>
              ))}
            </div>
            <div className="xl-rows">
              <div className="xl-row">
                <div className={`xl-row-hdr ${selectedCell.row === -1 ? "selected" : ""}`}>1</div>
                {COLS.map((col) => (
                  <div key={col} className={`xl-cell xl-cell-header ${selectedCell.row === -1 && selectedCell.col === col ? "xl-cell-selected" : ""}`}
                    style={{ width: COL_WIDTHS[col], minWidth: COL_WIDTHS[col] }}
                    onClick={() => setSelectedCell({ row: -1, col })}>
                    {HEADERS[col]}
                  </div>
                ))}
              </div>
              {loadingNews ? (
                <div className="xl-loading-row"><div className="xl-spinner" /></div>
              ) : newsList.length === 0 ? (
                <div className="xl-loading-row xl-muted">데이터를 불러오지 못했습니다.</div>
              ) : (
                newsList.map((n, i) => (
                  <div key={i} className="xl-row"
                    onClick={() => { setSelectedRow(i); setSelectedCell({ row: i, col: "B" }); }}>
                    <div className={`xl-row-hdr ${selectedRow === i ? "selected" : ""}`}>{i + 2}</div>
                    {COLS.map((col) => {
                      let content = "";
                      let cls = "xl-cell";
                      if (col === "A") { content = i + 1; cls += " xl-cell-num"; }
                      if (col === "B") { content = n.title; cls += " xl-cell-stem"; }
                      if (col === "C") { content = n.source; cls += " xl-cell-answer"; }
                      if (col === "D") { content = n.pub_date; cls += " xl-cell-answer"; }
                      if (selectedRow === i) cls += " xl-cell-chosen";
                      const isSel = selectedCell.row === i && selectedCell.col === col;
                      return (
                        <div key={col} className={`${cls} ${isSel ? "xl-cell-selected" : ""}`}
                          style={{ width: COL_WIDTHS[col], minWidth: COL_WIDTHS[col] }}
                          onClick={(e) => { e.stopPropagation(); setSelectedRow(i); setSelectedCell({ row: i, col }); }}>
                          {content}
                        </div>
                      );
                    })}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="xl-note-wrap">
          <div className="xl-note-header">
            <span className="xl-note-badge">{selectedNews?.source || "분석"}</span>
            <span className="xl-note-hint">글자수 {session.char_limit} · 권장 {session.time_limit_min}분 · 경과 {formatElapsed(elapsed)}</span>
          </div>
          <div className="xl-note-body" style={{ maxWidth: 900 }}>
            <p className="xl-source-title">{selectedNews?.title}</p>
            <div className="xl-question-box">
              <strong>분석 항목</strong>
              <p>{session.question}</p>
            </div>

            {!feedback ? (
              <>
                <textarea
                  className="xl-answer-textarea"
                  rows={14}
                  placeholder="내용을 입력하세요…"
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  disabled={submitting}
                />
                <div className="xl-answer-count">
                  <span className={answer.length > session.char_limit ? "xl-over" : "xl-muted"}>
                    {answer.length} / {session.char_limit}자
                  </span>
                </div>
              </>
            ) : (
              <ReactMarkdown>{feedback}</ReactMarkdown>
            )}
          </div>
        </div>
      )}

      {error && <div className="xl-error-bar">{error}</div>}

      <div className="xl-sheet-tabs">
        <span className={`xl-stab ${sheet === "main" ? "xl-stab-active" : ""}`} onClick={() => setSheet("main")}>현황분석</span>
        <span className={`xl-stab ${sheet === "history" ? "xl-stab-active" : ""}`} onClick={() => setSheet("history")}>기록</span>
        <span className="xl-stab xl-stab-add">＋</span>
        <div className="xl-status-bar"><span style={{ marginLeft: "auto" }}>준비  |  100%  |  ─────── +</span></div>
      </div>
    </div>
  );
}
