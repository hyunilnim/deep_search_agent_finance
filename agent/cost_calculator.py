import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PerplexityCostCalculator:
    """Perplexity Sonar 모델들의 사용료 계산기"""

    # Sonar 모델별 가격 (USD per 1M tokens)
    PRICING = {
        "sonar": {
            "input_tokens": 1.0,  # $1 per 1M tokens
            "output_tokens": 1.0,  # $1 per 1M tokens
            "citation_tokens": 0.0,  # Not applicable
            "search_queries": 0.0,  # Not applicable
            "reasoning_tokens": 0.0,  # Not applicable
        },
        "sonar-pro": {
            "input_tokens": 3.0,  # $3 per 1M tokens
            "output_tokens": 15.0,  # $15 per 1M tokens
            "citation_tokens": 0.0,  # Not applicable
            "search_queries": 0.0,  # Not applicable
            "reasoning_tokens": 0.0,  # Not applicable
        },
        "sonar-reasoning": {
            "input_tokens": 1.0,  # $1 per 1M tokens
            "output_tokens": 5.0,  # $5 per 1M tokens
            "citation_tokens": 0.0,  # Not applicable
            "search_queries": 0.0,  # Not applicable
            "reasoning_tokens": 0.0,  # Not applicable
        },
        "sonar-reasoning-pro": {
            "input_tokens": 2.0,  # $2 per 1M tokens
            "output_tokens": 8.0,  # $8 per 1M tokens
            "citation_tokens": 0.0,  # Not applicable
            "search_queries": 0.0,  # Not applicable
            "reasoning_tokens": 0.0,  # Not applicable
        },
        "sonar-deep-research": {
            "input_tokens": 2.0,  # $2 per 1M tokens
            "output_tokens": 8.0,  # $8 per 1M tokens
            "citation_tokens": 2.0,  # $2 per 1M tokens
            "search_queries": 5.0,  # $5 per 1K queries
            "reasoning_tokens": 3.0,  # $3 per 1M tokens
        },
    }

    def __init__(self, model_name: str = "sonar-deep-research"):
        self.model_name = model_name
        self.pricing = self.PRICING.get(model_name, self.PRICING["sonar-deep-research"])

    def calculate_cost(self, usage: Dict[str, Any]) -> Dict[str, Any]:
        """
        usage 객체에서 사용료를 계산합니다.

        Args:
            usage: Perplexity API response의 usage 객체

        Returns:
            계산된 사용료 정보
        """
        try:
            # usage에서 각 필드 추출 (Perplexity API 필드명에 맞춤)
            input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
            output_tokens = usage.get(
                "completion_tokens", usage.get("output_tokens", 0)
            )
            citation_tokens = usage.get("citation_tokens", 0)
            search_queries = usage.get(
                "num_search_queries", usage.get("search_queries", 0)
            )
            reasoning_tokens = usage.get("reasoning_tokens", 0)

            # 각 항목별 비용 계산
            input_cost = (input_tokens / 1_000_000) * self.pricing["input_tokens"]
            output_cost = (output_tokens / 1_000_000) * self.pricing["output_tokens"]
            citation_cost = (citation_tokens / 1_000_000) * self.pricing[
                "citation_tokens"
            ]
            search_cost = (search_queries / 1_000) * self.pricing["search_queries"]
            reasoning_cost = (reasoning_tokens / 1_000_000) * self.pricing[
                "reasoning_tokens"
            ]

            # 총 비용 계산
            total_cost = (
                input_cost + output_cost + citation_cost + search_cost + reasoning_cost
            )

            result = {
                "model": self.model_name,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "citation_tokens": citation_tokens,
                    "search_queries": search_queries,
                    "reasoning_tokens": reasoning_tokens,
                },
                "costs": {
                    "input_cost": round(input_cost, 6),
                    "output_cost": round(output_cost, 6),
                    "citation_cost": round(citation_cost, 6),
                    "search_cost": round(search_cost, 6),
                    "reasoning_cost": round(reasoning_cost, 6),
                },
                "total_cost": round(total_cost, 6),
                "total_cost_usd": f"${total_cost:.6f}",
            }

            logger.info(
                f"Cost calculation for {self.model_name}: {result['total_cost_usd']}"
            )
            return result

        except Exception as e:
            logger.error(f"Error calculating cost: {e}")
            return {
                "model": self.model_name,
                "error": str(e),
                "total_cost": 0.0,
                "total_cost_usd": "$0.000000",
            }

    def format_cost_summary(self, cost_info: Dict[str, Any]) -> str:
        """사용료 정보를 읽기 쉬운 형태로 포맷팅합니다."""
        if "error" in cost_info:
            return f"❌ Cost calculation error: {cost_info['error']}"

        usage = cost_info["usage"]
        costs = cost_info["costs"]

        summary = f"""
💰 **Perplexity Sonar Deep Research 사용료**

📊 **사용량:**
• Input Tokens: {usage['input_tokens']:,}
• Output Tokens: {usage['output_tokens']:,}
• Citation Tokens: {usage['citation_tokens']:,}
• Search Queries: {usage['search_queries']:,}
• Reasoning Tokens: {usage['reasoning_tokens']:,}

💵 **비용 세부사항:**
• Input Cost: ${costs['input_cost']:.6f}
• Output Cost: ${costs['output_cost']:.6f}
• Citation Cost: ${costs['citation_cost']:.6f}
• Search Cost: ${costs['search_cost']:.6f}
• Reasoning Cost: ${costs['reasoning_cost']:.6f}

🎯 **총 비용: {cost_info['total_cost_usd']}**
"""
        return summary.strip()
