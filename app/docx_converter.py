import os, base64, zipfile, mimetypes, shutil, uuid
from lxml import etree
from pdf2docx import Converter
import traceback
import tempfile
import re
from bs4 import BeautifulSoup
import aspose.words as aw

def convert_pdf_to_word_xml(pdf_path: str, file_id: str) -> str:
    docx_filename = f"output/{file_id}.docx"
    unzip_dir = f"output/{file_id}_unzipped"
    output_xml_path = f"output/{file_id}.xml"

    # Convert PDF to DOCX
    cv = Converter(pdf_path)
    cv.convert(docx_filename)
    cv.close()

    # Unzip DOCX
    os.makedirs(unzip_dir, exist_ok=True)
    with zipfile.ZipFile(docx_filename, 'r') as zip_ref:
        zip_ref.extractall(unzip_dir)

    # Build Word-compatible XML
    pkg_package = build_pkg_package(unzip_dir)

    # Save XML
    xml_content = etree.tostring(pkg_package, pretty_print=True, encoding='utf-8')
    xml_declaration = b'<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n'
    processing_instruction = b'<?mso-application progid="Word.Document"?>\n'

    with open(output_xml_path, "wb") as f:
        f.write(xml_declaration + processing_instruction + xml_content)

    # Clean up intermediate files
    shutil.rmtree(unzip_dir)
    os.remove(docx_filename)

    return output_xml_path

def build_pkg_package(input_dir):
    NSMAP = {None: "http://schemas.microsoft.com/office/2006/xmlPackage"}
    pkg_package = etree.Element("{http://schemas.microsoft.com/office/2006/xmlPackage}package", nsmap=NSMAP)

    for root, _, files_in_dir in os.walk(input_dir):
        for file in files_in_dir:
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, input_dir).replace("\\", "/")
            with open(full_path, "rb") as f:
                content = f.read()

            content_type, _ = mimetypes.guess_type(file)
            if not content_type:
                content_type = "application/octet-stream"

            part_elem = etree.SubElement(pkg_package,
                                         "{http://schemas.microsoft.com/office/2006/xmlPackage}part",
                                         name=f"/{relative_path}",
                                         contentType=content_type,
                                         compression="store",
                                         padding="512")

            if file.endswith(".xml") or file.endswith(".rels"):
                try:
                    xml_tree = etree.fromstring(content)
                    xml_data_elem = etree.SubElement(part_elem, "{http://schemas.microsoft.com/office/2006/xmlPackage}xmlData")
                    xml_data_elem.append(xml_tree)
                except Exception:
                    binary_elem = etree.SubElement(part_elem, "{http://schemas.microsoft.com/office/2006/xmlPackage}binaryData")
                    binary_elem.text = base64.b64encode(content).decode('utf-8')
            else:
                binary_elem = etree.SubElement(part_elem, "{http://schemas.microsoft.com/office/2006/xmlPackage}binaryData")
                binary_elem.text = base64.b64encode(content).decode('utf-8')

    return pkg_package

def convert_word_to_html_aspose(word_file_path, output_id):
    """
    Convert Word document to HTML using Aspose.Words library for better conversion quality.
    Returns the HTML content of the body section only.
    """
    try:
        # Output directory
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        # Define output HTML file path
        html_file_path = os.path.join(output_dir, f"{output_id}_aspose.html")
        
        print(f"Converting {word_file_path} to HTML using Aspose.Words")
        
        # Load the Word document
        doc = aw.Document(word_file_path)
        
        # Save as HTML
        doc.save(html_file_path)
        
        print(f"Word document converted to HTML: {html_file_path}")
        
        # Extract body content from the HTML file
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Parse the HTML to extract only the body content
        soup = BeautifulSoup(html_content, 'html.parser')
        body = soup.find('body')
        
        if body:
            # Extract the body content
            body_html = ''.join(str(tag) for tag in body.contents)
            
            # Clean up the HTML content if needed
            # For example, remove any unwanted elements or attributes
            cleaned_body_soup = BeautifulSoup(body_html, 'html.parser')
            
            # Remove any script tags
            for script in cleaned_body_soup.find_all('script'):
                script.decompose()
            
            # Get the cleaned HTML
            body_html = str(cleaned_body_soup)
            
            # Save the body content to a separate file for reference
            body_file_path = os.path.join(output_dir, f"{output_id}_body.html")
            with open(body_file_path, 'w', encoding='utf-8') as f:
                f.write(body_html)
            
            return {
                "html_content": body_html,
                "html_path": body_file_path,
                "full_html_path": html_file_path
            }
        else:
            raise Exception("No body tag found in the HTML output")
        
    except Exception as e:
        print(f"Error in Aspose.Words conversion: {str(e)}")
        traceback.print_exc()
        raise e

def convert_pdf_to_word_xml(pdf_path, file_id):
    """
    Convert PDF to Word XML format (placeholer function - implementation needed).
    """
    # This is a placeholder function
    # In a real implementation, use a library like pdf2docx to convert
    # PDF to Word, then extract the XML from the Word document
    
    # For now, just return a dummy XML file path
    xml_path = f"output/{file_id}.xml"
    with open(xml_path, "w") as f:
        f.write("<xml>PDF content would be here</xml>")
    
    return xml_path
