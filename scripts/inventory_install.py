"""Read-only inventory of the full install; preserve selected data in a CE snapshot.

No executable or game file is modified. A manifest is private because it can
contain an account ID. All inventory outputs remain under .artifacts.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import re
import shutil
from pathlib import Path
from common import ROOT, output_path, sha256, write_json

def classify(relative: Path) -> tuple[bool, str]:
    parts = relative.parts
    if relative.suffix.lower() == '.s14' and any(p in {'0010_KO', '0010_JP'} for p in parts):
        return True, 'SCENARIO_OR_SHARED_DATA'
    if len(parts) == 2 and parts[0] == '0000' and relative.suffix == '.bin':
        return True, 'STATIC_SYSTEM_OR_MAP_DATA'
    if relative.name in {'ReadMe_KO.txt', 'ReadMe.txt'}:
        return True, 'INSTALL_DOCUMENTATION'
    return False, 'NOT_SELECTED_FOR_P0_SNAPSHOT'

def capture(source: Path, manifest: Path, destination: Path) -> dict:
    source = source.resolve(strict=True)
    manifest = manifest.resolve(strict=True)
    destination = output_path(destination)
    if not destination.is_relative_to((ROOT / '.artifacts').resolve()):
        raise ValueError('Private snapshots must stay in .artifacts')
    if source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('Source and snapshot must be independent')
    before_manifest = manifest.read_bytes()
    text = before_manifest.decode('utf-8')
    build = re.search(r'"buildid"\s+"(\d+)"', text)
    if not build:
        raise ValueError('Manifest lacks build ID')
    files = sorted(p for p in source.rglob('*') if p.is_file())
    destination.mkdir(parents=True)
    rows = []
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError('Source symlink outside inventory boundary')
        relative = path.relative_to(source)
        stat = path.stat()
        digest = sha256(path)
        after = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f'Install changed while hashing: {relative}')
        selected, reason = classify(relative)
        with path.open('rb') as stream:
            signature = stream.read(32).hex()
        if selected:
            copy = destination / 'game' / relative
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, copy)
            if sha256(copy) != digest:
                raise RuntimeError(f'Snapshot hash mismatch: {relative}')
        rows.append({'relative_path': relative.as_posix(), 'size_bytes': stat.st_size,
                     'mtime_ns': stat.st_mtime_ns, 'sha256': digest,
                     'prefix_hex': signature, 'preserved': selected, 'reason': reason})
    current = sorted(p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file())
    if current != [r['relative_path'] for r in rows]:
        # Windows path ordering differs from string ordering; compare sets.
        if set(current) != {r['relative_path'] for r in rows}:
            raise RuntimeError('Install file set changed during capture')
    for row in rows:
        stat = (source / row['relative_path']).stat()
        if (stat.st_size, stat.st_mtime_ns) != (row['size_bytes'], row['mtime_ns']):
            raise RuntimeError('Install changed during capture; snapshot is incomplete')
    if manifest.read_bytes() != before_manifest:
        raise RuntimeError('Steam manifest changed during capture')
    (destination / 'appmanifest_872410.acf').write_bytes(before_manifest)
    data = {'inventory_version': 1, 'captured_at': datetime.now(timezone.utc).isoformat(),
            'steam_app_id': 872410, 'steam_build_id': build.group(1),
            'source_root': str(source), 'snapshot_key': f'ce-ko-build-{build.group(1)}',
            'clean_state': 'UNVERIFIED', 'user_report': 'No game data modifications reported',
            'clean_state_note': 'User statement recorded; no official file-hash verification performed',
            'installed_dlc_ids': sorted(set(map(int, re.findall(r'"dlcappid"\s+"(\d+)"', text)))),
            'files': rows, 'total_bytes': sum(r['size_bytes'] for r in rows),
            'preserved_bytes': sum(r['size_bytes'] for r in rows if r['preserved'])}
    write_json(destination / 'inventory.json', data)
    return data

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    data = capture(args.source_root, args.manifest, args.output)
    print(f"Build {data['steam_build_id']}: {len(data['files'])} files, "
          f"{data['preserved_bytes']:,} bytes preserved; full install hashed")

if __name__ == '__main__':
    main()
