import os
from pathlib import Path
from typing import Optional

# Import only essential modules
from .pdf_processor import process_word_to_html

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# Configure CORS with more explicit settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.get("/")
async def root():
    return {"status": "Converter API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.options("/upload-word-to-html/")
async def options_upload_word_to_html():
    return {}

@app.post("/upload-word-to-html/")
async def upload_word_to_html(
    id: str = Form(...), 
    file: UploadFile = File(...), 
    api_url: str = Form(None)
):
    """
    Convert Word file directly to HTML and optionally send it to the admin API.
    If api_url is provided, the HTML content will be sent to {api_url}/papers/{id}/upload-html
    """
    try:
        # Save the uploaded Word file
        safe_id = "".join(c for c in id if c.isalnum() or c in ['-', '_']).strip()
        if not safe_id:
            safe_id = "document"
            
        word_path = os.path.join(OUTPUT_DIR, f"{safe_id}.docx")
        
        file_content = await file.read()
        if not file_content:
            return JSONResponse(
                status_code=400,
                content={"error": "Uploaded file is empty"}
            )
            
        with open(word_path, "wb") as f:
            f.write(file_content)
        
        # Process the Word file to HTML
        result = process_word_to_html(word_path, safe_id)
        
        # If API URL is provided, send the HTML to the admin API
        api_response = None
        if api_url:
            try:
                async with httpx.AsyncClient() as client:
                    upload_url = f"{api_url}/papers/{id}/upload-html"
                    api_result = await client.post(
                        upload_url,
                        json={
                            "html_content": result["html_content"]
                        }
                    )
                    
                    api_response = {
                        "status_code": api_result.status_code,
                        "admin_api_response": api_result.text
                    }
            except Exception as e:
                api_response = {
                    "status": "error",
                    "message": f"Error sending HTML to admin API: {str(e)}"
                }
        
        # Return the HTML content, metadata, and API response
        return JSONResponse(
            content={
                "status": "success",
                "html_content": result["html_content"],
                "metadata": result.get("metadata", {"title": safe_id}),
                "admin_api_upload": api_response
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "file_info": {
                    "filename": getattr(file, "filename", "unknown"),
                    "content_type": getattr(file, "content_type", "unknown"),
                }
            }
        ) 