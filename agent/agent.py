import logging
import json
import re
import time
import datetime
import os
import aiohttp
import asyncio
from agent.agent_tools import perplexity_deep_research_tool
from agent.cost_calculator import PerplexityCostCalculator
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.tools.google_search_tool import google_search
from google.adk import Runner
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from a2a.types import (
    AgentCard,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
    TaskStatus,
    TaskState,
)
from a2a.utils import new_text_artifact
from datetime import datetime

from prompts.prompt import get_system_instruction

logger = logging.getLogger(__name__)
MAX_RETRY = 1


def extract_json_from_llm_output(text):
    """
    LLM 응답에서 ```json ... ``` 코드블록이 감싸져 있으면 내부만 추출해서 반환.
    코드블록이 없으면 그대로 반환.
    """
    # 연속 중괄호("{" 또는 "}")가 2개 이상 이어지면 1개로 축소 (예: {{{foo}}} -> {foo})
    text = re.sub(r"\{\{+", "{", text)
    text = re.sub(r"\}\}+", "}", text)
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        return match.group(1)
    return text


class DeepSearchAgent:
    """단일 날짜 일일 작업 조회 전담 서브 에이전트"""

    def __init__(self, app_name: str = "default-app"):
        self.app_name = app_name
        # .env 파일 로드
        load_dotenv()

        # LlmAgent 와 Runner 는 비동기적으로 초기화되어야 하지만, __init__ 는 동기 함수이므로
        # 여기서는 바로 생성하지 않고 지연 초기화(lazy initialization) 방식으로 보관합니다.
        # 실제 invoke 시점에 필요한 이벤트 루프 안에서 생성하도록 합니다.
        self.agent: LlmAgent | None = None
        self.runner = Runner(
            app_name=app_name,
            agent=self.agent,
            session_service=InMemorySessionService(),
        )

    # ------------------------------------------------------------------
    async def _refresh_agent(self):
        """Refresh prompt and connectors; rebuild LlmAgent if needed"""
        rebuilt = False
        instruction = None

        logger.info(f"[DeepSearchAgent] _refresh_agent 실행, app_name: {self.app_name}")
        # 1. Prompt update - 외부 함수 사용 (fallback 포함)
        try:
            instruction = await get_system_instruction(self.app_name)
            # if instruction is None:
            #     print("[GeocodeAgent] 외부 프롬프트 함수가 None을 반환, 내부 프롬프트 사용")
            #     instruction = self._build_instruction()
        except Exception as e:
            print(f"[DeepSearchAgent] 외부 프롬프트 함수 실패: {e}, 내부 프롬프트 사용")
            # instruction = self._build_instruction()

        if self.agent is None or instruction != self.agent.instruction:
            rebuilt = True

        # 3. Rebuild if needed
        if rebuilt:
            print("[DeepSearchAgent] Rebuilding LlmAgent due to update")
            self.agent = await self._build_agent()
            if self.runner:
                self.runner.agent = self.agent  # replace in existing runner

    async def _build_agent(self) -> LlmAgent:
        # 외부 프롬프트 함수 실패 시 fallback
        instruction = None
        try:
            instruction = await get_system_instruction(self.app_name)
            # if instruction is None:
            #     instruction = self._build_instruction()
        except Exception as e:
            print(f"[DeepSearchAgent] 외부 프롬프트 함수 실패: {e}, 내부 프롬프트 사용")
            # instruction = self._build_instruction()

        agent = LlmAgent(
            model="gemini-2.5-flash",
            name="deep_search_agent",
            description="딥 서치 에이전트",
            instruction=instruction,
            tools=[perplexity_deep_research_tool],
        )
        return agent

    async def invoke(
        self,
        query: str,
        session_id: str,
        task_id: str,
        user_id: str,
        app_name: str = "default-app",
    ):
        """서브 에이전트 실행"""
        logger.info(
            "[DeepSearchAgent] invoke 시작 | query=%s, session_id=%s, task_id=%s, user_id=%s",
            query,
            session_id,
            task_id,
            user_id,
        )

        # 최신 정보 반영
        await self._refresh_agent()

        if self.runner is None:
            self.runner = Runner(
                app_name=app_name,
                agent=self.agent,
                session_service=InMemorySessionService(),
            )

        # 사용료 계산기 초기화
        cost_calculator = PerplexityCostCalculator("sonar-deep-research")
        total_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "citation_tokens": 0,
            "search_queries": 0,
            "reasoning_tokens": 0,
        }

        try:
            # 세션 처리
            session = await self.runner.session_service.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
            )
            if session is None:
                session = await self.runner.session_service.create_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    state={},
                )

            # 오늘 날짜 정보 추가
            today_str = datetime.now().strftime("%Y-%m-%d")
            augmented_query = f"(시스템 정보) 오늘 날짜는 {today_str} 입니다.\n{query}"
            content = types.Content(
                role="user", parts=[types.Part.from_text(text=augmented_query)]
            )

            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
                run_config=RunConfig(max_llm_calls=20),
            ):

                event_dict = event.dict()

                # 사용료 정보 추출 및 누적
                if "usage" in event_dict:
                    usage = event_dict["usage"]
                    for key in total_usage:
                        if key in usage:
                            total_usage[key] += usage[key]
                    logger.info(f"Usage accumulated: {total_usage}")

                # 함수 응답 처리 (Google ADK의 자동 함수 호출 결과)
                # if 'function_responses' in event_dict and event_dict['function_responses']:
                #     for response in event_dict['function_responses']:
                #         print(f"Function response: {response}")  # Debug print
                #         if 'response' in response:
                #             yield json.dumps(response['response'], ensure_ascii=False)
                #             return

                # 모든 text 부분을 하나로 합치기
                text = ""
                if "content" in event_dict and "parts" in event_dict["content"]:
                    for part in event_dict["content"]["parts"]:
                        if "text" in part and part["text"] is not None:
                            text += part["text"]

                # 텍스트가 있으면 처리
                if text.strip():
                    # 1. JSON 형식인지 먼저 시도
                    json_str = extract_json_from_llm_output(text)
                    logger.info(f"Deep Search Agent 응답: {json_str}")
                    try:
                        data = json.loads(json_str)
                        answer = data.get("answer", json_str)
                        # answer가 딕셔너리인 경우 JSON 문자열로 변환
                        if isinstance(answer, dict):
                            answer = json.dumps(answer, ensure_ascii=False)

                        # 사용료 계산 및 추가
                        cost_info = cost_calculator.calculate_cost(total_usage)
                        cost_summary = cost_calculator.format_cost_summary(cost_info)

                        # 응답에 사용료 정보 추가
                        final_response = {
                            "answer": answer,
                            "cost_info": cost_info,
                            "cost_summary": cost_summary,
                        }

                        yield json.dumps(final_response, ensure_ascii=False)
                        break
                    except json.JSONDecodeError:
                        # 2. 일반 텍스트로 처리
                        if len(text.strip()) > 10:
                            # 사용료 계산 및 추가
                            cost_info = cost_calculator.calculate_cost(total_usage)
                            cost_summary = cost_calculator.format_cost_summary(
                                cost_info
                            )

                            # 응답에 사용료 정보 추가
                            final_response = {
                                "answer": text.strip(),
                                "cost_info": cost_info,
                                "cost_summary": cost_summary,
                            }

                            yield json.dumps(final_response, ensure_ascii=False)
                            break

                yield event
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("[DeepSearchAgent] invoke 예외: %s", exc)
            raise


#     @staticmethod
#     def _build_instruction() -> str:
#         return (
#             """
# # Amadeus API 액세스 토큰 획득 에이전트 시스템 인스트럭션

# ## Amadeus API 토큰 획득 조건(get_geocode_tool)
# - 사용자가 어떤 키워드를 입력하든 상관없이, 무조건 get_geocode_tool 함수를 호출하세요.
# - 이 함수는 Amadeus API의 OAuth2 액세스 토큰을 획득하는 역할을 합니다.
# - 절대 추가 질문이나 안내문을 생성하지 마세요.
# - Never generate any prompt or question. Just call get_geocode_tool function immediately.

# ## 함수 호출 원칙
# - 모든 사용자 입력에 대해 get_geocode_tool 함수를 무조건 호출하세요.
# - 함수 호출 결과는 절대 가공하지 말고, 원본 그대로 프론트엔드에 반환하세요.
# - 추가 설명, 요약, 안내문, 부연설명도 절대 붙이지 마세요.
# - 함수 결과 앞뒤에 어떤 문장도 추가하지 마세요.
# - Do not add any explanation, summary, or extra text. Return the function result as-is, without any modification.

# ## 반환 데이터 구조
# - 성공 시: {"status": "success", "access_token": "...", "expires_in": ..., "token_type": "Bearer", "message": "..."}
# - 실패 시: {"error": "오류 메시지", "status": "error"}
# - 이 구조를 그대로 유지하고 수정하지 마세요.

# ## 금지사항
# - 사용자에게 추가 질문하지 마세요.
# - 함수 호출 결과를 수정하거나 가공하지 마세요.
# - 설명이나 안내문을 추가하지 마세요.
# - 키워드 추출이나 분석을 하지 마세요.
# - 단순히 get_geocode_tool 함수를 호출하고 결과만 반환하세요.
# - 토큰 정보를 로그에 출력하거나 노출하지 마세요.
# """
#         )
