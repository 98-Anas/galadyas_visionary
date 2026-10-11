"""mindas-scene render FILE | mindas-scene still FILE T [T ...]"""

import argparse
from pathlib import Path

from .render import load


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mindas-scene", description="Render videos written as code.")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("render", help="encode a scene file to MP4")
    r.add_argument("file")
    r.add_argument("-o", "--out", help="output path (default: media/<name>.mp4)")
    r.add_argument("--draft", action="store_true", help="1x resolution, 15 fps: fast previews")
    r.add_argument("--workers", type=int, help="parallel processes (default: all cores)")
    r.add_argument("--audio", help="audio track to mux in")

    s = sub.add_parser("still", help="save PNG frames at given times")
    s.add_argument("file")
    s.add_argument("times", nargs="+", type=float)
    s.add_argument("-o", "--out-dir", default="media/stills")

    args = p.parse_args(argv)
    video = load(args.file)
    if args.command == "render":
        out = args.out or f"media/{Path(args.file).stem}{'_draft' if args.draft else ''}.mp4"
        print(video.render(out, workers=args.workers, draft=args.draft, audio=args.audio))
    else:
        for path in video.stills(args.times, args.out_dir):
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
