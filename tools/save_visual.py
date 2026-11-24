"""Export a source image as a lightweight WebP for a lecture visual slot."""

import argparse
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image


VISUALS = Path(__file__).resolve().parents[1] / 'assets' / 'visuals'
MAX_WIDTH = 720


def check_webp(path):
    with Image.open(path) as image:
        image.load()
        if image.format != 'WEBP' or image.width > MAX_WIDTH:
            raise ValueError(f'Invalid lecture WebP: {path}')


def save_visual(source, destination):
    if source.resolve() == destination.resolve():
        raise ValueError('Source and destination must be different files')
    if destination.exists():
        raise FileExistsError(destination)

    with Image.open(source) as original:
        image = original.convert('RGBA' if original.has_transparency_data else 'RGB')
    if image.width > MAX_WIDTH:
        height = max(1, round(image.height * MAX_WIDTH / image.width))
        image = image.resize((MAX_WIDTH, height), Image.Resampling.LANCZOS)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, suffix='.webp', delete=False) as tmp:
        staging = Path(tmp.name)
    try:
        image.save(staging, format='WEBP', quality=55, method=6)
        check_webp(staging)
        staging.chmod(0o644)
        # Publish without replacing an asset, including during concurrent exports.
        os.link(staging, destination)
    finally:
        staging.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('visual_id')
    parser.add_argument('source', type=Path)
    parser.add_argument('--remove-source', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)+', args.visual_id):
        parser.error('The visual ID must match the corresponding lecture slot')

    destination = save_visual(args.source, VISUALS / f'{args.visual_id}.webp')
    if args.remove_source:
        args.source.unlink()
    print(f'{destination} ({destination.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
