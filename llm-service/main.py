from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import httpx
from typing import List

app = FastAPI(title="LLM Service with MCP")

# MCP server configuration
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8090")

class GenerationRequest(BaseModel):
    prompt: str
    context: List[str]
    max_tokens: int = 512
    temperature: float = 0.7

@app.post("/generate")
async def generate_text(request: GenerationRequest):
    # Format prompt with context
    formatted_prompt = f"""
    Answer the question based on the following context from Red Hat documentation:
    
    Context:
    {' '.join(request.context)}
    
    Question: {request.prompt}
    
    Answer:
    """
    
    # Format request for MCP server
    mcp_request = {
        "prompt": formatted_prompt,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature
    }
    
    # Send request to MCP server
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MCP_SERVER_URL}/v1/completions",
            json=mcp_request
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="MCP server error")
        
        result = response.json()
    
    # Extract answer
    generated_text = result["choices"][0]["text"]
    answer = generated_text.split("Answer:")[1].strip() if "Answer:" in generated_text else generated_text
    
    return {"answer": answer}
