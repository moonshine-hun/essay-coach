import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
_GEMINI_KEY    = os.environ.get("GEMINI_API_KEY", "").strip()

_USE_ANTHROPIC = bool(_ANTHROPIC_KEY and not _ANTHROPIC_KEY.startswith("sk-ant-여기에"))
_USE_GEMINI    = bool(_GEMINI_KEY and not _GEMINI_KEY.startswith("여기에"))
AI_ENABLED     = _USE_ANTHROPIC or _USE_GEMINI

if _USE_ANTHROPIC:
    import anthropic
    _anthropic_client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)

if _USE_GEMINI:
    from google import genai as _genai
    _gemini_client = _genai.Client(api_key=_GEMINI_KEY)
    _GEMINI_MODEL = "gemini-2.5-flash-lite"

_last_gemini_call = 0.0
_GEMINI_MIN_INTERVAL = 4.2  # 15 RPM = 4s/req, 여유 0.2s


def _gemini_call(model: str, **kwargs) -> object:
    """RPM 초과 방지: 호출 간 최소 4.2초 보장 + 429 시 자동 재시도"""
    global _last_gemini_call
    elapsed = time.time() - _last_gemini_call
    if elapsed < _GEMINI_MIN_INTERVAL:
        time.sleep(_GEMINI_MIN_INTERVAL - elapsed)

    for attempt in range(3):
        try:
            _last_gemini_call = time.time()
            return _gemini_client.models.generate_content(model=model, **kwargs)
        except Exception as e:
            err = str(e)
            is_429 = "429" in err or "RESOURCE_EXHAUSTED" in err
            is_503 = "503" in err or "UNAVAILABLE" in err
            if is_503:
                raise
            if is_429 and attempt < 2:
                time.sleep(60 * (attempt + 1))
            else:
                raise


def _parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


_ESSAY_Q_SYSTEM = """당신은 중견/중소기업 및 공기업 채용 필기시험의 IT/시사 논술 출제위원입니다.
실제 논술시험처럼 제시문을 바탕으로 명확한 논제를 만드십시오. 요청받은 JSON 형식만 출력하고 preamble, 설명, 마크다운 백틱은 절대 넣지 마십시오."""


def _essay_question_prompt(title: str, desc: str) -> str:
    return f"""아래는 최근 IT/시사 뉴스입니다.

제목: {title}
내용: {desc}

이 뉴스를 제시문으로 삼아, 실제 중견기업·공기업 채용 필기 논술시험에 나올 법한 논제를 출제하세요.

아래 JSON 스키마를 정확히 따라 출력하십시오:
{{
  "question": "논제 (제시문 요약 + 구체적 논술 요구사항, 2~4문장)",
  "char_limit": 800,
  "time_limit_min": 40
}}

규칙:
- 단순 요약이 아니라 지원자의 견해·분석·대안을 요구하는 논제로 작성
- char_limit은 600~1200 사이에서 논제 난이도에 맞게 설정
- time_limit_min은 30~50 사이"""


def generate_essay_question(title: str, desc: str) -> dict:
    if not AI_ENABLED:
        raise RuntimeError("API 키 미설정")

    prompt = _essay_question_prompt(title, desc)

    if _USE_ANTHROPIC:
        try:
            msg = _anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_ESSAY_Q_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            return _parse(msg.content[0].text)
        except Exception:
            pass  # Gemini로 폴백

    try:
        resp = _gemini_call(model=_GEMINI_MODEL, contents=_ESSAY_Q_SYSTEM + "\n\n" + prompt)
        return _parse(resp.text)
    except Exception as e:
        raise RuntimeError(f"논제 생성 실패: {e}") from e


_ESSAY_FEEDBACK_SYSTEM = """당신은 채용 필기 논술시험 첨삭 전문가입니다. 공정하고 구체적인 근거를 들어 첨삭하십시오.
답안이 논제와 무관하거나, 실질적인 주장·근거 없이 단어만 나열하거나, 성의 없이 짧게 때우려 한 경우
절대 좋게 포장하지 말고 낮은 점수(총점 20점 미만)를 주고 그 이유를 명확히 지적하십시오."""


def _essay_feedback_prompt(news_title: str, news_desc: str, question: str, answer: str) -> str:
    return f"""[제시문]
제목: {news_title}
내용: {news_desc}

[논제]
{question}

[응시자 답안]
{answer}

위 답안을 실제 채용 논술시험 채점 기준으로 첨삭해주세요. 아래 구조를 마크다운으로 작성하세요:

먼저 답안이 논제에 실질적으로 답하고 있는지 판단하세요. 논제와 무관하거나 내용이 거의 없다면
"## 총점"을 20점 미만으로 매기고, "잘된 점"에 억지로 칭찬거리를 만들어내지 마세요
(정말 없으면 "특별히 평가할 내용이 없습니다"라고 쓰세요).

## 총점: X/100

## 세부 점수
- 논제 이해도: X/25
- 논리적 구성: X/25
- 시사·전공 이해도: X/25
- 문장력·표현: X/25

## 잘된 점
구체적으로 어느 문장·논리가 좋았는지

## 개선할 점
빠진 논점, 논리 비약, 근거 부족 등을 구체적으로

## 모범 답안 예시 (핵심 문단만)
답안의 핵심 주장을 어떻게 더 설득력 있게 쓸 수 있는지 예시 문단

## 총평
2~3문장 요약 피드백"""


def grade_essay(news_title: str, news_desc: str, question: str, answer: str) -> str:
    if not AI_ENABLED:
        raise RuntimeError("API 키 미설정")

    prompt = _essay_feedback_prompt(news_title, news_desc, question, answer)

    if _USE_ANTHROPIC:
        try:
            msg = _anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=_ESSAY_FEEDBACK_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except Exception:
            pass  # Gemini로 폴백

    try:
        resp = _gemini_call(model=_GEMINI_MODEL, contents=_ESSAY_FEEDBACK_SYSTEM + "\n\n" + prompt)
        return resp.text
    except Exception as e:
        raise RuntimeError(f"첨삭 실패: {e}") from e
