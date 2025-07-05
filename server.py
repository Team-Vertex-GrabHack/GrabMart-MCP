import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mcp_client import MCPReActAgent

# Global MCP client instance
mcp_client_instance: Optional[MCPReActAgent] = None

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
    mcp_client_instance = MCPReActAgent()
    
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
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
    """Process a query using the MCP client with timeout"""
    global mcp_client_instance
    
    if not mcp_client_instance or not mcp_client_instance.session:
        raise HTTPException(status_code=503, detail="MCP client not connected")
    
    try:
        # Set timeout to 5 minutes (300 seconds) for long-running queries
        timeout_seconds = 300
        response = await asyncio.wait_for(
            mcp_client_instance.process_query(request.query),
            timeout=timeout_seconds
        )
        return QueryResponse(response=response)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408, 
            detail=f"Request timed out after {timeout_seconds} seconds. The query is taking too long to process."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)