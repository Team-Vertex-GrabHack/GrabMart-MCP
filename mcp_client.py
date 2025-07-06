import asyncio
import os
import sys
import logging
import json
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from prompt import META_PROMPT

# LlamaIndex imports
from llama_index.core.llms import ChatMessage
from llama_index.llms.bedrock import Bedrock
from llama_index.core.tools import FunctionTool, ToolMetadata
from llama_index.core.base.llms.types import MessageRole

# Workflow imports
from llama_index.core.workflow import (
    Context,
    Workflow,
    StartEvent,
    StopEvent,
    step,
    Event,
)
from llama_index.core.agent.react import ReActChatFormatter, ReActOutputParser
from llama_index.core.agent.react.types import (
    ActionReasoningStep,
    ObservationReasoningStep,
)
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import ToolSelection, ToolOutput

# Supabase imports
from supabase import create_client, Client

load_dotenv()  # load environment variables from .env

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("mcp_react_agent.log"),
    ],
)

logger = logging.getLogger(__name__)


# Custom Events for our workflow
class PrepEvent(Event):
    pass


class InputEvent(Event):
    input: list[ChatMessage]


class StreamEvent(Event):
    delta: str


class ToolCallEvent(Event):
    tool_calls: list[ToolSelection]


class FunctionOutputEvent(Event):
    output: ToolOutput


class ThoughtEvent(Event):
    """Custom event to save thoughts to Supabase"""

    thought: str
    step_type: str  # 'reasoning', 'action', 'observation'
    session_id: str


class MCPToolWrapper:
    """Wrapper to convert MCP tools to LlamaIndex FunctionTool format"""

    def __init__(
        self,
        session: ClientSession,
        tool_name: str,
        tool_description: str,
        tool_schema: dict,
    ):
        self.session = session
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.tool_schema = tool_schema

    async def execute_tool(self, **kwargs) -> str:
        """Execute the MCP tool with given arguments"""
        try:
            logger.info(f"[Executing MCP tool: {self.tool_name} with args: {kwargs}]")

            result = await self.session.call_tool(self.tool_name, kwargs)

            # Handle different result types
            if hasattr(result, "content"):
                if isinstance(result.content, list):
                    if len(result.content) == 0:
                        return "No results found or empty response from tool."

                    # Handle multiple content blocks
                    content_parts = []
                    for item in result.content:
                        if hasattr(item, "text"):
                            content_parts.append(item.text)
                        elif hasattr(item, "content"):
                            content_parts.append(str(item.content))
                        else:
                            content_parts.append(str(item))

                    if content_parts:
                        return "\n".join(content_parts)
                    else:
                        return "Tool executed but returned no readable content."
                else:
                    if result.content:
                        return str(result.content)
                    else:
                        return "Tool executed but returned empty content."

            if hasattr(result, "structuredContent") and result.structuredContent:
                return str(result.structuredContent)

            if hasattr(result, "isError") and result.isError:
                return f"Tool execution failed with error status."

            return f"Tool executed successfully but result format is unclear. Raw result: {result}"

        except Exception as e:
            logger.error(f"Error executing tool {self.tool_name}: {str(e)}")
            return f"Error: {str(e)}"


class MCPReActWorkflow(Workflow):
    """Custom ReAct Workflow with MCP tools and Supabase logging"""

    def __init__(
        self,
        llm,
        tools: List[FunctionTool],
        supabase_client: Client,
        session_id: str,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.llm = llm
        self.tools = tools
        self.supabase_client = supabase_client
        self.session_id = session_id
        self.step_count = 0
        self.max_steps = 30

        # Initialize ReAct components
        self.formatter = ReActChatFormatter.from_defaults(context=META_PROMPT)
        self.output_parser = ReActOutputParser()

    async def initialize_session(self, user_query: str):
        """Initialize a new session in Supabase"""
        try:
            data = {
                "session_id": self.session_id,
                "user_query": user_query,
                "total_steps": 0,
                "status": "active",
            }

            result = self.supabase_client.table("agent_sessions").insert(data).execute()
            logger.info(f"Initialized session {self.session_id} in Supabase")

        except Exception as e:
            logger.error(f"Error initializing session in Supabase: {str(e)}")

    async def save_step_to_supabase(self, step_type: str, content: str):
        """Save step to Supabase using column-wise storage"""
        try:
            if self.step_count >= self.max_steps:
                logger.warning(
                    f"Maximum steps ({self.max_steps}) reached for session {self.session_id}"
                )
                return

            self.step_count += 1

            # Create update data for the specific step columns
            update_data = {
                f"step_{self.step_count}_type": step_type,
                f"step_{self.step_count}_content": content,
                "total_steps": self.step_count,
                "updated_at": "now()",
            }

            # Update the session record
            result = (
                self.supabase_client.table("agent_sessions")
                .update(update_data)
                .eq("session_id", self.session_id)
                .execute()
            )
            logger.info(
                f"Saved step {self.step_count} ({step_type}) to Supabase: {content[:100]}..."
            )

        except Exception as e:
            logger.error(f"Error saving step to Supabase: {str(e)}")

    async def finalize_session(
        self, final_answer: str, status: str = "completed", error_message: str = None
    ):
        """Finalize the session with final answer and status"""
        try:
            update_data = {
                "final_answer": final_answer,
                "status": status,
                "updated_at": "now()",
            }

            if error_message:
                update_data["error_message"] = error_message

            result = (
                self.supabase_client.table("agent_sessions")
                .update(update_data)
                .eq("session_id", self.session_id)
                .execute()
            )
            logger.info(f"Finalized session {self.session_id} with status: {status}")

        except Exception as e:
            logger.error(f"Error finalizing session in Supabase: {str(e)}")

    @step
    async def new_user_msg(self, ctx: Context, ev: StartEvent) -> PrepEvent:
        """Handle new user message and initialize context"""
        # Clear sources
        await ctx.set("sources", [])

        # Init memory if needed
        memory = await ctx.get("memory", default=None)
        if not memory:
            memory = ChatMemoryBuffer.from_defaults(llm=self.llm)

        # Get user input
        user_input = ev.input
        user_msg = ChatMessage(role="user", content=user_input)
        memory.put(user_msg)

        # Clear current reasoning
        await ctx.set("current_reasoning", [])

        # Set memory
        await ctx.set("memory", memory)

        # Initialize session in Supabase
        await self.initialize_session(user_input)

        # Save user input as first step
        await self.save_step_to_supabase("user_input", user_input)

        return PrepEvent()

    @step
    async def prepare_chat_history(self, ctx: Context, ev: PrepEvent) -> InputEvent:
        """Prepare chat history with ReAct formatting"""
        # Get chat history
        memory = await ctx.get("memory")
        chat_history = memory.get()
        current_reasoning = await ctx.get("current_reasoning", default=[])

        # Format the prompt with react instructions
        llm_input = self.formatter.format(
            self.tools, chat_history, current_reasoning=current_reasoning
        )

        return InputEvent(input=llm_input)

    @step
    async def handle_llm_input(
        self, ctx: Context, ev: InputEvent
    ) -> ToolCallEvent | StopEvent:
        """Handle LLM input and parse reasoning"""
        chat_history = ev.input
        current_reasoning = await ctx.get("current_reasoning", default=[])
        memory = await ctx.get("memory")

        # Use regular chat instead of stream_chat since Bedrock doesn't support streaming
        try:
            response = await self.llm.achat(chat_history)
            full_response = response.message.content

            # Since we can't stream, we'll just write the full response at once
            ctx.write_event_to_stream(StreamEvent(delta=full_response))

        except Exception as e:
            error_msg = f"Error getting LLM response: {str(e)}"
            logger.error(error_msg)
            await self.save_step_to_supabase("error", error_msg)
            await self.finalize_session("", "error", error_msg)

            current_reasoning.append(ObservationReasoningStep(observation=error_msg))
            await ctx.set("current_reasoning", current_reasoning)
            return PrepEvent()

        try:
            # Parse the reasoning step
            reasoning_step = self.output_parser.parse(response.message.content)
            current_reasoning.append(reasoning_step)

            # Save reasoning step to Supabase
            if hasattr(reasoning_step, "thought"):
                await self.save_step_to_supabase("reasoning", reasoning_step.thought)

            if reasoning_step.is_done:
                # Final response - save to Supabase
                await self.save_step_to_supabase(
                    "final_answer", reasoning_step.response
                )
                await self.finalize_session(reasoning_step.response, "completed")

                memory.put(
                    ChatMessage(role="assistant", content=reasoning_step.response)
                )
                await ctx.set("memory", memory)
                await ctx.set("current_reasoning", current_reasoning)

                sources = await ctx.get("sources", default=[])
                return StopEvent(
                    result={
                        "response": reasoning_step.response,
                        "sources": sources,
                        "reasoning": current_reasoning,
                        "session_id": self.session_id,
                    }
                )

            elif isinstance(reasoning_step, ActionReasoningStep):
                # Tool action needed - save to Supabase
                action_content = f"Action: {reasoning_step.action}, Args: {reasoning_step.action_input}"
                await self.save_step_to_supabase("action", action_content)

                tool_name = reasoning_step.action
                tool_args = reasoning_step.action_input

                return ToolCallEvent(
                    tool_calls=[
                        ToolSelection(
                            tool_id="fake",
                            tool_name=tool_name,
                            tool_kwargs=tool_args,
                        )
                    ]
                )

        except Exception as e:
            error_msg = f"Error in parsing reasoning: {e}"
            logger.error(error_msg)

            # Save error to Supabase
            await self.save_step_to_supabase("error", error_msg)
            await self.finalize_session("", "error", error_msg)

            current_reasoning.append(ObservationReasoningStep(observation=error_msg))
            await ctx.set("current_reasoning", current_reasoning)

        # Loop again if no tool calls or final response
        return PrepEvent()

    @step
    async def handle_tool_calls(self, ctx: Context, ev: ToolCallEvent) -> PrepEvent:
        """Handle tool execution and save observations"""
        tool_calls = ev.tool_calls
        tools_by_name = {tool.metadata.get_name(): tool for tool in self.tools}
        current_reasoning = await ctx.get("current_reasoning", default=[])
        sources = await ctx.get("sources", default=[])

        # Execute tools
        for tool_call in tool_calls:
            tool = tools_by_name.get(tool_call.tool_name)

            if not tool:
                error_msg = f"Tool {tool_call.tool_name} does not exist"
                current_reasoning.append(
                    ObservationReasoningStep(observation=error_msg)
                )
                await self.save_step_to_supabase("error", error_msg)
                continue

            try:
                # Execute the tool
                tool_output = await tool.acall(**tool_call.tool_kwargs)
                sources.append(tool_output)

                observation = tool_output.content
                current_reasoning.append(
                    ObservationReasoningStep(observation=observation)
                )

                # Save tool observation to Supabase
                observation_content = (
                    f"Tool '{tool_call.tool_name}' result: {observation}"
                )
                await self.save_step_to_supabase("observation", observation_content)

            except Exception as e:
                error_msg = f"Error calling tool {tool.metadata.get_name()}: {e}"
                current_reasoning.append(
                    ObservationReasoningStep(observation=error_msg)
                )
                await self.save_step_to_supabase("error", error_msg)

        # Save updated state
        await ctx.set("sources", sources)
        await ctx.set("current_reasoning", current_reasoning)

        return PrepEvent()


class MCPReActAgent:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.workflow: Optional[MCPReActWorkflow] = None
        self.tools: List[FunctionTool] = []  # Store tools for reuse

        # Initialize Supabase client
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_ANON_KEY")

        if supabase_url and supabase_key:
            self.supabase_client = create_client(supabase_url, supabase_key)
        else:
            logger.warning("Supabase credentials not found. Thoughts won't be saved.")
            self.supabase_client = None

        # Initialize AWS Bedrock client via LlamaIndex
        self.llm = Bedrock(
            model=os.environ.get(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
            ),
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
            max_tokens=2048,
            context_size=4096,
        )

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server and store tools for reuse"""
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        # List available tools and convert them to LlamaIndex tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

        # Convert MCP tools to LlamaIndex FunctionTool format and store them
        self.tools = []
        for tool in tools:
            tool_wrapper = MCPToolWrapper(
                self.session, tool.name, tool.description, tool.inputSchema
            )

            def make_tool_function(wrapper):
                async def tool_function(**kwargs):
                    return await wrapper.execute_tool(**kwargs)

                return tool_function

            tool_function = make_tool_function(tool_wrapper)

            try:
                function_tool = FunctionTool.from_defaults(
                    async_fn=tool_function, name=tool.name, description=tool.description
                )
                self.tools.append(function_tool)
                logger.info(f"Successfully converted tool: {tool.name}")

            except Exception as e:
                logger.error(f"Failed to convert tool {tool.name}: {str(e)}")
                continue

        print(f"\nMCP Tools initialized: {len(self.tools)} tools available")

    async def process_query(self, query: str) -> str:
        """Process a query using ReAct workflow - creates a NEW session for each query"""
        if not self.tools:
            return "Error: No tools available. Please connect to server first."

        try:
            # Create a NEW session ID for each query
            import time

            session_id = f"session_{int(time.time() * 1000)}"  # More unique timestamp

            # Create a NEW workflow instance for each query
            workflow = MCPReActWorkflow(
                llm=self.llm,
                tools=self.tools,
                supabase_client=self.supabase_client,
                session_id=session_id,
                timeout=240,
                verbose=True,
            )

            logger.info(f"Created new workflow with session ID: {session_id}")

            # Run the workflow
            result = await workflow.run(input=query)

            # Return just the response string
            return result.get("response", "No response generated")

        except Exception as e:
            logger.error(f"Error processing query with ReAct workflow: {str(e)}")
            return f"Error: {str(e)}"


async def main():
    if len(sys.argv) < 2:
        print("Usage: python react_mcp_agent.py <path_to_server_script>")
        print("\nExample:")
        print("python react_mcp_agent.py ./filesystem_server.py")
        print("\nMake sure to set the following environment variables:")
        print("- SUPABASE_URL")
        print("- SUPABASE_ANON_KEY")
        print("- AWS_ACCESS_KEY_ID")
        print("- AWS_SECRET_ACCESS_KEY")
        print("- AWS_DEFAULT_REGION")
        sys.exit(1)

    agent = MCPReActAgent()
    try:
        await agent.connect_to_server(sys.argv[1])
        await agent.chat_loop()
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
