from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
from app.pdf_processor import process_pdf
from app.docx_converter import convert_pdf_to_word_xml

app = FastAPI()

# Configure CORS with more explicit settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # Cache preflight requests for 24 hours
)

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.get("/")
async def root():
    return {"status": "Converter API is running"}

@app.options("/upload-pdf-crop/")
async def options_upload_pdf_crop():
    return {}

@app.options("/upload-pdf-to-xml/")
async def options_upload_pdf_to_xml():
    return {}

@app.options("/upload-pdf-to-html/")
async def options_upload_pdf_to_html():
    return {}

@app.post("/upload-pdf-crop/")
async def upload_pdf_crop(id: str = Form(...), file: UploadFile = File(...), api_url: str = Form(None)):
    try:
        pdf_path = os.path.join(OUTPUT_DIR, f"{id}.pdf")

        with open(pdf_path, "wb") as f:
            f.write(await file.read())

        result = process_pdf(pdf_path, id)
        
        # If API URL is provided, send the HTML to the admin API
        if api_url:
            try:
                async with httpx.AsyncClient() as client:
                    upload_url = f"{api_url}/papers/{id}/upload-html"
                    response = await client.post(
                        upload_url,
                        json={"html_content": result["html_content"]}
                    )
                    
                    if response.status_code != 200:
                        print(f"Failed to upload HTML to admin API: {response.text}")
            except Exception as e:
                print(f"Error sending HTML to admin API: {str(e)}")
        
        return FileResponse(result["html_path"], media_type="text/html", filename="cropped_output.html")
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.post("/upload-pdf-to-html/")
async def upload_pdf_to_html(
    id: str = Form(...), 
    file: UploadFile = File(...), 
    api_url: str = Form(None)
):
    """
    Convert PDF to HTML and optionally send it to the admin API.
    If api_url is provided, the HTML content will be sent to {api_url}/papers/{id}/upload-html
    """
    try:
        pdf_path = os.path.join(OUTPUT_DIR, f"{id}.pdf")

        with open(pdf_path, "wb") as f:
            f.write(await file.read())

        result = process_pdf(pdf_path, id)
        
        # If API URL is provided, send the HTML to the admin API
        api_response = None
        if api_url:
            try:
                async with httpx.AsyncClient() as client:
                    upload_url = f"{api_url}/papers/{id}/upload-html"
                    api_response = await client.post(
                        upload_url,
                        json={"html_content": result["html_content"]}
                    )
                    
                    api_response = {
                        "status_code": api_response.status_code,
                        "admin_api_response": api_response.text
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
                "metadata": result["metadata"],
                "file_path": result["html_path"],
                "admin_api_upload": api_response
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/get-html/{file_id}")
async def get_html(file_id: str):
    """
    Get the HTML content of a previously processed PDF.
    This would normally come from a database, but for demo purposes,
    we're reading from the file system.
    """
    html_path = f"output/{file_id}.html"
    
    if not os.path.exists(html_path):
        return JSONResponse(
            status_code=404,
            content={"error": f"HTML for ID {file_id} not found"}
        )
    
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content)

@app.post("/upload-pdf-to-xml/")
async def upload_pdf_to_xml(id: str = Form(...), file: UploadFile = File(...)):
    try:
        pdf_path = os.path.join(OUTPUT_DIR, f"{id}.pdf")

        with open(pdf_path, "wb") as f:
            f.write(await file.read())

        xml_path = convert_pdf_to_word_xml(pdf_path, id)
        return FileResponse(xml_path, media_type="application/xml", filename="word_compatible_output.xml")
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        ) 