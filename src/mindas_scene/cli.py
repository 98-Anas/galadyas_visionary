"""mindas-scene studio [FILE] | render FILE | still FILE T [T ...]

FILE is a project (.mscene) or a scene script (.py) that defines a Video.
"""

import argparse
import multiprocessing
import sys
from pathlib import Path

from .project import EXTENSION, Project, ProjectError
from .render import QUALITY, load


def _video(path: str):
    if path.endswith(EXTENSION):
        project = Project.load(path)
        if not project.scenes:
            raise ProjectError("The project has no scenes.")
        return project.video(), project.resolve(project.audio)
    return load(path), None


def main(argv=None) -> int:
    multiprocessing.freeze_support()
    p = argparse.ArgumentParser(prog="mindas-scene", description="Make videos from templates or code.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("studio", help="open the desktop app")
    s.add_argument("file", nargs="?")

    r = sub.add_parser("render", help="export a project or scene script to MP4")
    r.add_argument("file")
    r.add_argument("-o", "--out", help="output path (default: media/<name>.mp4)")
    r.add_argument("-q", "--quality", choices=list(QUALITY), default="high")
    r.add_argument("--draft", action="store_true", help="same as --quality draft")
    r.add_argument("--workers", type=int, help="parallel processes (default: all cores)")
    r.add_argument("--audio", help="audio track to mux in (overrides the project's)")

    st = sub.add_parser("still", help="save PNG frames at given times (seconds)")
    st.add_argument("file")
    st.add_argument("times", nargs="+", type=float)
    st.add_argument("-o", "--out-dir", default="media/stills")

    args = p.parse_args(argv)
    if args.command == "studio":
        from .gui.app import main as studio
        return studio([sys.argv[0]] + ([args.file] if args.file else []))
    try:
        video, audio = _video(args.file)
    except (OSError, ProjectError, LookupError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    stem = Path(args.file).stem
    if args.command == "render":
        out = args.out or f"media/{stem}{'_draft' if args.draft else ''}.mp4"
        print(video.render(out, workers=args.workers, quality="draft" if args.draft else args.quality,
                           audio=args.audio or audio))
    else:
        for path in video.stills(args.times, args.out_dir, stem=stem):
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
