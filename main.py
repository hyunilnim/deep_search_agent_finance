import os
import logging

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv

from agent.agent_card import build_agent_card
from agent.agent_executor import DeepSearchAgentExecutor

from prompts import prompt as news_prompt_module

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------

async def on_startup():
    global request_handler
    # Executor 재생성 및 교체
    request_handler.agent_executor = DeepSearchAgentExecutor()
    # preload prompt
    try:
        await news_prompt_module.get_system_instruction()
    except Exception as e:
        pass

# 초기 Executor 세팅 (빈 card 가능)
request_handler = DefaultRequestHandler(
    agent_executor=DeepSearchAgentExecutor(),
    task_store=InMemoryTaskStore(),
)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8003"))

server = A2AStarletteApplication(
    agent_card=build_agent_card(HOST, PORT),
    http_handler=request_handler,
)

app = server.build()

# Starlette startup 이벤트 등록
if hasattr(app, "add_event_handler"):
    app.add_event_handler("startup", on_startup)