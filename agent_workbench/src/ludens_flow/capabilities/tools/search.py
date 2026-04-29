"""
文件功能：能力工具模块（search.py），对外提供可控工具调用能力。
核心内容：封装工具参数处理、错误返回与结果摘要的统一行为。
核心内容：作为 Agent 工具层能力入口，服务文件/搜索/工作区相关任务。
"""

import logging
from typing import Dict, Any, List

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

logger = logging.getLogger(__name__)

def web_search(query: str, max_results: int = 5) -> str:
    """
    Perform a web search using DuckDuckGo and return a summarized text result.
    """
    if DDGS is None:
        return "Error: duckduckgo_search library is not installed. Web Search is disabled."
        
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title", "No Title")
                href = r.get("href", "")
                body = r.get("body", "No Content")
                results.append(f"[{title}]({href})\n{body}")
                
        if not results:
            return f"No search results found for query: '{query}'"
            
        return "\n\n---\n\n".join(results)
    except Exception as e:
        err_msg = f"Web search failed: {e}"
        logger.error(err_msg)
        return err_msg


# Standard OpenAI Tool Schema for the web search function
SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Perform a real-time web search to find current information, documentation, news, or solve errors. Useful when you need information beyond your training data.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string. Be specific and concise."
                }
            },
            "required": ["query"]
        }
    }
}
