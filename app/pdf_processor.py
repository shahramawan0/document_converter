import os
import traceback
import base64
from bs4 import BeautifulSoup
import cloudconvert
import requests
import time
import tempfile
import shutil
import re
import mimetypes

# Configure CloudConvert with your API key
cloudconvert.configure(api_key='eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwianRpIjoiMzU2YmE5OGU2YmUwYWRjYWNhNTc4ZWFkYTM3MGUwYzc0OWI2NjlkMDc0YTE5YTA5MmVjOGRhNzYwOWY2ODQzZjQxN2NiMzRlMTMxMTNmNjkiLCJpYXQiOjE3NDc1NTMyOTYuMzI3NTUzLCJuYmYiOjE3NDc1NTMyOTYuMzI3NTU0LCJleHAiOjQ5MDMyMjY4OTYuMzIzNDk4LCJzdWIiOiI3MTk2MDI2NCIsInNjb3BlcyI6WyJ1c2VyLnJlYWQiLCJ1c2VyLndyaXRlIiwidGFzay5yZWFkIiwidGFzay53cml0ZSIsIndlYmhvb2sucmVhZCIsIndlYmhvb2sud3JpdGUiLCJwcmVzZXQucmVhZCIsInByZXNldC53cml0ZSJdfQ.qTo0dqqU4PYEfIegobPTfnJTMFGPzjAPQsz2uW0DnjOGcRG-GoK-oexFMph9kNHIA-FjiEChjCG88cIsjHaZfOsfH5b3U-hlQkq2ZSp_wK1IN20fY6rb3Nk_hjp1rhDbZ1Nqm9rIOpFCsA0SrT0g7BkehRu1yopZmr7gZMTfN4bmD5Yy7OONNCIKi3x-WE75EePlZJ0pRN8B997PtAqUVfM_IoDaqA6MA1_cmvDYSYopy0zH8u8At5tx8j6A7NEvBW7QjUkK9jezdhU6p4w8mIXdHQtnvdbrWIDSMQnQHwRRPLTZYvgY23vGyv2EWaq73-Y1x1zZUw5o4r60L6ntH3OP0CFd2-GZKZTb-bPXU4bAXX1lLgVMQUFvk1zgY2mj6bb3JXCwucHNizTzYDoN5MvblH_lVOxyGtbdf09I89x7zrN1m2z5D7dRD9V5HNhQNYSX35fpI8oFnlLzl2BcQEUWMvKWFGyoDzum44ZRZjcM6PL-Gd62IeYtH4eHg2gn5EZacw6IAar7y-2rlftZOhnq3VHmt8ybZS_IpKY6X-AHU4SuMeOHdlVsUNxBdWZZUQMclw8_yQWf-plVdhPs3PWJ7eo6_gynHkQscN18eQATX6molzcheo44ZD2I81ypSLuXXUUl3vJAe5e0flEma4nF6hl1nO23zYXkzLLXd3A')

def process_pdf(pdf_path: str, file_id: str) -> dict:
    """
    Process a PDF file and convert it to HTML.
    This function is kept for compatibility but will return an error message.
    """
    error_html = """
    <div class="pdf-content">
        <h1>PDF Conversion Not Supported</h1>
        <p>This version only supports Word to HTML conversion.</p>
                </div>
    """
    
    return {
        "html_content": error_html,
        "html_path": "",
        "metadata": {"title": "Error", "authors": "", "abstract": "PDF conversion not supported"}
    }

def encode_image_to_base64(image_path):
    """
    Encodes an image file to a base64 data URI
    """
    try:
        with open(image_path, 'rb') as img_file:
            img_data = img_file.read()
            
            # Get the MIME type based on file extension
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type:
                # Default to jpeg if we can't determine
                extension = os.path.splitext(image_path)[1].lower()
                if extension == '.jpg' or extension == '.jpeg':
                    mime_type = 'image/jpeg'
                elif extension == '.png':
                    mime_type = 'image/png'
                elif extension == '.gif':
                    mime_type = 'image/gif'
                elif extension == '.svg':
                    mime_type = 'image/svg+xml'
                else:
                    mime_type = 'image/jpeg'  # Default
            
            # Encode to base64
            base64_data = base64.b64encode(img_data).decode('utf-8')
            return f"data:{mime_type};base64,{base64_data}", base64_data, mime_type
    except Exception as e:
        print(f"Error encoding image {image_path}: {str(e)}")
        return None, None, None

def download_image_and_convert_to_base64(image_url, timeout=30):
    """
    Download an image from a URL and convert it to a base64 data URI
    """
    try:
        response = requests.get(image_url, timeout=timeout)
        response.raise_for_status()
        
        # Get content type from headers or guess based on URL
        content_type = response.headers.get('Content-Type')
        if not content_type or not content_type.startswith('image/'):
            # Try to guess from URL
            if image_url.lower().endswith('.jpg') or image_url.lower().endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif image_url.lower().endswith('.png'):
                content_type = 'image/png'
            elif image_url.lower().endswith('.gif'):
                content_type = 'image/gif'
            elif image_url.lower().endswith('.svg'):
                content_type = 'image/svg+xml'
            else:
                content_type = 'image/jpeg'  # Default to JPEG
        
        # Convert to base64
        base64_data = base64.b64encode(response.content).decode('utf-8')
        return f"data:{content_type};base64,{base64_data}", base64_data, content_type
    except Exception as e:
        print(f"Error downloading image from {image_url}: {str(e)}")
        return None, None, None

def find_image_file(image_relpath, file_id, html_file_path):
    """
    Find the actual image file location from a relative path pattern
    like '42305_files/image001.jpg'
    """
    # Extract just the filename
    filename = os.path.basename(image_relpath)
    
    # Common patterns in CloudConvert output
    files_dir = f"{file_id}_files"
    
    # Places to look for the file
    potential_places = [
        # Standard CloudConvert output folder
        os.path.join(os.path.dirname(html_file_path), files_dir, filename),
        os.path.join(os.path.dirname(html_file_path), filename),
        # Our own image directory
        os.path.join(f"output/{file_id}_images", filename),
        # Try subfolders in the images directory
        *[os.path.join(f"output/{file_id}_images", subfolder, filename) 
          for subfolder in ['extracted', 'media', 'images']]
    ]
    
    # Also check for variations of the filename (some converters change names)
    basename, ext = os.path.splitext(filename)
    # Look for files matching the pattern 'image001' regardless of extension
    basename_pattern = re.match(r'(image\d+)', basename)
    if basename_pattern:
        base_name_only = basename_pattern.group(1)
        for dirpath in [os.path.dirname(html_file_path), f"output/{file_id}_images", f"output"]:
            if os.path.exists(dirpath):
                for file in os.listdir(dirpath):
                    if base_name_only in file:
                        potential_places.append(os.path.join(dirpath, file))
    
    # Check each potential location
    for path in potential_places:
        if os.path.exists(path):
            return path
    
    return None

def fix_html_for_website(html_content, file_id):
    """
    Fix various issues in the HTML content to ensure it displays properly on the website
    """
    # Check for and fix "_files/" references which are common in Word to HTML conversions
    soup = BeautifulSoup(html_content, 'html.parser')
    
    files_pattern = re.compile(rf'{file_id}_files/|_files/|files/')
    
    # Fix image sources
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if files_pattern.search(src):
            # This matches our pattern - mark for replacement
            img['data-original-src'] = src
            img['data-needs-base64'] = 'true'
    
    return str(soup)

def process_word_to_html(word_path: str, file_id: str) -> dict:
    """
    Process a Word file and convert it to HTML using CloudConvert API.
    Returns a dict with the HTML content, focusing only on the essential parts.
    """
    try:
        # Make sure output directory exists
        os.makedirs("output", exist_ok=True)
        
        # Create a job using the CloudConvert API
        job = cloudconvert.Job.create(payload={
            "tasks": {
                "upload-file": {
                    "operation": "import/upload"
                },
                "convert-file": {
                    "operation": "convert",
                    "input": "upload-file",
                    "output_format": "html",
                    "engine": "office",
                    "options": {
                        "embed_images": True
                    }
                },
                "export-file": {
                    "operation": "export/url",
                    "input": "convert-file"
                }
            }
        })
        
        # Get the upload task ID
        upload_task_id = next((task["id"] for task in job["tasks"] if task["operation"] == "import/upload"), None)
        if not upload_task_id:
            raise ValueError("Failed to find upload task")
        
        # Get the upload task and upload the file
        upload_task = cloudconvert.Task.find(id=upload_task_id)
        cloudconvert.Task.upload(file_name=word_path, task=upload_task)
        
        # Wait for the job to complete
        export_task_id = next((task["id"] for task in job["tasks"] if task["operation"] == "export/url"), None)
        if not export_task_id:
            raise ValueError("Failed to find export task")
        
        # Wait for the export task to complete
        export_task = cloudconvert.Task.wait(id=export_task_id)
        
        # Check if the task was successful
        if export_task["status"] != "finished":
            raise ValueError(f"Export task failed with status: {export_task['status']}")
        
        # Get the result files
        files = export_task.get("result", {}).get("files", [])
        if not files:
            raise ValueError("No files found in the export task result")
        
        # Download the HTML content
        html_content = ""
        for file_info in files:
            file_url = file_info.get("url")
            filename = file_info.get("filename")
            
            if not file_url or not filename:
                continue
                
            if filename.endswith('.html'):
                response = requests.get(file_url)
                response.raise_for_status()
                html_content = response.text
                break
        
        if not html_content:
            raise ValueError("No HTML content found in the result files")
        
        # Process HTML to extract only the content after Keywords
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the Keywords section
        keywords_tag = None
        for tag in soup.find_all(['p', 'div', 'span']):
            if tag.text and 'Keywords:' in tag.text:
                keywords_tag = tag
                break
        
        # If Keywords section found, keep only what comes after it
        if keywords_tag:
            # Find the parent container
            current = keywords_tag
            while current.parent and current.parent.name != 'body' and current.parent.name != 'html':
                current = current.parent
                
            # Create a new document with only content after keywords
            new_soup = BeautifulSoup('<html><body></body></html>', 'html.parser')
            
            # Get all content that comes after the keywords section
            found_keywords = False
            keep_content = []
            
            for element in soup.body.contents:
                if element == current:
                    found_keywords = True
                elif found_keywords:
                    keep_content.append(element)
            
            # Add the content after keywords to the new document
            for element in keep_content:
                new_soup.body.append(element)
                
            final_html = str(new_soup)
        else:
            # If no keywords section found, return the original HTML
            final_html = html_content
        
        # Save the final HTML
        final_html_path = f"output/{file_id}_embedded.html"
        with open(final_html_path, "w", encoding="utf-8") as f:
            f.write(final_html)
        
        return {
            "html_content": final_html,
            "html_path": final_html_path,
            "metadata": {"title": file_id}
        }
    except Exception as e:
        error_html = f"""
        <div class="pdf-content">
            <h1>Error Converting Word File</h1>
            <p>{str(e)}</p>
        </div>
        """
        
        return {
            "html_content": error_html,
            "html_path": "",
            "metadata": {"title": "Error"}
        } 