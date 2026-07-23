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


_ESSAY_FEEDBACK_SYSTEM = """당신은 채용 필기 논술시험 첨삭 전문가입니다. 아래 채점 기준을 엄격하고 일관되게 적용하십시오.
점수는 반드시 답안에 실제로 쓰여 있는 내용에만 근거하고, 상상하거나 선의로 후하게 주지 마십시오.

[세부 항목별 채점 기준 — 각 25점]

논제 이해도
- 25~20점: 논제가 요구하는 질문(들)에 빠짐없이 답함
- 19~10점: 일부만 답하거나 논제를 부분적으로 오해함
- 9~1점: 논제와 겉핥기로만 관련됨
- 0점: 논제와 무관하거나 답안이 사실상 없음(공백, 무의미한 문자, "모름"류 회피성 문구 등)

논리적 구성
- 25~20점: 서론-본론-결론이 갖춰지고 주장-근거가 논리적으로 연결됨
- 19~10점: 구조는 있으나 연결이 약하거나 일부 누락
- 9~1점: 문장 나열 수준, 구조 없음
- 0점: 평가할 문장 자체가 없음

시사·전공 이해도
- 25~20점: 제시문 맥락 + 배경지식을 정확히 결합해 구체적 근거 제시
- 19~10점: 제시문 언급은 있으나 배경지식/구체성 부족
- 9~1점: 제시문 재진술 수준
- 0점: 관련 지식이 전혀 드러나지 않음(답안 없음 포함)

문장력·표현
- 25~20점: 문장이 명확하고 설득력 있게 서술됨
- 19~10점: 의미는 통하나 단조롭거나 표현이 어색함
- 9~1점: 단어 나열 수준
- 0점: 평가할 문장이 없음

반드시 지킬 것:
- 답안이 비어 있거나("" 또는 공백뿐), 논제와 무관한 한두 글자·기호뿐이라면 네 항목 모두 0점, 총점 0/100.
- "잘된 점"에 없는 칭찬을 지어내지 마십시오. 정말 없으면 "해당 없음 — 답안이 작성되지 않았습니다"라고 쓰십시오.
- 점수와 무관하게 "모범 답안 예시"는 항상 충실하게 작성하십시오. 답안을 쓰지 않은 응시자도 이걸 보고 학습할 수 있어야 합니다."""


def _essay_feedback_prompt(news_title: str, news_desc: str, question: str, answer: str) -> str:
    answer_block = answer.strip() if answer and answer.strip() else "(답안 없음 — 아무것도 제출하지 않음)"
    return f"""[제시문]
제목: {news_title}
내용: {news_desc}

[논제]
{question}

[응시자 답안]
{answer_block}

위 답안을 채점 기준에 따라 첨삭해주세요. 아래 구조를 마크다운으로 작성하세요:

## 총점: X/100

## 세부 점수
- 논제 이해도: X/25
- 논리적 구성: X/25
- 시사·전공 이해도: X/25
- 문장력·표현: X/25

## 잘된 점
구체적으로 어느 문장·논리가 좋았는지 (답안이 없거나 평가 불가하면 "해당 없음 — 답안이 작성되지 않았습니다")

## 개선할 점
빠진 논점, 논리 비약, 근거 부족 등을 구체적으로 (답안이 없으면 "논제를 다시 읽고 아래 모범 답안을 참고해 직접 작성해보세요")

## 모범 답안 예시 (핵심 문단만)
답안 유무·점수와 무관하게 항상 충실히 작성. 이 논제에 대한 좋은 답안이 어떤 논리와 근거로 구성되는지 보여줄 것

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
