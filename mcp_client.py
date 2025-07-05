import asyncio
import os
import sys
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.gemini_client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        self.model = "gemini-2.5-flash-lite-preview-06-17"

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    def _format_tools_for_gemini(self, tools):
        """Format MCP tools for Gemini's function calling format"""
        if not tools:
            return []
            
        function_declarations = []
        for tool in tools:
            # Create function declaration as a dict (not types.FunctionDeclaration)
            function_declaration = {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
            function_declarations.append(function_declaration)
        
        # Create Tool object with function declarations
        gemini_tool = types.Tool(function_declarations=function_declarations)
        return [gemini_tool]

    async def process_query(self, query: str) -> str:
        """Process a query using Gemini and available tools"""
        # Get available tools
        response = await self.session.list_tools()
        available_tools = self._format_tools_for_gemini(response.tools)

        # Create initial conversation with tools
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=query),
                ],
            ),
        ]

        # Configure generation with function calling
        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=0,
            ),
            tools=available_tools,
            response_mime_type="text/plain",
        )

        try:
            # Initial Gemini API call
            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            )

            final_text = []

            # Process the response
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                
                # Handle text content
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            final_text.append(part.text)
                        elif hasattr(part, 'function_call') and part.function_call:
                            # Handle function call
                            function_call = part.function_call
                            tool_name = function_call.name
                            tool_args = dict(function_call.args) if function_call.args else {}
                            
                            final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                            
                            # Execute tool call
                            try:
                                result = await self.session.call_tool(tool_name, tool_args)
                                
                                # Add function response to conversation
                                contents.append(candidate.content)  # Add the assistant's response with function call
                                contents.append(
                                    types.Content(
                                        role="user",
                                        parts=[
                                            types.Part.from_function_response(
                                                name=tool_name,
                                                response={"result": str(result.content)}
                                            )
                                        ],
                                    )
                                )
                                # Get follow-up response from Gemini
                                follow_up_response = self.gemini_client.models.generate_content(
                                    model=self.model,
                                    contents=contents,
                                    config=generate_content_config,
                                )
                                
                                if (follow_up_response.candidates and 
                                    len(follow_up_response.candidates) > 0 and
                                    follow_up_response.candidates[0].content and
                                    follow_up_response.candidates[0].content.parts):
                                    
                                    for part in follow_up_response.candidates[0].content.parts:
                                        if hasattr(part, 'text') and part.text:
                                            final_text.append(part.text)
                                            
                            except Exception as e:
                                final_text.append(f"Error executing tool {tool_name}: {str(e)}")
                
                return "\n".join(final_text) if final_text else "No response generated"
            else:
                return "No response generated from Gemini"
                
        except Exception as e:
            return f"Error processing query: {str(e)}"

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)
        
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())