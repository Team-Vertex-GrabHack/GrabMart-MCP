import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from mcp_client import MCPClient

# Global MCP client instance
mcp_client_instance: Optional[MCPClient] = None

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: str
    status: str = "success"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifecycle of the MCP client"""
    global mcp_client_instance
    
    # Get server script path from command line args
    if len(sys.argv) < 2:
        print("Usage: python server.py m")
        sys.exit(1)
    
    server_script_path = sys.argv[1]
    
    # Initialize and connect MCP client
    print("Initializing MCP client...")
    mcp_client_instance = MCPClient()
    
    try:
        await mcp_client_instance.connect_to_server(server_script_path)
        print("MCP client connected successfully!")
        yield
    except Exception as e:
        print(f"Failed to connect MCP client: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if mcp_client_instance:
            await mcp_client_instance.cleanup()
            print("MCP client cleaned up")

app = FastAPI(
    title="MCP Client API",
    description="FastAPI server that processes queries using MCP client",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "MCP Client API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global mcp_client_instance
    if mcp_client_instance and mcp_client_instance.session:
        return {"status": "healthy", "mcp_connected": True}
    return {"status": "unhealthy", "mcp_connected": False}

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process a query using the MCP client"""
    global mcp_client_instance
    
    if not mcp_client_instance or not mcp_client_instance.session:
        raise HTTPException(status_code=503, detail="MCP client not connected")
    
    try:
        response = await mcp_client_instance.process_query(request.query)
        return QueryResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)