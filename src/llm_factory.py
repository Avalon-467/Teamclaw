"""
LLM 厂商路由工厂 —— 全局共享

根据环境变量 (LLM_PROVIDER / LLM_MODEL / LLM_BASE_URL / LLM_API_KEY)
自动推断厂商并返回对应的 LangChain ChatModel 实例。

支持：Google Gemini / Anthropic Claude / DeepSeek / OpenAI 兼容兜底
所有 provider 均支持 base_url 透传（可接中转代理）。

同时提供 extract_text() 统一提取 AIMessage.content 为纯文本字符串。
"""

import os
from langchain_core.language_models.chat_models import BaseChatModel


# ======================================================================
# 统一文本提取：AIMessage.content -> str
# ======================================================================

def extract_text(content) -> str:
    """从 AIMessage.content 提取纯文本。

    不同厂商的 SDK 返回格式不同：
      - ChatOpenAI / ChatDeepSeek / ChatAnthropic: str
      - ChatGoogleGenerativeAI: list[dict]  (例如 [{"type":"text","text":"..."}])

    本函数统一处理为纯字符串。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                # 跳过 thought_signature 等非文本 block
        return "".join(parts)
    return str(content)

# 模型名 -> 厂商 的自动推断映射
_MODEL_PROVIDER_PATTERNS: dict[str, str] = {
    # 有专用 LangChain 包的厂商
    "gemini": "google",
    "claude": "anthropic",
    "deepseek": "deepseek",
    # 以下统一走 ChatOpenAI（兼容 OpenAI 格式）
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "qwen": "openai",
    "minimax": "openai",
    "glm": "openai",
    "moonshot": "openai",
    "yi-": "openai",
    "baichuan": "openai",
    "doubao": "openai",
    "hunyuan": "openai",
    "ernie": "openai",
    "mistral": "openai",
    "llama": "openai",
    "groq": "openai",
}

# 不支持自定义 temperature 的模型前缀（如 OpenAI 推理模型 o1/o3/o4 系列）
# 这些模型只允许 temperature=1，传其他值会报 400 错误
_NO_TEMPERATURE_PREFIXES = ("o1", "o3", "o4")


def _model_supports_temperature(model: str) -> bool:
    """检查模型是否支持自定义 temperature 参数。"""
    model_lower = model.lower()
    for prefix in _NO_TEMPERATURE_PREFIXES:
        if model_lower.startswith(prefix) and (
            len(model_lower) == len(prefix)        # 精确匹配 "o1"
            or model_lower[len(prefix)] in "-_."   # 匹配 "o3-mini", "o4-mini" 等
        ):
            return False
    return True


def create_chat_model(
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: int = 60,
    max_retries: int = 2,
) -> BaseChatModel:
    """
    读取环境变量，自动路由到正确的厂商 SDK 并返回 ChatModel。

    可覆盖的参数：temperature / max_tokens / timeout / max_retries
    模型、API Key、Base URL、Provider 均从环境变量读取。

    注意：对不支持自定义 temperature 的模型（如 OpenAI o1/o3/o4 推理系列），
    会自动忽略 temperature 参数，使用模型默认值。
    """
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").strip()
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()

    if not api_key:
        raise ValueError("未检测到 LLM_API_KEY，请在环境变量中设置。")

    # 对不支持 temperature 的模型，强制使用默认值 1
    supports_temp = _model_supports_temperature(model)
    effective_temp = temperature if supports_temp else 1

    # 1) 自动推断 provider
    if not provider:
        model_lower = model.lower()
        for pattern, prov in _MODEL_PROVIDER_PATTERNS.items():
            if pattern in model_lower:
                provider = prov
                break
        else:
            provider = "openai"

    # 2) 根据 provider 构造 ChatModel
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        kwargs = dict(
            model=model,
            google_api_key=api_key,
            temperature=effective_temp,
            max_output_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
        if base_url:
            kwargs["base_url"] = base_url
        return ChatGoogleGenerativeAI(**kwargs)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        kwargs = dict(
            model=model,
            api_key=api_key,
            temperature=effective_temp,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
        if base_url:
            kwargs["base_url"] = base_url
        return ChatAnthropic(**kwargs)

    if provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek
        return ChatDeepSeek(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=effective_temp,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            use_responses_api=False,
        )

    # 默认: OpenAI 兼容格式
    from langchain_openai import ChatOpenAI
    openai_base = base_url.rstrip("/") + "/v1"
    return ChatOpenAI(
        model=model,
        base_url=openai_base,
        api_key=api_key,
        temperature=effective_temp,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
    )
