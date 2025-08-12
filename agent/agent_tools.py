import datetime
import os
import logging
import aiohttp
import ssl
import json
import asyncio
from typing import Dict, Any, Optional, List
from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

async def perplexity_deep_research_tool(
    query: str, 
    tool_context: None = None
) -> Dict[str, Any]:
    """
    Perplexity API를 사용한 Deep Research 기능
    
    Args:
        query: 연구할 질문이나 주제
        tool_context: 도구 컨텍스트
    
    Returns:
        연구 결과를 포함한 딕셔너리
    """
    print(f"=== perplexity_deep_research_tool called with query: {query} ===")
    logger.info(f"=== perplexity_deep_research_tool called with query: {query} ===")
    
    try:
        # 환경 변수에서 Perplexity API 키 가져오기
        api_key = os.getenv('PERPLEXITY_API_KEY')
        
        if not api_key:
            print("=== API 키 누락 ===\nPERPLEXITY_API_KEY 환경 변수가 설정되지 않았습니다.")
            logger.error("PERPLEXITY_API_KEY 환경 변수가 설정되지 않았습니다.")
            return {
                "error": "PERPLEXITY_API_KEY 환경 변수가 설정되지 않았습니다.",
                "error_details": "환경 변수 PERPLEXITY_API_KEY를 설정해주세요.",
                "status": "error"
            }
        
        # SSL 인증서 검증 우회를 위한 컨텍스트 생성
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        # 타임아웃 설정 (30분으로 설정)
        timeout = aiohttp.ClientTimeout(total=1800, connect=1800)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Perplexity API 엔드포인트
            api_url = "https://api.perplexity.ai/chat/completions"
            
            # 요청 헤더
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # 요청 데이터 준비 (시스템 프롬프트 보강)
            request_data = {
                "model": "sonar-deep-research",
                "messages": [
                    {
                        "role": "system",
                        "content": """당신은 전문 투자 분석가입니다. 모든 분석은 상세하고 포괄적이어야 합니다.

각 섹션은 최소 200-300단어 이상으로 자세하고 길게 작성해주세요. 구체적인 수치, 데이터, 최신 뉴스, 분석가 의견, 시장 동향 등을 포함하여 전체 리포트가 최소 3000단어 이상이 되도록 해주세요.

사용자가 요청한 구조와 목차에 따라 체계적으로 분석하되, 각 부분을 충분히 상세하게 다뤄주세요."""
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                "stream": False,
                "reasoning_effort": "high",
                "max_tokens": 12000,  # 최대 토큰 수 대폭 증가
                "temperature": 0.3,  # 창의성과 정확성의 균형
                "top_p": 0.9,
                "return_citations": True,  # 인용문 포함
                "search_recency_filter": "month"  # 최신 정보 우선
            }
            
            print(f"=== Perplexity API 요청 ===\nURL: {api_url}\nHeaders: {headers}\nData: {json.dumps(request_data, indent=2, ensure_ascii=False)}")
            logger.info(f"Perplexity API 요청: {api_url}")
            logger.info(f"요청 데이터: {json.dumps(request_data, indent=2, ensure_ascii=False)}")
            
            # API 호출 (재시도 로직 포함)
            max_retries = 3  # 재시도 횟수 증가
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    print(f"=== Perplexity API 호출 시도 {retry_count + 1}/{max_retries} ===")
                    async with session.post(api_url, json=request_data, headers=headers) as response:
                        if response.status == 200:
                            if request_data['stream']:
                                # 스트리밍 응답 처리
                                result_text = ""
                                async for line in response.content:
                                    line_text = line.decode('utf-8').strip()
                                    if line_text.startswith('data: '):
                                        data_text = line_text[6:]  # 'data: ' 제거
                                        if data_text == '[DONE]':
                                            break
                                        try:
                                            data = json.loads(data_text)
                                            if 'choices' in data and len(data['choices']) > 0:
                                                delta = data['choices'][0].get('delta', {})
                                                if 'content' in delta:
                                                    result_text += delta['content']
                                        except json.JSONDecodeError:
                                            continue
                                
                                return {
                                    "status": "success",
                                    "query": query,
                                    "response": result_text,
                                    "reasoning_effort": 'high',
                                    "stream": request_data['stream'],
                                    "message": "Deep research가 완료되었습니다."
                                }
                            else:
                                # 일반 응답 처리
                                response_data = await response.json()
                                print(f"=== Perplexity API 성공 응답 ===\n{json.dumps(response_data, indent=2, ensure_ascii=False)}")
                                logger.info(f"Perplexity API 성공 응답: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                                
                                # 응답에서 내용 추출
                                if 'choices' in response_data and len(response_data['choices']) > 0:
                                    content = response_data['choices'][0].get('message', {}).get('content', '')
                                    usage = response_data.get('usage', {})
                                    
                                    # 응답 길이 확인 및 로깅
                                    content_length = len(content)
                                    print(f"=== 응답 길이: {content_length} 문자 ===")
                                    logger.info(f"응답 길이: {content_length} 문자")
                                    
                                    if content_length < 1000:
                                        print(f"=== 경고: 응답이 너무 짧습니다 ({content_length} 문자) ===")
                                        logger.warning(f"응답이 너무 짧음: {content_length} 문자")
                                    
                                    return {
                                        "status": "success",
                                        "query": query,
                                        "response": content,
                                        "reasoning_effort": 'high',
                                        "stream": request_data['stream'],
                                        "usage": {
                                            "prompt_tokens": usage.get('prompt_tokens', 0),
                                            "completion_tokens": usage.get('completion_tokens', 0),
                                            "total_tokens": usage.get('total_tokens', 0)
                                        },
                                        "response_length": content_length,
                                        "message": "Deep research가 완료되었습니다."
                                    }
                                else:
                                    print(f"=== 응답 내용 없음 ===\n응답 데이터: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                                    logger.error(f"Perplexity API 응답에서 내용을 찾을 수 없음: {response_data}")
                                    return {
                                        "error": "응답에서 내용을 찾을 수 없습니다.",
                                        "error_details": f"응답 데이터: {json.dumps(response_data, indent=2, ensure_ascii=False)}",
                                        "response": response_data,
                                        "status": "error"
                                    }
                        else:
                            error_text = await response.text()
                            print(f"=== HTTP 에러 응답 ===\nStatus: {response.status}\nHeaders: {dict(response.headers)}\nBody: {error_text}")
                            logger.error(f"Perplexity API HTTP 에러: {response.status} - {error_text}")
                            return {
                                "error": f"Perplexity API 호출 실패: HTTP {response.status}",
                                "error_details": f"응답 헤더: {dict(response.headers)}\n응답 본문: {error_text}",
                                "response": error_text,
                                "status": "error"
                            }
                            
                except asyncio.TimeoutError as e:
                    retry_count += 1
                    print(f"=== 타임아웃 에러 (시도 {retry_count}/{max_retries}) ===\n{str(e)}")
                    logger.warning(f"Perplexity API 타임아웃 (시도 {retry_count}/{max_retries}): {str(e)}")
                    
                    if retry_count >= max_retries:
                        return {
                            "error": f"Perplexity API 호출 타임아웃 (최대 {max_retries}회 시도)",
                            "error_details": f"마지막 에러: {str(e)}",
                            "status": "error"
                        }
                    
                    # 재시도 전 잠시 대기
                    await asyncio.sleep(2 ** retry_count)  # 지수 백오프
                    
                except Exception as e:
                    retry_count += 1
                    print(f"=== 기타 에러 (시도 {retry_count}/{max_retries}) ===\n{str(e)}")
                    logger.warning(f"Perplexity API 기타 에러 (시도 {retry_count}/{max_retries}): {str(e)}")
                    
                    if retry_count >= max_retries:
                        import traceback
                        error_details = traceback.format_exc()
                        logger.error(f"Perplexity API 최종 실패: {str(e)}")
                        logger.error(f"상세 에러 정보: {error_details}")
                        print(f"=== 상세 에러 정보 ===\n{error_details}")
                        return {
                            "error": f"Perplexity API 호출 중 오류가 발생했습니다: {str(e)}",
                            "error_details": error_details,
                            "status": "error"
                        }
                    
                    # 재시도 전 잠시 대기
                    await asyncio.sleep(2 ** retry_count)  # 지수 백오프
                    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Perplexity API 호출 중 오류 발생: {str(e)}")
        logger.error(f"상세 에러 정보: {error_details}")
        print(f"=== 상세 에러 정보 ===\n{error_details}")
        return {
            "error": f"Perplexity API 호출 중 오류가 발생했습니다: {str(e)}",
            "error_details": error_details,
            "status": "error"
        }