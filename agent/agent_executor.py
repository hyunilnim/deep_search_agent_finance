from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import TaskState, TextPart, UnsupportedOperationError, Message
from a2a.utils.errors import ServerError
from a2a.types import TaskArtifactUpdateEvent, TaskStatusUpdateEvent, TaskStatus, TaskState, TextPart, UnsupportedOperationError, Message
from a2a.utils import new_agent_text_message, new_task, new_text_artifact

from agent.agent import DeepSearchAgent
from a2a.types import AgentCard
import logging
import traceback
import json
import time
import os
import datetime
import aiohttp
from pprint import pformat

logger = logging.getLogger("deep_search_agent.agent_executor")

class DeepSearchAgentExecutor(AgentExecutor):

    def __init__(self):
        self.agent = None
        # 캐싱 관련 변수들
        self._cached_cards = None
        self._cached_hash = None
        self._last_cache_time = 0
        self._cache_duration = int(os.getenv('AGENT_CACHE_DURATION', '600'))  # 기본 10분
    
    async def execute(
        self, 
        context:RequestContext, 
        event_queue:EventQueue
    ) -> None:
        
        metadata = context._params.message.metadata or {}
        session_id = metadata.get("session_id", "default-session")
        app_name = metadata.get('app_name', 'default-app')
        user_id = metadata.get("user_id", "default-user")

        print(f"app_name: {app_name}")
        
        # plan과 next_steps 정보 추출
        plan = metadata.get("plan", "")
        next_steps = metadata.get("next_steps", [])
        current_step = metadata.get("current_step", "")
        step_index = metadata.get("step_index", 0)
        total_steps = metadata.get("total_steps", 0)
        accumulated_results = metadata.get("accumulated_results", [])
        original_target = metadata.get("original_target", "")
        
        query = context.get_user_input()
        task = context.current_task

        # WebSocket 서버로 메시지 push
        try:
            async with aiohttp.ClientSession() as session:
                push_message = {
                    "type": "agent_status",
                    "message": "보고서 작성을 위한 검색 중입니다.",
                    "agent": "deep_search_agent",
                    "session_id": session_id,
                    "user_id": user_id,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
                async with session.post(
                    "http://localhost:4000/push",
                    json=push_message,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        logger.info("WebSocket 메시지 push 성공")
                    else:
                        logger.warning(f"WebSocket 메시지 push 실패: {response.status}")
        except Exception as e:
            logger.error(f"WebSocket 메시지 push 오류: {e}")

        if self.agent is None or getattr(self.agent, 'app_name', None) != app_name:
                self.agent = DeepSearchAgent(app_name)

        try :
            if not task :
                task = new_task(context.message)
                await event_queue.enqueue_event(new_task(context.message))
            
            # 메타데이터를 포함한 컨텍스트 정보를 쿼리에 추가
            enhanced_query = query
            if plan or next_steps:
                step_info = f" (단계 {step_index + 1}/{total_steps})" if total_steps > 0 else ""
                enhanced_query = f"""
                                    원본 요청: {query}

                                    전체 계획: {plan}
                                    현재 단계: {current_step}{step_info}

                                    이전 단계 결과:
                                    {chr(10).join([f"- {result}" for result in accumulated_results]) if accumulated_results else "없음"}

                                    위 계획에 따라 {current_step} 작업을 수행해주세요.
                                    """
            else:
                pass
            # 텍스트 chunk를 누적하여 최종 결과 생성
            accumulated_text = ""
            async for text_chunk in self.agent.invoke(enhanced_query, session_id, task.id, user_id, app_name):
                logger.info(f"[DeepSearchAgent] text_chunk: {text_chunk}")
                if isinstance(text_chunk, str):
                    accumulated_text += text_chunk
                    
                    # 진행 상황을 실시간으로 전달
                    await event_queue.enqueue_event(
                        TaskStatusUpdateEvent(
                            taskId=task.id,
                            contextId=task.contextId,
                            status=TaskStatus(
                                state=TaskState.working,
                                message=new_agent_text_message(
                                    f"뉴스 검색 중... {len(accumulated_text)}자",
                                    task.id,
                                    task.contextId,
                                ),
                            ),
                            final=False,
                        )
                    )
            
            # 최종 결과를 이벤트로 생성
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    taskId=task.id,
                    contextId=task.contextId,
                    artifact=new_text_artifact(
                        name='deep_search_agent_result',
                        description='딥 서치 에이전트 결과',
                        text=accumulated_text,
                    ),
                    append=False,
                    lastChunk=True,
                )
            )
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    taskId=task.id,
                    contextId=task.contextId,
                    status=TaskStatus(state=TaskState.completed),
                    final=True
                )
            )
            
        except Exception as e :
            traceback.print_exc()
            raise ServerError(f"Error executing deep_search_agent: {e}")

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
            raise ServerError(error=UnsupportedOperationError())        
