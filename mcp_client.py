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
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool, ToolMetadata
from llama_index.core.base.llms.types import MessageRole

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
            # print(f"Tool: {self.tool_name}")
            # print(f"Args: {kwargs}")
            # print(f"Schema: {self.tool_schema}")

            result = await self.session.call_tool(self.tool_name, kwargs)
            # print(f"Result: {result}")
            # print(f"Result type: {type(result)}")
            # print(f"Result attributes: {dir(result)}")

            # Handle different result types
            if hasattr(result, "content"):
                # print(f"Content: {result.content}")
                # print(f"Content type: {type(result.content)}")

                if isinstance(result.content, list):
                    if len(result.content) == 0:
                        return "No results found or empty response from tool."

                    # Handle multiple content blocks
                    content_parts = []
                    for item in result.content:
                        # print(f"Content item: {item}, type: {type(item)}")
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

            # Check for other attributes that might contain the result
            if hasattr(result, "structuredContent") and result.structuredContent:
                print(f"Structured content: {result.structuredContent}")
                return str(result.structuredContent)

            if hasattr(result, "isError") and result.isError:
                return f"Tool execution failed with error status."

            # If we get here, the tool executed but we don't know how to parse the result
            return f"Tool executed successfully but result format is unclear. Raw result: {result}"

        except Exception as e:
            logger.error(f"Error executing tool {self.tool_name}: {str(e)}")
            print(f"Full error: {e}")
            import traceback

            traceback.print_exc()
            return f"Error: {str(e)}"


class MCPReActAgent:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.agent: Optional[ReActAgent] = None

        # Initialize AWS Bedrock client via LlamaIndex
        self.llm = Bedrock(
            model=os.environ.get(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
            ),
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.environ.get(
                "AWS_SESSION_TOKEN"
            ),  # Optional for temporary credentials
            max_tokens = 2048,
            context_size = 4096,
            # max_tokens = 65536, 
            # temperature=0.1,
            trace
            
        )

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server and initialize ReACT agent

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
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

        # Convert MCP tools to LlamaIndex FunctionTool format
        llamaindex_tools = []
        for tool in tools:
            # Create wrapper for MCP tool
            tool_wrapper = MCPToolWrapper(
                self.session, tool.name, tool.description, tool.inputSchema
            )

            # Create a proper async function that captures the tool_wrapper
            def make_tool_function(wrapper):
                async def tool_function(**kwargs):
                    return await wrapper.execute_tool(**kwargs)

                return tool_function

            tool_function = make_tool_function(tool_wrapper)

            # Try different approaches to create the tool
            try:
                # Approach 1: Simple FunctionTool without schema
                function_tool = FunctionTool.from_defaults(
                    async_fn=tool_function, name=tool.name, description=tool.description
                )

                llamaindex_tools.append(function_tool)
                logger.info(f"Successfully converted tool: {tool.name}")

            except Exception as e1:
                logger.warning(f"First approach failed for tool {tool.name}: {str(e1)}")

                try:
                    # Approach 2: Use ToolMetadata
                    metadata = ToolMetadata(
                        name=tool.name, description=tool.description
                    )

                    function_tool = FunctionTool(
                        fn=tool_function, metadata=metadata, async_fn=tool_function
                    )

                    llamaindex_tools.append(function_tool)
                    logger.info(
                        f"Successfully converted tool with metadata: {tool.name}"
                    )

                except Exception as e2:
                    logger.error(
                        f"All approaches failed for tool {tool.name}: {str(e2)}"
                    )
                    print(f"Error converting tool {tool.name}: {e2}")
                    import traceback

                    traceback.print_exc()
                    continue

        # Initialize ReACT agent with the converted tools
        self.agent = ReActAgent.from_tools(
            llamaindex_tools, llm=self.llm, verbose=True, max_iterations=30, context=META_PROMPT
        )

        print(f"\nReACT Agent initialized with {len(llamaindex_tools)} tools")

    async def process_query(self, query: str) -> str:
        """Process a query using ReACT agent"""
        if not self.agent:
            return "Error: Agent not initialized. Please connect to server first."

        try:
            # Use the ReACT agent to process the query
            response = await self.agent.achat(query)
            return str(response)

        except Exception as e:
            logger.error(f"Error processing query with ReACT agent: {str(e)}")
            return f"Error processing query: {str(e)}"

    # Add this method for API usage
    async def process_single_query(self, query: str) -> Dict[str, Any]:
        """Process a single query and return structured response"""
        try:
            response = await self.process_query(query)
            return {
                "success": True,
                "response": response,
                "error": None
            }
        except Exception as e:
            logger.error(f"Error in process_single_query: {str(e)}")
            return {
                "success": False,
                "response": None,
                "error": str(e)
            }

    async def chat_loop(self):
        """Run an interactive chat loop with ReACT agent"""
        print("\nMCP ReACT Agent Started!")
        print(
            "The agent will use Reasoning, Acting, and Observing to solve your problems."
        )
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                print("\n" + "=" * 50)
                print("ReACT Agent Processing...")
                print("=" * 50)

                response = await self.process_query(query)
                print(f"\nFinal Answer: {response}")

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python react_mcp_agent.py <path_to_server_script>")
        print("\nExample:")
        print("python react_mcp_agent.py ./filesystem_server.py")
        sys.exit(1)

    agent = MCPReActAgent()
    try:
        await agent.connect_to_server(sys.argv[1])
        await agent.chat_loop()
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
