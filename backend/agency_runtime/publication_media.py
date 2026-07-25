from __future__ import annotations

import hashlib
import io
import warnings
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError


_MAX_MEDIA_BYTES = 8 * 1024 * 1024
_MIN_DIMENSION = 320
_MAX_DIMENSION = 1440
_EXPECTED_CONTENT_TYPE = "image/jpeg"
_EXPECTED_FORMAT = "JPEG"


class PublicationMediaValidationError(ValueError):
    """Raised when uploaded publication media is not safe for the bounded contract."""


@dataclass(frozen=True)
class ValidatedPublicationMedia:
    content_type: str
    byte_size: int
    sha256: str
    width: int
    height: int


def validate_publication_media(
    content: bytes,
    content_type: str,
) -> ValidatedPublicationMedia:
    """Fully decode and validate one immutable Instagram JPEG image.

    INC-022 intentionally supports a single 4:5 JPEG image. The original bytes are
    retained so the hash approved by Greenlight is exactly what the provider fetches.
    """

    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type != _EXPECTED_CONTENT_TYPE:
        raise PublicationMediaValidationError("publication media must be image/jpeg")
    if not content or len(content) > _MAX_MEDIA_BYTES:
        raise PublicationMediaValidationError("publication media byte size is invalid")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as probe:
                if probe.format != _EXPECTED_FORMAT:
                    raise PublicationMediaValidationError(
                        "publication media content does not match image/jpeg"
                    )
                width, height = probe.size
                probe.verify()
            # verify() invalidates the decoder. Reopen and force a complete decode so
            # truncated/corrupt entropy data cannot enter the durable media vault.
            with Image.open(io.BytesIO(content)) as decoded:
                if decoded.format != _EXPECTED_FORMAT or decoded.size != (width, height):
                    raise PublicationMediaValidationError(
                        "publication media decoder result is inconsistent"
                    )
                decoded.load()
    except PublicationMediaValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as error:
        raise PublicationMediaValidationError(
            "publication media is not a valid complete JPEG"
        ) from error

    if not (
        _MIN_DIMENSION <= width <= _MAX_DIMENSION
        and _MIN_DIMENSION <= height <= _MAX_DIMENSION
    ):
        raise PublicationMediaValidationError(
            "publication media dimensions are outside the supported range"
        )
    if width * 5 != height * 4:
        raise PublicationMediaValidationError(
            "publication media must use an exact 4:5 portrait aspect ratio"
        )

    return ValidatedPublicationMedia(
        content_type=_EXPECTED_CONTENT_TYPE,
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        width=width,
        height=height,
    )
