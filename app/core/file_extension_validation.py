from app.constants.content_type import ALLOWED_EXTENSIONS


class FileExtensionError(Exception):
    pass


def _validate_file_extension(file_extension: str):
    allowed_extension = ALLOWED_EXTENSIONS

    if file_extension.lower() not in allowed_extension:
        raise FileExtensionError(
            f"file extension '{file_extension}' is not allowed."
            f"allowed extensions: {sorted(allowed_extension)}"
        )

    return file_extension.lower()


def is_valid_file_extension(
    extension: str,
) -> bool:
    try:
        _validate_file_extension(file_extension=extension)
        return True
    except (FileExtensionError, ValueError):
        return False
