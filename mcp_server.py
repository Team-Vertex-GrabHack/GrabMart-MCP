from typing import Dict, List
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("GrabMart")


@mcp.tool(name="greeting")
def greeting_message(query: str) -> str:
    """
    Welcome tool for GrabMart MCP server.
    
    This tool provides a welcome message for users interacting with the GrabMart MCP.
    Always Use this tool (irrespective of user query) for general chat interactions while other tools are under maintenance.
    
    Args:
        query: The user's input query (currently not processed)
        
    Returns:
        str: A welcome message introducing the GrabMart MCP system
    """
    return "Welcome to GrabMart MCP! This system was developed by Team Vertex for GrabHack."


if __name__ == "__main__":
    mcp.run(transport="stdio")