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
import copy

# Configure CloudConvert with your API key
cloudconvert.configure(api_key='eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwianRpIjoiOTg4ODZiYTE5MjE2MWUzYTY2ZDA4YTdhZDZiOTY1ZDQzNmNkYjA3MjhjYTJkYjljNDNlMzIwZDRlYzk5Y2YyY2JhNzlkNTVjMWRmMzA2MzkiLCJpYXQiOjE3NDc1NTE5OTYuMDM2NjA2LCJuYmYiOjE3NDc1NTE5OTYuMDM2NjA4LCJleHAiOjQ5MDMyMjU1OTYuMDMxMzAyLCJzdWIiOiI3MTk2MDI2NCIsInNjb3BlcyI6WyJ1c2VyLnJlYWQiLCJ1c2VyLndyaXRlIiwidGFzay5yZWFkIiwidGFzay53cml0ZSIsIndlYmhvb2sucmVhZCIsIndlYmhvb2sud3JpdGUiLCJwcmVzZXQucmVhZCIsInByZXNldC53cml0ZSJdfQ.dvOkvDdIbhi17PEErZiTTmNvrZ92_oUClfZxvyaeEysuZtBoaSBNTnmB1S_I_4uO0Xk8OfNJOmHnzT7y1LC7aGiOtHJEm8VezmQU4CdlP6jmYNHLtIAYXERQ-ipSp7OBM07weL2lIIz8cctsiow_ZN6hAntVdB_Z4Am6KuqbWUdIXhY005dpAHA29V2-bBbRC7OkQQPtm0q8rfc8EArsXf1vIyjQBFikT3Rf4FzHHHXw5lO4g7POLACNcS1qzubAMdxkrHEjWQjUBg2DKvPQBoDR-7mzm8rdKsDQfRDq1IrE2bsGLwy78e5s8cDtu_myu4P0pDWZhSnsGG2tkd4JwnoBHEwaq-ZuxPkJvPUrdRaOMGbMNtOnNUx8enTa4EiHR-g6f26po6vJfLiGALfz8Rhc9oELFtPfoQ3z8DYaqeiqb26DGdrbGlWoyjTU-V4PyXdiGcJKdCRE8DdEGE6bF30ElhyxQaQTnHbUSRDbMYkMM7bu07FuXl3XDl6byoFBFR_s-jIy3GA8mKVR8C-5S5RaqzawzpvJpahsuCPP-XL2Xr5MAPhMrDkWSR6b6ygwx1eloz7UzziyFxWVu5hFhdI2HPLGZxOkBM4IBP9l4XBlfv1NFYYYjqzmoZQYf5TjsIQZXhGqmlINhZDgN158khx2Tqu_Hv87H9196O3uGz0')

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

def trim_html_to_keywords(html_content):
    """
    Trims HTML content to keep only the Keywords section and all content after it.
    Returns the trimmed HTML content.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the Keywords section by looking for text that starts with keyword variations
    keyword_patterns = [
        r'^keywords:',
        r'^key words:',
        r'^key word:',
        r'^keyword:',
        r'^key terms:',
    ]
    
    # Compile regex patterns for case-insensitive matching
    regex_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in keyword_patterns]
    
    # Track if we've found the keywords section
    keywords_found = False
    keyword_element = None
    
    # Check different possible elements that might contain Keywords
    for element in soup.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        if element.text:
            text = element.text.strip()
            for pattern in regex_patterns:
                if pattern.match(text):
                    keywords_found = True
                    keyword_element = element
                    print(f"Found keywords section: '{text}'")
                    break
            if keywords_found:
                break
    
    if not keywords_found or not keyword_element:
        print("Warning: Keywords section not found in HTML")
        return html_content  # Return original content if no keywords found
    
    # Create a new soup with the same structure, keeping the html and body tags
    new_soup = BeautifulSoup('<html><head></head><body></body></html>', 'html.parser')
    
    # Copy any head content
    if soup.head:
        for item in soup.head.contents:
            new_soup.head.append(copy.copy(item))
    
    # Find the parent that contains the keyword element
    container = None
    for parent in keyword_element.parents:
        if parent.name == 'body':
            container = parent
            break
    
    if not container:
        container = soup.body or soup
    
    # Keep track of whether we've reached the keywords section
    reached_keywords = False
    
    # Copy all elements from the body, but only start adding them once we've reached the keywords
    for element in container.contents:
        # Check if this element or any of its children contains the keyword element
        # NavigableString objects don't have find_all method, so check the type first
        if keyword_element == element or (hasattr(element, 'find_all') and keyword_element in element.find_all()):
            reached_keywords = True
        
        # If we've reached the keywords section, add this element
        if reached_keywords:
            new_soup.body.append(copy.copy(element))
    
    print(f"Trimmed HTML to start from Keywords section")
    return str(new_soup)

def process_word_to_html(word_path: str, file_id: str) -> dict:
    """
    Process a Word file and convert it to HTML using CloudConvert API.
    Returns a dict with the HTML content and path. All images are embedded as base64.
    """
    try:
        # Generate output path
        os.makedirs("output", exist_ok=True)
        html_file_path = f"output/{file_id}.html"
        images_dir = f"output/{file_id}_images"
        os.makedirs(images_dir, exist_ok=True)
        
        print(f"Starting CloudConvert job for {word_path}")
        
        # Create a job using the CloudConvert API to convert Word to HTML
        job = cloudconvert.Job.create(payload={
            "tasks": {
                # First task: Upload the Word file
                "upload-file": {
                    "operation": "import/upload"
                },
                # Second task: Convert to HTML
                "convert-file": {
                    "operation": "convert",
                    "input": "upload-file",
                    "output_format": "html",
                    "engine": "office",  # Use Office engine for better conversion
                    "options": {
                        "embed_images": True,  # Embed images as data URIs
                    }
                },
                # Third task: Export the converted file
                "export-file": {
                    "operation": "export/url",
                    "input": "convert-file"
                }
            }
        })
        
        # Get the upload task from the job
        upload_task_id = None
        for task in job["tasks"]:
            if task["operation"] == "import/upload":
                upload_task_id = task["id"]
                break
        
        if not upload_task_id:
            raise ValueError("Failed to find upload task in the job")
        
        # Get the upload task details
        upload_task = cloudconvert.Task.find(id=upload_task_id)
        
        # Upload the Word file
        print(f"Uploading {word_path} to CloudConvert")
        cloudconvert.Task.upload(file_name=word_path, task=upload_task)
        
        # Wait for the job to complete
        print("Waiting for conversion to complete...")
        export_task_id = None
        for task in job["tasks"]:
            if task["operation"] == "export/url":
                export_task_id = task["id"]
                break
        
        if not export_task_id:
            raise ValueError("Failed to find export task in the job")
        
        # Wait for the export task to complete
        export_task = cloudconvert.Task.wait(id=export_task_id)
        
        # Check if the task was successful
        if export_task["status"] != "finished":
            raise ValueError(f"Export task failed with status: {export_task['status']}")
        
        # Download the converted HTML file and any associated files
        files = export_task.get("result", {}).get("files", [])
        if not files:
            raise ValueError("No files found in the export task result")
        
        # Download all files from the export (to capture any image files)
        downloaded_files = []
        for file_info in files:
            file_url = file_info.get("url")
            filename = file_info.get("filename")
            
            if not file_url or not filename:
                        continue
                    
            # Download the file
            file_path = os.path.join("output", filename)
            print(f"Downloading file: {filename}")
            
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            
            # Save the file
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            downloaded_files.append(file_path)
            
            # Extract ZIP files if needed (CloudConvert sometimes returns them)
            if filename.endswith('.zip'):
                try:
                    import zipfile
                    print(f"Extracting ZIP file: {file_path}")
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall("output")
                    
                    # Check for HTML file in the extracted files
                    for extracted_file in zip_ref.namelist():
                        if extracted_file.endswith('.html'):
                            html_file_path = os.path.join("output", extracted_file)
                            print(f"Found HTML file in ZIP: {html_file_path}")
                except Exception as zip_err:
                    print(f"Error extracting ZIP file: {str(zip_err)}")
        
        # Find the main HTML file from downloaded files
        html_file = None
        for file_path in downloaded_files:
            if file_path.endswith('.html'):
                html_file = file_path
                html_file_path = file_path
                break
        
        if not html_file:
            # If we couldn't find an HTML file in the downloaded files, use the default path
            html_file = html_file_path
        
        # Read the HTML content
        with open(html_file_path, "r", encoding="utf-8") as f:
            original_html_content = f.read()
        
        # Pre-process HTML to identify and mark patterns specific to CloudConvert output
        preprocessed_html = fix_html_for_website(original_html_content, file_id)
        
        # Create a directory to store extracted images
        extracted_images_dir = os.path.join(images_dir, "extracted")
        os.makedirs(extracted_images_dir, exist_ok=True)
        
        # Process the HTML with BeautifulSoup to ensure all images are embedded
        soup = BeautifulSoup(preprocessed_html, 'html.parser')
        
        # Track all images for extraction and embedding
        images = []
        external_image_count = 0
        embedded_image_count = 0
        download_image_count = 0
        cloud_convert_image_count = 0
        
        print(f"Processing HTML content for images")
        
        # Find all images in the HTML
        for img_idx, img in enumerate(soup.find_all('img')):
            src = img.get('src', '')
            
            # This handles CloudConvert-specific patterns marked during preprocessing
            needs_base64 = img.get('data-needs-base64') == 'true'
            original_src = img.get('data-original-src', '')
            
            if needs_base64 and original_src:
                src = original_src
                cloud_convert_image_count += 1
                print(f"Found CloudConvert image pattern: {src}")
            
            print(f"Found image #{img_idx+1}: {src[:50]}{'...' if len(src) > 50 else ''}")
            
            # Skip empty sources
            if not src:
                print(f"  - Skipping empty src")
                        continue
            
            # If the image is already a data URI, just record it
            if src.startswith('data:'):
                embedded_image_count += 1
                print(f"  - Already embedded as data URI")
                
                try:
                    # Extract metadata from the data URI
                    parts = src.split(',', 1)
                    if len(parts) != 2:
                        print(f"  - Invalid data URI format")
                                    continue
                                    
                    header = parts[0]
                    img_data = parts[1]
                    
                    # Get the mime type
                    mime_match = re.search(r'data:(.*?);', header)
                    if not mime_match:
                        print(f"  - Could not extract mime type from data URI")
                        mime_type = "image/jpeg"  # Default
                                else:
                        mime_type = mime_match.group(1)
                    
                    # Determine format from mime type
                    if mime_type == "image/jpeg" or mime_type == "image/jpg":
                        img_format = "jpg"
                    elif mime_type == "image/png":
                        img_format = "png"
                    elif mime_type == "image/gif":
                        img_format = "gif"
                    elif mime_type == "image/svg+xml":
                        img_format = "svg"
                            else:
                        img_format = "jpg"  # Default
                    
                    # Add to our images list
                    images.append({
                        "filename": f"image_{embedded_image_count}.{img_format}",
                        "data": img_data,  # Already base64 encoded
                        "mime_type": mime_type
                    })
                    
                    # Also save the image to disk for reference
                    try:
                        img_binary = base64.b64decode(img_data)
                        img_path = os.path.join(extracted_images_dir, f"image_{embedded_image_count}.{img_format}")
                        with open(img_path, 'wb') as img_file:
                            img_file.write(img_binary)
                        print(f"  - Saved embedded image to {img_path}")
                    except Exception as save_err:
                        print(f"  - Error saving embedded image: {str(save_err)}")
                    
                except Exception as parse_err:
                    print(f"  - Error parsing data URI: {str(parse_err)}")
                    
            else:
                # This is an external image URL or relative path
                external_image_count += 1
                
                # Check if this is a CloudConvert pattern (file_id_files/imageXXX.jpg)
                is_cloud_convert_pattern = False
                if f"{file_id}_files/" in src or "_files/" in src:
                    is_cloud_convert_pattern = True
                    print(f"  - CloudConvert image pattern detected: {src}")
                else:
                    print(f"  - External image (will attempt to embed): {src}")
                
                # For CloudConvert patterns, use special pattern matching to find the file
                if is_cloud_convert_pattern:
                    local_image_path = find_image_file(src, file_id, html_file_path)
                    if local_image_path:
                        print(f"  - Found CloudConvert image at: {local_image_path}")
                    else:
                        # If we couldn't find the file exactly, try alternative approaches
                        # 1. Look for the bare filename in known directories
                        basename = os.path.basename(src)
                        for search_dir in [os.path.dirname(html_file_path), images_dir, 
                                          os.path.join(images_dir, "extracted")]:
                            if os.path.exists(os.path.join(search_dir, basename)):
                                local_image_path = os.path.join(search_dir, basename)
                                print(f"  - Found image by basename in {search_dir}: {basename}")
                                break
                else:
                    # Check if it's a relative path to a local file (non-CloudConvert pattern)
                    local_image_path = None
                    if not (src.startswith('http://') or src.startswith('https://')):
                        # Try various approaches to find the local file
                        potential_paths = [
                            src,  # As-is
                            os.path.join(os.path.dirname(html_file_path), src),  # Relative to HTML
                            os.path.join(images_dir, os.path.basename(src)),  # In images dir
                            os.path.join("output", os.path.basename(src)),  # In output dir
                        ]
                        
                        for path in potential_paths:
                            if os.path.exists(path):
                                local_image_path = path
                                print(f"  - Found local image at {local_image_path}")
                                break
                
                # Process the image once we've located it or determined we need to download it
                if local_image_path:
                    # We found the image locally, encode it
                    data_uri, base64_data, mime_type = encode_image_to_base64(local_image_path)
                    if data_uri:
                        img['src'] = data_uri  # Replace the src with data URI
                        print(f"  - Successfully embedded local image")
                        
                        # Add to our images list
                        img_format = local_image_path.split('.')[-1].lower()
                        images.append({
                            "filename": f"local_image_{external_image_count}.{img_format}",
                            "data": base64_data,
                            "mime_type": mime_type
                        })
                    else:
                        print(f"  - Failed to encode local image")
                else:
                    # Need to download from URL
                    download_image_count += 1
                    print(f"  - Downloading image from URL")
                    data_uri, base64_data, mime_type = download_image_and_convert_to_base64(src)
                    if data_uri:
                        img['src'] = data_uri  # Replace with data URI
                        print(f"  - Successfully downloaded and embedded image")
                        
                        # Try to determine format from mime type
                        if mime_type == "image/jpeg" or mime_type == "image/jpg":
                            img_format = "jpg"
                        elif mime_type == "image/png":
                            img_format = "png"
                        elif mime_type == "image/gif":
                            img_format = "gif"
                        else:
                            img_format = "jpg"  # Default
                        
                        # Add to our images list
                        images.append({
                            "filename": f"downloaded_image_{download_image_count}.{img_format}",
                            "data": base64_data,
                            "mime_type": mime_type
                        })
                        
                        # Also save the downloaded image for reference
                        try:
                            img_binary = base64.b64decode(base64_data)
                            img_path = os.path.join(extracted_images_dir, f"downloaded_image_{download_image_count}.{img_format}")
                            with open(img_path, 'wb') as img_file:
                                img_file.write(img_binary)
                            print(f"  - Saved downloaded image to {img_path}")
                        except Exception as save_err:
                            print(f"  - Error saving downloaded image: {str(save_err)}")
                    else:
                        print(f"  - Failed to download and embed image")
            
            # Always remove our temporary attributes
            if img.has_attr('data-needs-base64'):
                del img['data-needs-base64']
            if img.has_attr('data-original-src'):
                del img['data-original-src']
        
        # Get the final HTML with all images embedded
        final_html = str(soup)
        
        # Trim the HTML to keep only Keywords and content after it
        final_html = trim_html_to_keywords(final_html)
        
        # Verify that all images in the final HTML are using data URLs
        verify_soup = BeautifulSoup(final_html, 'html.parser')
        non_embedded_images = []
        for img in verify_soup.find_all('img'):
            src = img.get('src', '')
            if src and not src.startswith('data:'):
                non_embedded_images.append(src)
                print(f"Warning: Found non-embedded image after processing: {src}")
        
        if non_embedded_images:
            print(f"Warning: {len(non_embedded_images)} images could not be embedded:")
            for img_src in non_embedded_images:
                print(f"  - {img_src}")
        else:
            print("All images successfully embedded as data URIs")
            
        print(f"Successfully converted Word to HTML: {html_file_path}")
        print(f"Found and processed {len(soup.find_all('img'))} images:")
        print(f"  - {embedded_image_count} were already embedded")
        print(f"  - {external_image_count} were external (local or remote)")
        print(f"  - {cloud_convert_image_count} were from CloudConvert '_files/' pattern")
        print(f"  - {download_image_count} needed to be downloaded")
        
        # Save the final HTML with embedded images
        final_html_path = f"output/{file_id}_embedded.html"
        with open(final_html_path, "w", encoding="utf-8") as f:
            f.write(final_html)
        
        return {
            "html_content": final_html,  # Return the updated HTML with all images embedded and trimmed to keywords
            "html_path": final_html_path,
            "metadata": {"title": file_id},
            "images": images  # We still include the images array for backward compatibility
        }
    except Exception as e:
        # Handle errors
        error_msg = f"Error in Word to HTML conversion: {str(e)}"
        print(error_msg)
        traceback_info = traceback.format_exc()
        print(f"Traceback: {traceback_info}")
        
        # Create simple HTML with error message
        error_html = f"""
        <div class="pdf-content">
            <h1>Error Converting Word File</h1>
            <p>{error_msg}</p>
        </div>
        """
        
        return {
            "html_content": error_html,
            "html_path": "",
            "metadata": {"title": "Error"},
            "images": []
        } 