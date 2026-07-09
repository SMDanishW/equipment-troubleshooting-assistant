from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ExtractedImage:
    filename: str
    path: str
    page: int
    content_hash: str
    width: int | None = None
    height: int | None = None
    bytes_size: int | None = None


@dataclass(frozen=True)
class _ImageCandidate:
    image: Any
    image_bytes: bytes
    content_hash: str
    width: int | None
    height: int | None
    mode: str | None
    color_space: str | None
    has_soft_mask: bool


def extract_pdf_images(
    pdf_path: Path,
    output_dir: Path,
    document_id: str,
    min_bytes: int = 4_000,
    min_width: int = 80,
    min_height: int = 80,
) -> list[ExtractedImage]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    seen_hashes: set[str] = set()
    extracted: list[ExtractedImage] = []

    for page_index, page in enumerate(reader.pages, start=1):
        candidates = [_inspect_image_candidate(image) for image in getattr(page, "images", [])]
        for image_index, candidate in enumerate(candidates, start=1):
            image_bytes = candidate.image_bytes
            content_hash = candidate.content_hash
            if content_hash in seen_hashes or len(image_bytes) < min_bytes:
                continue

            width = candidate.width
            height = candidate.height
            if width is not None and height is not None and (width < min_width or height < min_height):
                continue
            if _is_mask_companion(candidate, candidates):
                continue

            seen_hashes.add(content_hash)
            extension = Path(candidate.image.name).suffix.lower() or ".png"
            filename = f"{document_id}_p{page_index}_{image_index}_{uuid4().hex[:8]}{extension}"
            image_path = output_dir / filename
            image_path.write_bytes(image_bytes)
            extracted.append(
                ExtractedImage(
                    filename=filename,
                    path=str(image_path),
                    page=page_index,
                    content_hash=content_hash,
                    width=width,
                    height=height,
                    bytes_size=len(image_bytes),
                )
            )

    return extracted


def _inspect_image_candidate(image: Any) -> _ImageCandidate:
    image_bytes = image.data
    width = getattr(image, "width", None)
    height = getattr(image, "height", None)
    mode = None
    if width is None or height is None or mode is None:
        try:
            from PIL import Image

            with Image.open(BytesIO(image_bytes)) as parsed_image:
                width, height = parsed_image.size
                mode = parsed_image.mode
        except Exception:
            width = None
            height = None

    color_space = None
    has_soft_mask = False
    try:
        image_object = image.indirect_reference.get_object()
        color_space = str(image_object.get("/ColorSpace", ""))
        has_soft_mask = "/SMask" in image_object
    except Exception:
        pass

    return _ImageCandidate(
        image=image,
        image_bytes=image_bytes,
        content_hash=sha256(image_bytes).hexdigest(),
        width=width,
        height=height,
        mode=mode,
        color_space=color_space,
        has_soft_mask=has_soft_mask,
    )


def _is_mask_companion(candidate: _ImageCandidate, page_candidates: list[_ImageCandidate]) -> bool:
    if candidate.has_soft_mask:
        return False
    if candidate.width is None or candidate.height is None:
        return False
    if candidate.mode not in {"1", "L", "LA"} and "DeviceGray" not in (candidate.color_space or ""):
        return False

    for other in page_candidates:
        if other is candidate:
            continue
        if other.width != candidate.width or other.height != candidate.height:
            continue
        if other.has_soft_mask and other.mode in {"RGB", "RGBA", "P"}:
            return True
    return False
