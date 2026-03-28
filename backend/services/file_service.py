import os
import uuid
from fastapi import UploadFile, HTTPException


ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png"]
ALLOWED_PDF_TYPE = "application/pdf"

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def save_file(file: UploadFile, folder: str, allowed_types):

    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")

    contents = file.file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    file_path = os.path.join("uploads", folder, unique_filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    return file_path