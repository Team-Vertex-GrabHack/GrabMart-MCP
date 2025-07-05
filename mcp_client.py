import asyncio
import os
import sys
import logging
import json
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('mcp_client.log')
    ]
)

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
        # Initialize AWS Bedrock client
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            aws_session_token=os.environ.get('AWS_SESSION_TOKEN')  # Optional for temporary credentials
        )
        
        # Available models: anthropic.claude-3-5-sonnet-20241022-v2:0, anthropic.claude-3-haiku-20240307-v1:0, etc.
        self.model_id = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')

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

    def _format_tools_for_bedrock(self, tools):
        """Format MCP tools for Bedrock's function calling format"""
        if not tools:
            return []
            
        bedrock_tools = []
        for tool in tools:
            # Format for Bedrock Claude models
            bedrock_tool = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
            bedrock_tools.append(bedrock_tool)
        
        return bedrock_tools

    def _create_bedrock_request(self, messages, tools=None):
        """Create a request body for Bedrock Claude API"""
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "messages": messages
        }
        
        if tools:
            request_body["tools"] = tools
            
        return request_body

    async def process_query(self, query: str) -> str:
        """Process a query using Bedrock Claude and available tools"""
        # Get available tools
        response = await self.session.list_tools()
        available_tools = self._format_tools_for_bedrock(response.tools)

        # Create initial conversation
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        try:
            # Initial Bedrock API call
            request_body = self._create_bedrock_request(messages, available_tools)
            
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            
            # Process the response
            if 'content' in response_body:
                content = response_body['content']
                final_text = []
                
                for content_block in content:
                    if content_block['type'] == 'text':
                        final_text.append(content_block['text'])
                    elif content_block['type'] == 'tool_use':
                        # Handle tool use
                        tool_use = content_block
                        tool_name = tool_use['name']
                        tool_args = tool_use['input']
                        tool_use_id = tool_use['id']
                        
                        logger.info(f"[Calling tool {tool_name} with args {tool_args}]")
                        
                        # Execute tool call
                        try:
                            result = await self.session.call_tool(tool_name, tool_args)
                            
                            # print(f"Tool result: {result}")
                            
                            # Add assistant message with tool use
                            messages.append({
                                "role": "assistant",
                                "content": response_body['content']
                            })
                            
                            # Add tool result
                            messages.append({
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_use_id,
                                        "content": str(result.content)
                                    }
                                ]
                            })
                            
                            # Get follow-up response from Bedrock
                            follow_up_request = self._create_bedrock_request(messages, available_tools)
                            
                            follow_up_response = self.bedrock_client.invoke_model(
                                modelId=self.model_id,
                                body=json.dumps(follow_up_request)
                            )
                            
                            follow_up_body = json.loads(follow_up_response['body'].read())
                            
                            if 'content' in follow_up_body:
                                for follow_up_content in follow_up_body['content']:
                                    if follow_up_content['type'] == 'text':
                                        final_text.append(follow_up_content['text'])
                                            
                        except Exception as e:
                            final_text.append(f"Error executing tool {tool_name}: {str(e)}")
                
                return "\n".join(final_text) if final_text else "No response generated"
            else:
                return "No response generated from Bedrock"
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            return f"Bedrock API error ({error_code}): {error_message}"
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