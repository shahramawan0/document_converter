import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

# Fix the import paths - using relative imports
from .pdf_processor import process_pdf, process_word_to_html
from .docx_converter import convert_pdf_to_word_xml

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import base64

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

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.options("/upload-pdf-crop/")
async def options_upload_pdf_crop():
    return {}

@app.options("/upload-pdf-to-xml/")
async def options_upload_pdf_to_xml():
    return {}

@app.options("/upload-pdf-to-html/")
async def options_upload_pdf_to_html():
    return {}

@app.options("/upload-word-to-html/")
async def options_upload_word_to_html():
    return {}

@app.options("/upload-word-aspose/")
async def options_upload_word_aspose():
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

@app.post("/upload-word-to-html/")
async def upload_word_to_html(
    id: str = Form(...), 
    file: UploadFile = File(...), 
    api_url: str = Form(None)
):
    """
    Convert Word file directly to HTML and optionally send it to the admin API.
    This gives better results than PDF-to-HTML conversion.
    If api_url is provided, the HTML content will be sent to {api_url}/papers/{id}/upload-html
    """
    try:
        print(f"Received Word file upload: filename={file.filename}, content_type={file.content_type}, size={file.size}")
        
        # Validate file mime type and extension
        valid_mime_types = [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
            "application/msword"
        ]
        
        file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        is_valid_extension = file_ext in ['docx', 'doc']
        is_valid_mime = file.content_type in valid_mime_types
        
        if not (is_valid_extension or is_valid_mime):
            print(f"Invalid file: ext={file_ext}, mime={file.content_type}")
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid file type. Please upload a .docx or .doc file. Got: {file.content_type}, extension: {file_ext}"}
            )
            
        # Save the uploaded Word file with sanitized path
        safe_id = "".join(c for c in id if c.isalnum() or c in ['-', '_']).strip()
        if not safe_id:
            safe_id = "document"
            
        word_path = os.path.join(OUTPUT_DIR, f"{safe_id}.docx")
        
        print(f"Saving file to {word_path}")
        file_content = await file.read()
        if not file_content:
            return JSONResponse(
                status_code=400,
                content={"error": "Uploaded file is empty"}
            )
            
        with open(word_path, "wb") as f:
            f.write(file_content)
            
        # Verify the file was saved properly
        if not os.path.exists(word_path):
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to save the uploaded file"}
            )
            
        file_size = os.path.getsize(word_path)
        print(f"File saved successfully. Size: {file_size} bytes")
        
        if file_size == 0:
            return JSONResponse(
                status_code=400,
                content={"error": "Saved file is empty"}
            )

        # Process the Word file to HTML
        print(f"Starting Word-to-HTML conversion for {word_path}")
        result = process_word_to_html(word_path, safe_id)
        print(f"Conversion completed. HTML content length: {len(result['html_content'])}")
        
        # Collect image data from output directory if available
        images = []
        image_dir = f"output/{safe_id}_images"
        if os.path.exists(image_dir):
            print(f"Collecting images from {image_dir}")
            for img_file in os.listdir(image_dir):
                if img_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    img_path = os.path.join(image_dir, img_file)
                    try:
                        with open(img_path, 'rb') as f:
                            img_data = f.read()
                            img_format = img_file.split('.')[-1].lower()
                            mime_type = f"image/{img_format}"
                            if img_format == 'jpg':
                                mime_type = "image/jpeg"
                                
                            img_b64 = base64.b64encode(img_data).decode('utf-8')
                            images.append({
                                "filename": img_file,
                                "data": img_b64,
                                "mime_type": mime_type
                            })
                    except Exception as img_err:
                        print(f"Error reading image file {img_file}: {str(img_err)}")
        
        print(f"Collected {len(images)} images")
        
        # If API URL is provided, send the HTML to the admin API
        api_response = None
        if api_url:
            try:
                print(f"Sending HTML content to admin API at {api_url}/papers/{id}/upload-html")
                async with httpx.AsyncClient() as client:
                    upload_url = f"{api_url}/papers/{id}/upload-html"
                    api_result = await client.post(
                        upload_url,
                        json={
                            "html_content": result["html_content"],
                            "images": images  # Include the images in the request
                        }
                    )
                    
                    api_response = {
                        "status_code": api_result.status_code,
                        "admin_api_response": api_result.text
                    }
                    print(f"Admin API response: {api_response}")
            except Exception as e:
                error_msg = f"Error sending HTML to admin API: {str(e)}"
                print(error_msg)
                api_response = {
                    "status": "error",
                    "message": error_msg
                }
        
        # Return the HTML content, metadata, and API response
        return JSONResponse(
            content={
                "status": "success",
                "html_content": result["html_content"],
                "metadata": result["metadata"],
                "file_path": result["html_path"],
                "images": images,  # Include images in the response
                "admin_api_upload": api_response
            }
        )
    except Exception as e:
        error_msg = f"Error processing Word file: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        
        return JSONResponse(
            status_code=500,
            content={
                "error": error_msg,
                "traceback": traceback.format_exc(),
                "file_info": {
                    "filename": getattr(file, "filename", "unknown"),
                    "content_type": getattr(file, "content_type", "unknown"),
                    "size": getattr(file, "size", "unknown")
                }
            }
        )

@app.post("/use-example-docx/")
async def use_example_docx(
    id: str = Form(...),
    api_url: str = Form(None)
):
    """
    Use the example Word file from the admin folder instead of uploading a new one.
    This is useful for testing the conversion with a known file.
    """
    try:
        print(f"Using example Word file for paper ID: {id}")
        
        # Path to the example Word file
        example_file_path = "../../admin/Paper-2426172717-2025-05-05.docx"
        
        # Check if the file exists
        if not os.path.exists(example_file_path):
            alternative_paths = [
                "../admin/Paper-2426172717-2025-05-05.docx",
                "/d:/fspublishers/admin/Paper-2426172717-2025-05-05.docx",
                "D:/fspublishers/admin/Paper-2426172717-2025-05-05.docx",
            ]
            
            for alt_path in alternative_paths:
                if os.path.exists(alt_path):
                    example_file_path = alt_path
                    print(f"Found example file at alternative path: {alt_path}")
                    break
            else:
                return JSONResponse(
                    status_code=404,
                    content={"error": "Example Word file not found. Please ensure the file is in the admin folder."}
                )
        
        # Create a safe ID for the file
        safe_id = "".join(c for c in id if c.isalnum() or c in ['-', '_']).strip()
        if not safe_id:
            safe_id = "example_document"
        
        # Copy the example file to the output directory
        output_file_path = os.path.join(OUTPUT_DIR, f"{safe_id}.docx")
        shutil.copy2(example_file_path, output_file_path)
        
        print(f"Copied example file to {output_file_path}")
        
        # Process the Word file to HTML
        result = process_word_to_html(output_file_path, safe_id)
        
        # Collect image data from output directory if available
        images = []
        image_dir = f"output/{safe_id}_images"
        if os.path.exists(image_dir):
            print(f"Collecting images from {image_dir}")
            for img_file in os.listdir(image_dir):
                if img_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    img_path = os.path.join(image_dir, img_file)
                    try:
                        with open(img_path, 'rb') as f:
                            img_data = f.read()
                            img_format = img_file.split('.')[-1].lower()
                            mime_type = f"image/{img_format}"
                            if img_format == 'jpg':
                                mime_type = "image/jpeg"
                                
                            img_b64 = base64.b64encode(img_data).decode('utf-8')
                            images.append({
                                "filename": img_file,
                                "data": img_b64,
                                "mime_type": mime_type
                            })
                    except Exception as img_err:
                        print(f"Error reading image file {img_file}: {str(img_err)}")
        
        print(f"Collected {len(images)} images")
        
        # If API URL is provided, send the HTML to the admin API
        api_response = None
        if api_url:
            try:
                print(f"Sending HTML to admin API: {api_url}/papers/{id}/upload-html")
                async with httpx.AsyncClient() as client:
                    upload_url = f"{api_url}/papers/{id}/upload-html"
                    api_result = await client.post(
                        upload_url,
                        json={
                            "html_content": result["html_content"],
                            "images": images  # Include the images in the request
                        }
                    )
                    
                    api_response = {
                        "status_code": api_result.status_code,
                        "admin_api_response": api_result.text
                    }
                    print(f"Admin API response: {api_response}")
            except Exception as e:
                error_msg = f"Error sending HTML to admin API: {str(e)}"
                print(error_msg)
                api_response = {
                    "status": "error",
                    "message": error_msg
                }
        
        # Return the HTML content, metadata, and API response
        return JSONResponse(
            content={
                "status": "success",
                "html_content": result["html_content"],
                "metadata": result["metadata"],
                "file_path": result["html_path"],
                "images": images,  # Include images in the response
                "admin_api_upload": api_response
            }
        )
    except Exception as e:
        error_msg = f"Error processing example Word file: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        
        return JSONResponse(
            status_code=500,
            content={
                "error": error_msg,
                "traceback": traceback.format_exc()
            }
        )

@app.post("/upload-word-aspose/")
async def upload_word_aspose(
    id: str = Form(...), 
    file: UploadFile = File(...), 
    api_url: str = Form(None)
):
    """
    Convert Word file to HTML using Aspose.Words for better quality conversion.
    If api_url is provided, the HTML content will be sent to {api_url}/papers/{id}/upload-html
    """
    try:
        print(f"Received Word file for Aspose conversion: filename={file.filename}, content_type={file.content_type}")
        
        # Validate file mime type and extension
        valid_mime_types = [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
            "application/msword",
            "application/octet-stream"  # Some systems might use this generic type
        ]
        
        file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        is_valid_extension = file_ext in ['docx', 'doc']
        
        if not is_valid_extension:
            print(f"Invalid file extension: {file_ext}")
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid file type. Please upload a .docx or .doc file. Got extension: {file_ext}"}
            )
            
        # Save the uploaded Word file with sanitized path
        safe_id = "".join(c for c in id if c.isalnum() or c in ['-', '_']).strip()
        if not safe_id:
            safe_id = "document"
            
        word_path = os.path.join(OUTPUT_DIR, f"{safe_id}.docx")
        
        print(f"Saving file to {word_path}")
        file_content = await file.read()
        if not file_content:
            return JSONResponse(
                status_code=400,
                content={"error": "Uploaded file is empty"}
            )
            
        with open(word_path, "wb") as f:
            f.write(file_content)
            
        # Verify the file was saved properly
        if not os.path.exists(word_path):
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to save the uploaded file"}
            )
            
        file_size = os.path.getsize(word_path)
        print(f"File saved successfully. Size: {file_size} bytes")
        
        if file_size == 0:
            return JSONResponse(
                status_code=400,
                content={"error": "Saved file is empty"}
            )

        # Convert Word to HTML using Aspose.Words from the pdf_processor module
        print(f"Starting Word-to-HTML conversion with Aspose.Words for {word_path}")
        conversion_result = process_word_to_html(word_path, safe_id)
        print(f"Conversion completed. HTML content length: {len(conversion_result['html_content'])}")
        
        # If API URL is provided, send the HTML to the admin API
        api_response = None
        if api_url:
            try:
                print(f"Sending HTML content to admin API at {api_url}/papers/{id}/upload-html")
                async with httpx.AsyncClient() as client:
                    upload_url = f"{api_url}/papers/{id}/upload-html"
                    api_result = await client.post(
                        upload_url,
                        json={"html_content": conversion_result["html_content"]}
                    )
                    
                    api_response = {
                        "status_code": api_result.status_code,
                        "admin_api_response": api_result.text
                    }
                    print(f"Admin API response: {api_response}")
            except Exception as e:
                error_msg = f"Error sending HTML to admin API: {str(e)}"
                print(error_msg)
                api_response = {
                    "status": "error",
                    "message": error_msg
                }
        
        # Return the HTML content and API response
        return JSONResponse(
            content={
                "status": "success",
                "html_content": conversion_result["html_content"],
                "file_path": conversion_result["html_path"],
                "metadata": conversion_result.get("metadata", {"title": safe_id}),
                "admin_api_upload": api_response
            }
        )
    except Exception as e:
        error_msg = f"Error processing Word file with Aspose: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        
        return JSONResponse(
            status_code=500,
            content={
                "error": error_msg,
                "traceback": traceback.format_exc(),
                "file_info": {
                    "filename": getattr(file, "filename", "unknown"),
                    "content_type": getattr(file, "content_type", "unknown"),
                }
            }
        ) 