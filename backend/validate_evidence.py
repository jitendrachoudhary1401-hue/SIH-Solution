"""Bounded parsing subprocess: no API/database/model credentials are inherited."""
import io
import os
import sys
from pathlib import Path

if os.name != "nt":
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024, 1024))

try:
    content = Path(sys.argv[1]).read_bytes()
    if len(content) > 8 * 1024 * 1024:
        raise ValueError()
    if sys.argv[2] == "application/pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted or len(reader.pages) > 50 or len(reader.pages) == 0:
            raise ValueError()
    else:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 15000000
        import warnings
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        image = Image.open(io.BytesIO(content))
        if image.width * image.height > 15000000:
            raise ValueError()
        image.verify()
    sys.exit(0)
except Exception:
    sys.exit(1)
