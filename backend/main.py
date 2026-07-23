import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

_gemini_sem = asyncio.Semaphore(1)  # Gemini RPM 제한 방어

from db import get_db, init_db
from ai import AI_ENABLED, generate_essay_question, grade_essay
from news import fetch_news

_AI_DAILY_LIMIT = 18  # Gemini free tier 20 RPD, 여유 2개 확보


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Essay Coach API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _get_today_ai_count(db) -> int:
    cur = await db.execute(
        "SELECT COUNT(*) AS cnt FROM ai_call_log WHERE DATE(called_at)=DATE('now','localtime')"
    )
    row = await cur.fetchone()
    return row["cnt"] if row else 0


async def _inc_ai_count(db):
    await db.execute("INSERT INTO ai_call_log (called_at) VALUES (datetime('now','localtime'))")
    await db.commit()


@app.get("/api/health")
async def health():
    return {"status": "ok", "ai_enabled": AI_ENABLED}


@app.get("/api/ai-quota")
async def get_ai_quota():
    db = await get_db()
    try:
        used = await _get_today_ai_count(db)
        return {"used": used, "limit": _AI_DAILY_LIMIT, "remaining": max(0, _AI_DAILY_LIMIT - used)}
    finally:
        await db.close()


@app.get("/api/news")
async def news(
    category: str = Query("it", pattern="^(it|sisa)$"),
    count: int = Query(8, ge=1, le=20),
):
    items = fetch_news(category, count)
    return {"news": items}


class QuestionRequest(BaseModel):
    news_title: str
    news_summary: str = ""
    news_source: str = ""
    news_url: str = ""


@app.post("/api/question")
async def question(req: QuestionRequest):
    if not AI_ENABLED:
        raise HTTPException(503, "AI가 비활성화 상태입니다.")
    if not req.news_title.strip():
        raise HTTPException(400, "뉴스를 선택해주세요.")
    db = await get_db()
    try:
        used = await _get_today_ai_count(db)
        if used >= _AI_DAILY_LIMIT:
            raise HTTPException(503, f"오늘 AI 한도({_AI_DAILY_LIMIT}회)를 모두 사용했습니다.")

        try:
            async with _gemini_sem:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, generate_essay_question, req.news_title, req.news_summary
                )
        except Exception as e:
            raise HTTPException(503, f"논제 생성 실패: {e}")
        await _inc_ai_count(db)

        cur = await db.execute(
            """INSERT INTO essay_sessions
               (news_title, news_summary, news_source, news_url, question, char_limit, time_limit_min)
               VALUES (?,?,?,?,?,?,?)""",
            (
                req.news_title.strip(), req.news_summary.strip(),
                req.news_source.strip(), req.news_url.strip(),
                result.get("question", ""), result.get("char_limit", 800), result.get("time_limit_min", 40),
            ),
        )
        await db.commit()
        return {
            "id": cur.lastrowid,
            "question": result.get("question", ""),
            "char_limit": result.get("char_limit", 800),
            "time_limit_min": result.get("time_limit_min", 40),
        }
    finally:
        await db.close()


class SubmitRequest(BaseModel):
    session_id: int
    answer: str


_MIN_ANSWER_LEN = 50


@app.post("/api/submit")
async def submit(req: SubmitRequest):
    if not AI_ENABLED:
        raise HTTPException(503, "AI가 비활성화 상태입니다.")
    answer = req.answer.strip()
    if not answer:
        raise HTTPException(400, "답안을 작성해주세요.")
    if len(answer) < _MIN_ANSWER_LEN:
        raise HTTPException(400, f"답안이 너무 짧습니다. 최소 {_MIN_ANSWER_LEN}자 이상 작성해주세요. (현재 {len(answer)}자)")
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM essay_sessions WHERE id=?", (req.session_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "세션을 찾을 수 없습니다.")
        sess = dict(row)

        used = await _get_today_ai_count(db)
        if used >= _AI_DAILY_LIMIT:
            raise HTTPException(503, f"오늘 AI 한도({_AI_DAILY_LIMIT}회)를 모두 사용했습니다.")

        try:
            async with _gemini_sem:
                feedback = await asyncio.get_event_loop().run_in_executor(
                    None, grade_essay, sess["news_title"], sess["news_summary"], sess["question"], answer
                )
        except Exception as e:
            raise HTTPException(503, f"첨삭 실패: {e}")
        await _inc_ai_count(db)

        await db.execute(
            "UPDATE essay_sessions SET user_answer=?, feedback=?, submitted_at=datetime('now') WHERE id=?",
            (answer, feedback, req.session_id),
        )
        await db.commit()
        return {"feedback": feedback}
    finally:
        await db.close()


@app.get("/api/history")
async def history():
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM essay_sessions ORDER BY id DESC LIMIT 100")
        rows = await cur.fetchall()
        return {"sessions": [dict(r) for r in rows]}
    finally:
        await db.close()


@app.delete("/api/history/{item_id}")
async def history_delete(item_id: int):
    db = await get_db()
    try:
        await db.execute("DELETE FROM essay_sessions WHERE id=?", (item_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()
