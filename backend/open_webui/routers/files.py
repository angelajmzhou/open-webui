import logging
import os
import uuid
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
    Query,
)
from fastapi.responses import FileResponse, StreamingResponse
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS
from open_webui.models.files import (
    FileForm,
    FileModel,
    FileModelResponse,
    Files,
)
from open_webui.models.knowledge import Knowledges

from open_webui.routers.knowledge import get_knowledge, get_knowledge_list
from open_webui.routers.retrieval import ProcessFileForm, process_file
from open_webui.routers.audio import transcribe
from open_webui.storage.provider import Storage
from open_webui.utils.auth import get_admin_user, get_verified_user
from pydantic import BaseModel

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


router = APIRouter()


############################
# Check if the current user has access to a file through any knowledge bases the user may be in.
############################


def has_access_to_file(
    file_id: Optional[str], access_type: str, user=Depends(get_verified_user)
) -> bool:
    file = Files.get_file_by_id(file_id)
    log.debug(f"Checking if user has {access_type} access to file")

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    has_access = False
    knowledge_base_id = file.meta.get("collection_name") if file.meta else None

    if knowledge_base_id:
        knowledge_bases = Knowledges.get_knowledge_bases_by_user_id(
            user.id, access_type
        )
        for knowledge_base in knowledge_bases:
            if knowledge_base.id == knowledge_base_id:
                has_access = True
                break

    return has_access


############################
# Upload File
############################


@router.post("/", response_model=FileModelResponse)
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_verified_user),
    file_metadata: dict = {},
    process: bool = Query(True),
):
    log.info(f"file.content_type: {file.content_type}")
    try:
        unsanitized_filename = file.filename
        filename = os.path.basename(unsanitized_filename)

        # replace filename with uuid
        id = str(uuid.uuid4())
        name = filename
        filename = f"{id}_{filename}"
        contents, file_path = Storage.upload_file(file.file, filename)

        file_item = Files.insert_new_file(
            user.id,
            FileForm(
                **{
                    "id": id,
                    "filename": name,
                    "path": file_path,
                    "meta": {
                        "name": name,
                        "content_type": file.content_type,
                        "size": len(contents),
                        "data": file_metadata,
                    },
                }
            ),
        )
        if process:
            try:
                if file.content_type in [
                    "audio/mpeg",
                    "audio/wav",
                    "audio/ogg",
                    "audio/x-m4a",
                ]:
                    file_path = Storage.get_file(file_path)
                    result = transcribe(request, file_path)

                    process_file(
                        request,
                        ProcessFileForm(file_id=id, content=result.get("text", "")),
                        user=user,
                    )
                else:
                    process_file(request, ProcessFileForm(file_id=id), user=user)
                file_item = Files.get_file_by_id(id=id)
            except Exception as e:
                log.exception(e)
                log.error(f"Error processing file: {file_item.id}")
                file_item = FileModelResponse(
                    **{
                        **file_item.model_dump(),
                        "error": str(e.detail) if hasattr(e, "detail") else str(e),
                    }
                )

        if file_item:
            return file_item
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error uploading file"),
            )

    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


############################
# List Files
############################


@router.get("/", response_model=list[FileModelResponse])
async def list_files(user=Depends(get_verified_user), content: bool = Query(True)):
    if user.role == "admin":
        files = Files.get_files()
    else:
        files = Files.get_files_by_user_id(user.id)

    if not content:
        for file in files:
            del file.data["content"]

    return files


############################
# Search Files
############################


@router.get("/search", response_model=list[FileModelResponse])
async def search_files(
    filename: str = Query(
        ...,
        description="Filename pattern to search for. Supports wildcards such as '*.txt'",
    ),
    content: bool = Query(True),
    user=Depends(get_verified_user),
):
    """
    Search for files by filename with support for wildcard patterns.
    """
    # Get files according to user role
    if user.role == "admin":
        files = Files.get_files()
    else:
        files = Files.get_files_by_user_id(user.id)

    # Get matching files
    matching_files = [
        file for file in files if fnmatch(file.filename.lower(), filename.lower())
    ]

    if not matching_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No files found matching the pattern.",
        )

    if not content:
        for file in matching_files:
            del file.data["content"]

    return matching_files


############################
# Delete All Files
############################


@router.delete("/all")
async def delete_all_files(user=Depends(get_admin_user)):
    result = Files.delete_all_files()
    if result:
        try:
            Storage.delete_all_files()
        except Exception as e:
            log.exception(e)
            log.error("Error deleting files")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error deleting files"),
            )
        return {"message": "All files deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error deleting files"),
        )


############################
# Get File By Id
############################


@router.get("/{id}", response_model=Optional[FileModel])
async def get_file_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    if (
        file.user_id == user.id
        or user.role == "admin"
        or has_access_to_file(id, "read", user)
    ):
        return file
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# Get File Data Content By Id
############################


@router.get("/{id}/data/content")
async def get_file_data_content_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        file.user_id == user.id
        or user.role == "admin"
        or has_access_to_file(id, "read", user)
    ):
        return {"content": file.data.get("content", "")}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )



############################
# Get File Content By Id
############################


@router.get("/{id}/content")
async def get_file_content_by_id(
    id: str, user=Depends(get_verified_user), attachment: bool = Query(False)
):
    file = Files.get_file_by_id(id)

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        file.user_id == user.id
        or user.role == "admin"
        or has_access_to_file(id, "read", user)
    ):
        try:
            file_path = Storage.get_file(file.path)
            file_path = Path(file_path)

            # Check if the file already exists in the cache
            if file_path.is_file():
                # Handle Unicode filenames
                filename = file.meta.get("name", file.filename)
                encoded_filename = quote(filename)  # RFC5987 encoding

                content_type = file.meta.get("content_type")
                filename = file.meta.get("name", file.filename)
                encoded_filename = quote(filename)
                headers = {}

                # Check if this is a .doc/.docx file that should be converted to PDF
                is_doc_file = (
                    content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or
                    content_type.startswith("application/vnd.openxmlformats-officedocument.wordprocessingml") or
                    content_type == "application/msword" or
                    content_type.startswith("application/vnd.ms-word") or
                    filename.lower().endswith(".docx") or
                    filename.lower().endswith(".doc")
                )

                log.info(f"File: {filename}, Content-Type: {content_type}, is_doc_file: {is_doc_file}, attachment: {attachment}")

                # For .doc/.docx files, check if PDF exists or create it
                if is_doc_file and not attachment:
                    pdf_path = file_path.with_suffix('.pdf')
                    
                    # If PDF doesn't exist or is older than original file, create it
                    if not pdf_path.exists() or pdf_path.stat().st_mtime < file_path.stat().st_mtime:
                        log.info(f"Creating PDF for {filename} at {pdf_path}")
                        try:
                            if filename.lower().endswith('.docx'):
                                try:
                                    import mammoth
                                    from weasyprint import HTML
                                    
                                    log.info(f"Starting mammoth+weasyprint conversion for {filename}")
                                    
                                    # Convert .docx to HTML with formatting
                                    with open(file_path, "rb") as docx_file:
                                        result = mammoth.convert_to_html(docx_file)
                                        html_content = result.value
                                    
                                    log.info(f"Successfully converted {filename} to HTML with mammoth")
                                    
                                    # Convert HTML to PDF with weasyprint
                                    HTML(string=html_content).write_pdf(str(pdf_path))
                                    log.info(f"Successfully converted {filename} to PDF with weasyprint")
                                    
                                except Exception as convert_error:
                                    log.error(f"Failed to convert {filename} with mammoth+weasyprint: {convert_error}")
                                    # Fallback to text extraction method
                                    try:
                                        from fpdf import FPDF
                                        import docx2txt
                                        
                                        text_content = docx2txt.process(str(file_path))
                                        log.info(f"Fallback: Successfully extracted text from {filename}")
                                        
                                        # Clean text of problematic Unicode characters
                                        if text_content:
                                            replacements = {
                                                '…': '...',  # ellipsis
                                                '"': '"',   # left double quotation mark
                                                '"': '"',   # right double quotation mark
                                                ''': "'",   # left single quotation mark
                                                ''': "'",   # right single quotation mark
                                                '–': '-',   # en dash
                                                '—': '-',   # em dash
                                            }
                                            
                                            for unicode_char, ascii_char in replacements.items():
                                                text_content = text_content.replace(unicode_char, ascii_char)
                                            
                                            text_content = text_content.encode('ascii', 'replace').decode('ascii')

                                        # Create PDF with FPDF
                                        pdf = FPDF()
                                        pdf.add_page()
                                        pdf.set_font("Helvetica", size=12)
                                        
                                        lines = text_content.split('\n')
                                        for line in lines:
                                            if len(line) > 80:
                                                words = line.split()
                                                current_line = ""
                                                for word in words:
                                                    if len(current_line + " " + word) <= 80:
                                                        current_line += " " + word if current_line else word
                                                    else:
                                                        if current_line:
                                                            pdf.cell(0, 10, text=current_line, new_x="LMARGIN", new_y="NEXT")
                                                        current_line = word
                                                if current_line:
                                                    pdf.cell(0, 10, text=current_line, new_x="LMARGIN", new_y="NEXT")
                                            else:
                                                pdf.cell(0, 10, text=line, new_x="LMARGIN", new_y="NEXT")

                                        pdf.output(str(pdf_path))
                                        log.info(f"Fallback: Created PDF for {filename} using FPDF")
                                        
                                    except Exception as fallback_error:
                                        log.error(f"Both mammoth+weasyprint and fallback failed for {filename}: {fallback_error}")
                                        raise fallback_error
                            else:
                                # For .doc files, use text extraction method
                                try:
                                    from fpdf import FPDF
                                    import docx2txt
                                    
                                    text_content = docx2txt.process(str(file_path))
                                except:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        text_content = f.read()

                                # Clean text and create PDF (same as fallback above)
                                if text_content:
                                    replacements = {
                                        '…': '...',  # ellipsis
                                        '"': '"',   # left double quotation mark
                                        '"': '"',   # right double quotation mark
                                        ''': "'",   # left single quotation mark
                                        ''': "'",   # right single quotation mark
                                        '–': '-',   # en dash
                                        '—': '-',   # em dash
                                    }
                                    
                                    for unicode_char, ascii_char in replacements.items():
                                        text_content = text_content.replace(unicode_char, ascii_char)
                                    
                                    text_content = text_content.encode('ascii', 'replace').decode('ascii')

                                pdf = FPDF()
                                pdf.add_page()
                                pdf.set_font("Helvetica", size=12)
                                
                                lines = text_content.split('\n')
                                for line in lines:
                                    if len(line) > 80:
                                        words = line.split()
                                        current_line = ""
                                        for word in words:
                                            if len(current_line + " " + word) <= 80:
                                                current_line += " " + word if current_line else word
                                            else:
                                                if current_line:
                                                    pdf.cell(0, 10, text=current_line, new_x="LMARGIN", new_y="NEXT")
                                                current_line = word
                                        if current_line:
                                            pdf.cell(0, 10, text=current_line, new_x="LMARGIN", new_y="NEXT")
                                    else:
                                        pdf.cell(0, 10, text=line, new_x="LMARGIN", new_y="NEXT")

                                pdf.output(str(pdf_path))
                                log.info(f"Created PDF for {filename} using FPDF")
                            
                        except Exception as e:
                            log.exception(e)
                            log.error(f"Failed to convert {filename} to PDF: {e}")
                    
                    if pdf_path.exists():
                        log.info(f"Serving PDF for {filename}: {pdf_path}")
                        headers["Content-Disposition"] = f"inline; filename*=UTF-8''{encoded_filename}"
                        return FileResponse(
                            path=str(pdf_path), 
                            headers=headers, 
                            media_type="application/pdf"
                        )
                    else:
                        log.info(f"PDF not found for {filename}, serving original file")

                if attachment:
                    headers["Content-Disposition"] = (
                        f"attachment; filename*=UTF-8''{encoded_filename}"
                    )
                else:
                    if content_type == "application/pdf" or filename.lower().endswith(
                        ".pdf"
                    ):
                        headers["Content-Disposition"] = (
                            f"inline; filename*=UTF-8''{encoded_filename}"
                        )
                        content_type = "application/pdf"
                    elif content_type.startswith("image/"):
                        headers["Content-Disposition"] = (
                            f"inline; filename*=UTF-8''{encoded_filename}"
                        )
                    elif content_type != "text/plain":
                        headers["Content-Disposition"] = (
                            f"attachment; filename*=UTF-8''{encoded_filename}"
                        )

                log.info(f"Serving original file: {filename}, Content-Type: {content_type}, Headers: {headers}")
                return FileResponse(file_path, headers=headers, media_type=content_type)

            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ERROR_MESSAGES.NOT_FOUND,
                )
        except Exception as e:
            log.exception(e)
            log.error("Error getting file content")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error getting file content"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )



@router.get("/{id}/content/{file_name}")
async def get_file_content_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        file.user_id == user.id
        or user.role == "admin"
        or has_access_to_file(id, "read", user)
    ):
        file_path = file.path

        # Handle Unicode filenames
        filename = file.meta.get("name", file.filename)
        encoded_filename = quote(filename)  # RFC5987 encoding
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }

        if file_path:
            file_path = Storage.get_file(file_path)
            file_path = Path(file_path)

            # Check if the file already exists in the cache
            if file_path.is_file():
                return FileResponse(file_path, headers=headers)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ERROR_MESSAGES.NOT_FOUND,
                )
        else:
            # File path doesn’t exist, return the content as .txt if possible
            file_content = file.content.get("content", "")
            file_name = file.filename

            # Create a generator that encodes the file content
            def generator():
                yield file_content.encode("utf-8")

            return StreamingResponse(
                generator(),
                media_type="text/plain",
                headers=headers,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# Delete File By Id
############################


@router.delete("/{id}")
async def delete_file_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        file.user_id == user.id
        or user.role == "admin"
        or has_access_to_file(id, "write", user)
    ):
        # We should add Chroma cleanup here

        result = Files.delete_file_by_id(id)
        if result:
            try:
                Storage.delete_file(file.path)
            except Exception as e:
                log.exception(e)
                log.error("Error deleting files")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT("Error deleting files"),
                )
            return {"message": "File deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error deleting file"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


