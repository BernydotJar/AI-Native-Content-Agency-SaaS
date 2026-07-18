from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Tuple, Union


_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class SkillCreationError(ValueError):
    pass


class UnsafeSkillPathError(SkillCreationError):
    pass


class SkillAlreadyExistsError(SkillCreationError):
    pass


@dataclass(frozen=True)
class SkillDocument:
    slug: str
    path: Path
    title: str
    description: str
    instructions: Tuple[str, ...]
    sha256: str
    overwritten: bool


class DynamicSkillCreator:
    """Create deterministic Markdown skill drafts inside one explicit root.

    The creator accepts a flat slug instead of a caller-supplied path. It refuses
    traversal, absolute paths, control characters, symlink escapes, and existing
    destinations unless `overwrite=True` is explicitly supplied.
    """

    def __init__(self, root: Union[str, Path]) -> None:
        raw_root = Path(root).expanduser()
        try:
            raw_root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise SkillCreationError(
                "skill root could not be initialized as a directory"
            ) from error
        self.root = raw_root.resolve(strict=True)
        if not self.root.is_dir():
            raise SkillCreationError("skill root must be a directory")

    def create(
        self,
        slug: str,
        title: str,
        description: str,
        instructions: Sequence[str],
        overwrite: bool = False,
    ) -> SkillDocument:
        normalized_slug = self._validate_slug(slug)
        normalized_title = self._validate_text(title, "title", 120)
        normalized_description = self._validate_text(
            description, "description", 500
        )
        normalized_instructions = self._validate_instructions(instructions)
        destination = self._safe_destination(normalized_slug)
        existed = destination.exists() or destination.is_symlink()
        if existed and not overwrite:
            raise SkillAlreadyExistsError(
                "skill already exists: {}".format(destination.name)
            )

        markdown = self._render(
            normalized_slug,
            normalized_title,
            normalized_description,
            normalized_instructions,
        )
        if overwrite:
            self._atomic_replace(destination, markdown)
        else:
            self._exclusive_create(destination, markdown)
        digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        return SkillDocument(
            slug=normalized_slug,
            path=destination,
            title=normalized_title,
            description=normalized_description,
            instructions=normalized_instructions,
            sha256=digest,
            overwritten=existed,
        )

    def _safe_destination(self, slug: str) -> Path:
        candidate = self.root / "{}.md".format(slug)
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(self.root)
        except ValueError as error:
            raise UnsafeSkillPathError("skill path escapes the configured root") from error
        if candidate.parent.resolve(strict=True) != self.root:
            raise UnsafeSkillPathError("skill parent is outside the configured root")
        return candidate

    @staticmethod
    def _validate_slug(slug: str) -> str:
        if not isinstance(slug, str) or not _SLUG_PATTERN.fullmatch(slug):
            raise UnsafeSkillPathError(
                "slug must match [a-z0-9][a-z0-9_-]{0,63}; paths are not accepted"
            )
        return slug

    @staticmethod
    def _validate_text(value: str, field: str, maximum_length: int) -> str:
        if not isinstance(value, str):
            raise SkillCreationError("{} must be a string".format(field))
        if _CONTROL_CHARACTER_PATTERN.search(value):
            raise SkillCreationError("{} contains control characters".format(field))
        normalized = " ".join(value.split())
        if not normalized:
            raise SkillCreationError("{} must not be empty".format(field))
        if len(normalized) > maximum_length:
            raise SkillCreationError(
                "{} must not exceed {} characters".format(field, maximum_length)
            )
        return normalized

    @classmethod
    def _validate_instructions(cls, instructions: Sequence[str]) -> Tuple[str, ...]:
        if isinstance(instructions, (str, bytes)):
            raise SkillCreationError("instructions must be a sequence of strings")
        values = tuple(instructions)
        if not values or len(values) > 50:
            raise SkillCreationError("instructions must contain between 1 and 50 items")
        return tuple(
            cls._validate_text(value, "instruction", 2000) for value in values
        )

    @staticmethod
    def _render(
        slug: str,
        title: str,
        description: str,
        instructions: Tuple[str, ...],
    ) -> str:
        lines = [
            "---",
            "name: {}".format(json.dumps(slug, ensure_ascii=False)),
            "title: {}".format(json.dumps(title, ensure_ascii=False)),
            "description: {}".format(json.dumps(description, ensure_ascii=False)),
            "generated_by: agency_runtime.DynamicSkillCreator",
            "sandbox: true",
            "---",
            "",
            "# {}".format(title),
            "",
            description,
            "",
            "## Instructions",
            "",
        ]
        lines.extend(
            "{}. {}".format(index, instruction)
            for index, instruction in enumerate(instructions, start=1)
        )
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _exclusive_create(destination: Path, markdown: str) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            descriptor = os.open(str(destination), flags, 0o600)
        except FileExistsError as error:
            raise SkillAlreadyExistsError(
                "skill already exists: {}".format(destination.name)
            ) from error
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(markdown)
            handle.flush()
            os.fsync(handle.fileno())

    def _atomic_replace(self, destination: Path, markdown: str) -> None:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=".skill-draft-",
                suffix=".tmp",
                dir=str(self.root),
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(markdown)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(destination))
            temporary_path = None
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
