import base64


def decode_b64_str(b64_str: str) -> bytes:
    """
    Tool to decode a base64 encoded string, optionally handling data URI format.

    This tool first checks if the input str is a data URI (starts with "data:").
    If URI, it extracts the base64 data portion. It then ensures the string is
    correctly padded before attempting to decode it into a bytes object.

    Args:
        b64_str (str): The base64 encoded string.

    Returns:
        (bytes): The decoded content as a bytes object.

    Raises:
        Exception: If the base64 decoding fails (eg. due to invalid characters).
    """
    if isinstance(b64_str, str) and b64_str.startswith("data:"):
        parts = b64_str.split(",", 1)

        if len(parts) == 2:
            b64_data = parts[1]

    b64_str = b64_str.strip()
    padding = len(b64_str) % 4

    if padding:
        b64_str += "=" * (4 - padding)

    try:
        return base64.b64decode(b64_str)
    
    except Exception as error:
        raise

