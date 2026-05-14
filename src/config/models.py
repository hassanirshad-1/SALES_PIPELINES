import os
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled
from agents.tool import Tool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()



# Initialize the AsyncOpenAI client pointed at AgentRouter
agentrouter_client = AsyncOpenAI(
    api_key=os.getenv("AGENTROUTER_API_KEY"),
    base_url=os.getenv("AGENTROUTER_BASE_URL")
)

def get_agentrouter_model(model_name=None):
    # TEMPORARY FALLBACK: Using Groq while SwiftRouter is in maintenance
    return get_groq_model(model_name)

# Legacy clients for reference
groq_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url=os.getenv("GROQ_BASE_URL")
)

hf_client = AsyncOpenAI(
    api_key=os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN"),
    base_url="https://router.huggingface.co/v1"
)



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
        # The parent method builds `converted_tools` internally and passes them.
        # We can't easily intercept that, so instead we'll patch the Converter.
        # But a cleaner approach: override get_response and stream_response.
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


def get_groq_model(model_name=None):
    """
    Returns a GroqChatCompletionsModel instance using the custom Groq client.
    This is passed directly into the Agent constructor.
    """
    name = model_name or os.getenv("GROQ_MODEL_NAME")

    return GroqChatCompletionsModel(
        model=name,
        openai_client=groq_client
    )
