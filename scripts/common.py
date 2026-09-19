"""Filesystem boundaries and deterministic artifacts for CE tools."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT.parent / '001-sam14-db'

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def output_path(value: str | Path, *, must_not_exist: bool = True) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to(ROOT) or path.is_relative_to(LEGACY.resolve()):
        raise ValueError('Outputs must remain inside the independent CE project')
    if path.is_relative_to((ROOT / '.git').resolve()):
        raise ValueError('Git metadata is not an output directory')
    if path == (ROOT / 'db/sam14.db').resolve():
        raise ValueError('Service DB cannot be written by build/analysis tools')
    if must_not_exist and path.exists():
        raise FileExistsError(f'Refusing to overwrite {path.name}')
    return path

def write_json(path: Path, data: object) -> None:
    path = output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
