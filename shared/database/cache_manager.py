import time
import os
from typing import Any, Callable, Optional, Dict, Tuple
import logging
import asyncio

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._default_duration = int(os.getenv('GLOBAL_CACHE_DURATION', '600'))
        pass
    
    async def get_or_fetch(self, key: str, fetch_func: Callable, cache_duration: Optional[int] = None) -> Any:
        """캐시된 값 반환 또는 새로 조회"""
        current_time = time.time()
        duration = cache_duration or self._default_duration
        
        # 캐시 확인
        if key in self._cache:
            cached_data, timestamp = self._cache[key]
            if current_time - timestamp < duration:
                return cached_data
        
        # 캐시 미스 - 새로 조회
        
        try:
            if asyncio.iscoroutinefunction(fetch_func):
                data = await fetch_func()
            else:
                data = fetch_func()
            
            # 캐시 저장
            self._cache[key] = (data, current_time)
            return data
            
        except Exception as e:
            raise
    
    def get(self, key: str) -> Optional[Any]:
        """캐시된 값 조회 (캐시 미스 시 None 반환)"""
        if key in self._cache:
            cached_data, timestamp = self._cache[key]
            if time.time() - timestamp < self._default_duration:
                return cached_data
        return None
    
    def set(self, key: str, value: Any, cache_duration: Optional[int] = None):
        """캐시에 값 저장"""
        duration = cache_duration or self._default_duration
        self._cache[key] = (value, time.time())
    
    def invalidate_cache(self, pattern: str = None):
        """캐시 무효화"""
        if pattern:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            count = len(self._cache)
            self._cache.clear()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """캐시 상태 정보"""
        current_time = time.time()
        valid_items = 0
        expired_items = 0
        
        for key, (_, timestamp) in self._cache.items():
            if current_time - timestamp < self._default_duration:
                valid_items += 1
            else:
                expired_items += 1
        
        return {
            'total_items': len(self._cache),
            'valid_items': valid_items,
            'expired_items': expired_items,
            'keys': list(self._cache.keys()),
            'default_duration': self._default_duration
        }
    
    def cleanup_expired(self):
        """만료된 캐시 항목 정리"""
        current_time = time.time()
        keys_to_remove = []
        
        for key, (_, timestamp) in self._cache.items():
            if current_time - timestamp >= self._default_duration:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._cache[key]

# 글로벌 인스턴스
cache_manager = CacheManager() 