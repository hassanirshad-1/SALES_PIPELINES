import os
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled
from agents.tool import Tool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ═══════════════════════════════════════════════════════════
# CLIENT DEFINITIONS
# ═══════════════════════════════════════════════════════════

# Groq (free tier — good for tool-calling models like gpt-oss-120b)
groq_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url=os.getenv("GROQ_BASE_URL"),
    timeout=600.0
)

# AgentRouter / SwiftRouter (premium models like Kimi K2.5)
agentrouter_client = AsyncOpenAI(
    api_key=os.getenv("AGENTROUTER_API_KEY"),
    base_url=os.getenv("AGENTROUTER_BASE_URL"),
    timeout=600.0
)

# HuggingFace Router (fallback)
hf_client = AsyncOpenAI(
    api_key=os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN"),
    base_url="https://router.huggingface.co/v1"
)


# ═══════════════════════════════════════════════════════════
# GROQ COMPATIBILITY PATCH
# The openai-agents SDK injects "strict": true/false into every 
# tool definition, but Groq's API does not support this field.
# This patch strips it before sending.
# ═══════════════════════════════════════════════════════════

class GroqChatCompletionsModel(OpenAIChatCompletionsModel):
    """
    Custom model wrapper that strips the 'strict' field from tool definitions
    before sending to Groq. The openai-agents SDK injects "strict": true/false
    into every tool definition, but Groq's API does not support this field.
    When Groq sees it, the Llama model sometimes falls back to generating
    tool calls as raw XML text (<function=...>) instead of using the proper
    tool_calls API, causing 400 errors.
    """

    async def _fetch_response(self, *args, **kwargs):
        """Override to intercept and fix tool definitions before they hit Groq."""
        return await super()._fetch_response(*args, **kwargs)


def _patch_converter():
    """
    Monkey-patch the SDK's Converter.tool_to_openai to strip the 'strict' field.
    This is the cleanest way to fix it without forking the SDK.
    """
    from agents.models.chatcmpl_converter import Converter
    from agents.tool import FunctionTool, ensure_function_tool_supports_responses_only_features

    _original = Converter.tool_to_openai

    @classmethod
    def tool_to_openai_patched(cls, tool: Tool):
        result = _original.__func__(cls, tool)
        # Strip the 'strict' field that Groq doesn't support
        if "function" in result and "strict" in result["function"]:
            del result["function"]["strict"]
        return result

    Converter.tool_to_openai = tool_to_openai_patched


# Apply the patch on import
_patch_converter()


# ═══════════════════════════════════════════════════════════
# MODEL FACTORY FUNCTIONS
# ═══════════════════════════════════════════════════════════

def get_groq_model(model_name=None):
    """
    Returns a GroqChatCompletionsModel using the Groq client.
    Default model from GROQ_MODEL_NAME env var.
    """
    name = model_name or os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-120b")
    return GroqChatCompletionsModel(
        model=name,
        openai_client=groq_client
    )


def get_swiftrouter_model(model_name=None):
    """
    Returns a model via AgentRouter/SwiftRouter.
    Good for Kimi K2.5 and other premium models.
    """
    name = model_name or os.getenv("AGENTROUTER_MODEL_NAME", "kimi-k2.5")
    return OpenAIChatCompletionsModel(
        model=name,
        openai_client=agentrouter_client
    )


def get_hf_model(model_name=None):
    """
    Returns a model via HuggingFace Router.
    """
    name = model_name or "Qwen/Qwen3-235B-A22B"
    return OpenAIChatCompletionsModel(
        model=name,
        openai_client=hf_client
    )


# ═══════════════════════════════════════════════════════════
# MAIN ROUTER — Change this to switch providers
# ═══════════════════════════════════════════════════════════

# Set ACTIVE_PROVIDER env var to switch: "groq", "swiftrouter", "hf"
# Default: "groq" (using GPT-OSS-120B while Kimi K2.5 is in maintenance)

_PROVIDER_MAP = {
    "groq": get_groq_model,
    "swiftrouter": get_swiftrouter_model,
    "agentrouter": get_swiftrouter_model,  # alias
    "hf": get_hf_model,
    "huggingface": get_hf_model,  # alias
}


def get_agentrouter_model(model_name=None):
    """
    Main entry point — returns the active model based on ACTIVE_PROVIDER env var.
    Defaults to Groq while SwiftRouter/Kimi is in maintenance.
    """
    provider = os.getenv("ACTIVE_PROVIDER", "groq").lower().strip()
    factory = _PROVIDER_MAP.get(provider, get_groq_model)
    return factory(model_name)
