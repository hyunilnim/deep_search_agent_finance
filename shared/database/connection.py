import os
import asyncio
import aiomysql
import pymysql
from typing import Optional, List, Dict, Any
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        # .env 파일 로드
        load_dotenv()
        self._config = self._load_config()
        self._async_pool: Optional[aiomysql.Pool] = None
        self._sync_connection: Optional[pymysql.Connection] = None

    def _load_config(self) -> Dict[str, Any]:
        """데이터베이스 연결 설정 로드 (pool_recycle 추가)"""
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "agent_house"),
            "charset": "utf8mb4",
            # pool_recycle 값을 환경 변수에서 가져오도록 추가 (기본값 3600초 = 1시간)
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", 3600)),
        }

    async def get_async_connection(self) -> aiomysql.Pool:
        """비동기 DB 연결 풀 반환 (pool_recycle, autocommit 적용)"""
        if not self._async_pool:
            try:
                # autocommit과 pool_recycle 설정 추가
                self._async_pool = await aiomysql.create_pool(
                    host=self._config["host"],
                    port=self._config["port"],
                    user=self._config["user"],
                    password=self._config["password"],
                    db=self._config["database"],
                    charset=self._config["charset"],
                    autocommit=True,
                    pool_recycle=self._config["pool_recycle"],
                )
                logger.info("Async DB connection pool created.")
            except Exception as e:
                logger.error(f"Failed to create async DB pool: {e}")
                raise
        return self._async_pool

    def get_sync_connection(self) -> pymysql.Connection:
        """동기 DB 연결 반환 (연결 상태 확인 및 자동 재연결 로직 추가)"""
        try:
            # 연결이 없거나, 닫혔을 경우 새로 생성
            if not self._sync_connection or not self._sync_connection.open:
                self._sync_connection = pymysql.connect(
                    host=self._config["host"],
                    port=self._config["port"],
                    user=self._config["user"],
                    password=self._config["password"],
                    database=self._config["database"],
                    charset=self._config["charset"],
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True,
                )
                logger.info("Sync DB connection created.")
            else:
                # 연결이 살아있는지 확인하고, 끊겼으면 재연결 시도
                self._sync_connection.ping(reconnect=True)
        except pymysql.err.OperationalError as e:
            logger.error(f"Sync DB connection failed. Attempting to reconnect: {e}")
            # 재연결 실패 시, 연결 객체를 None으로 만들어 다음 시도에 새로 생성하도록 함
            self._sync_connection = None
            raise
        return self._sync_connection

    async def execute_async_query(
        self, query: str, params: Optional[tuple] = None
    ) -> List[tuple]:
        """비동기 쿼리 실행"""
        try:
            pool = await self.get_async_connection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    return await cursor.fetchall()
        except Exception as e:
            logger.error(f"Async query failed: {e}")
            raise

    def execute_sync_query(
        self, query: str, params: Optional[tuple] = None, retries=1
    ) -> List[Dict[str, Any]]:
        """동기 쿼리 실행 (연결 오류 시 1회 자동 재시도)"""
        try:
            conn = self.get_sync_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except pymysql.err.OperationalError as e:
            # 연결 관련 문제 발생 시 재시도
            logger.warning(
                f"Sync query failed due to OperationalError: {e}. Retrying..."
            )
            self.close_sync_connection()  # 기존 연결 강제 종료
            if retries > 0:
                return self.execute_sync_query(query, params, retries=retries - 1)
            else:
                logger.error("Sync query failed after retry.")
                raise
        except Exception as e:
            logger.error(f"Sync query failed: {e}")
            raise

    async def close_async_pool(self):
        """비동기 연결 풀 종료"""
        if self._async_pool:
            self._async_pool.close()
            await self._async_pool.wait_closed()
            self._async_pool = None
            logger.info("Async DB connection pool closed.")

    def close_sync_connection(self):
        """동기 연결 종료"""
        if self._sync_connection:
            try:
                self._sync_connection.close()
            except Exception:
                pass  # 이미 닫혔거나 문제가 있어도 무시
            self._sync_connection = None
            logger.info("Sync DB connection closed.")


# 글로벌 인스턴스
db_manager = DatabaseManager()
