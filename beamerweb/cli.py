"""Build a PDF or a local, self-contained directory of SVG slide assets."""

import argparse
from ctypes.util import find_library
from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from xml.dom import minidom
from xml.parsers.expat import ExpatError

from jinja2 import Environment, FileSystemLoader, TemplateError

ROOT = Path(__file__).resolve().parent
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
UNCLOSED_GROUP = "missing closing tag(s)"
FRAME_RANGE = re.compile(r"\\beamer@framepages\s*\{(\d+)\}\{(\d+)\}")
URL_REF = re.compile(r"url\(\s*(['\"]?)#([^\s)'\"]+)\1\s*\)")


def run(command, cwd, env=None):
    result = subprocess.run(
        command, cwd=cwd, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, errors="replace", check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{command[0]} exited with {result.returncode}\n{result.stdout}")
    return result.stdout


def compile_tex(source, work, engine, web, pgf_driver="dvisvgm"):
    env = dict(os.environ, TMPDIR=str(work), TMP=str(work), TEMP=str(work))
    env["TEXINPUTS"] = os.pathsep.join((str(ROOT / "tex"), env.get("TEXINPUTS", ""), ""))
    entry = "./" + source.name
    if web:
        if any(character in source.name for character in "%{}\\"):
            raise ValueError("The TeX filename cannot contain %, braces, or backslashes.")
        entry = (
            r"\def\BeamerWebBuild{1}"
            r"\PassOptionsToPackage{dvisvgm}{graphicx,xcolor,hyperref}"
            rf"\def\pgfsysdriver{{pgfsys-{pgf_driver}.def}}"
            r"\AddToHook{begindocument/before}{\RequirePackage{beamerweb}}"
            r"\input{\detokenize{" + source.name + "}}"
        )

    engine_args = ["-no-pdf"] if web and engine == "xelatex" else []
    command = [
        engine, *engine_args, "-no-shell-escape", "-halt-on-error",
        "-interaction=nonstopmode", "-file-line-error", "-jobname=deck",
        f"-output-directory={work}", entry,
    ]
    for _ in range(2):
        run(command, source.parent, env)


def page_metadata(work, count):
    nav = work / "deck.nav"
    frames = FRAME_RANGE.findall(nav.read_text(errors="replace")) if nav.exists() else []
    title_file = work / "deck.bwtitles"
    titles = title_file.read_text(errors="replace").splitlines() if title_file.exists() else []
    ranges = {}
    for index, (first, last) in enumerate(frames, start=1):
        start, end = int(first), int(last)
        for page in range(start, min(end, count) + 1):
            ranges[page] = (index, page - start + 1)
    if len(ranges) != count:
        print("Warning: Beamer navigation does not describe every physical page.", file=sys.stderr)
    return [
        {
            "physicalPage": page,
            "frame": ranges.get(page, (None, None))[0],
            "overlay": ranges.get(page, (None, None))[1],
            "frameTitle": titles[page - 1] if page <= len(titles) else "",
        }
        for page in range(1, count + 1)
    ]


def inline_svg(path, page):
    doc = minidom.parseString(path.read_bytes())
    root = doc.documentElement
    if doc.doctype or root.namespaceURI != SVG_NS or root.localName != "svg":
        raise ValueError(f"{path.name}: expected an SVG document without a DOCTYPE")
    if not root.getAttribute("viewBox"):
        raise ValueError(f"{path.name}: missing SVG viewBox")
    elements = [root, *root.getElementsByTagName("*")]
    ids = {}
    for node in elements:
        if node.hasAttribute("id"):
            original = node.getAttribute("id")
            if original in ids:
                raise ValueError(f"{path.name}: duplicate SVG id {original!r}")
            ids[original] = f"bw{page}-{original}"
            node.setAttribute("id", ids[original])

    for node in elements:
        for attr in list(node.attributes.values()):
            value = attr.value
            if attr.localName == "href" and attr.namespaceURI in (None, XLINK_NS):
                if value.startswith("#") and value[1:] in ids:
                    attr.value = "#" + ids[value[1:]]
            elif "url(" in value:
                attr.value = URL_REF.sub(
                    lambda match: f"url(#{ids[match[2]]})" if match[2] in ids else match[0], value
                )
    root.setAttribute("preserveAspectRatio", "xMidYMid meet")
    return root.toxml()


def make_html(source, work, pages, placement, production):
    templates = Environment(
        loader=FileSystemLoader([Path.cwd() / "_templates", ROOT / "templates"]),
        autoescape=True,
    )
    return templates.get_template("index.html.j2").render(
        title=source.stem,
        slides=[inline_svg(path, page) for page, path in enumerate(pages, 1)],
        metadata=page_metadata(work, len(pages)),
        placement=placement,
        production=production,
    )


def build(args):
    source = args.source.resolve(strict=True)
    web = args.action != "pdf"
    engine = args.engine or ("latex" if web else "pdflatex")
    root = (Path.cwd() / "_build").resolve()
    output = args.output or (Path("html") if web else Path("pdf") / source.with_suffix(".pdf").name)
    if not output.is_absolute() and output.parts[:1] != ("_build",):
        output = root / output
    output = output.resolve()
    intermediates = root / "intermediate"
    if output == root or not output.is_relative_to(root) or output.is_relative_to(intermediates):
        raise ValueError("Output must be under _build and outside _build/intermediate.")

    # Isolate TeX jobs for inputs with the same filename and for different engines.
    job_key = sha256(os.fsencode(source)).hexdigest()[:16]
    work = intermediates / ("web" if web else "pdf") / engine / f"{source.stem}-{job_key}"
    work.mkdir(parents=True, exist_ok=True)
    for pattern in ("deck.*", "slide-*.svg"):
        for path in work.glob(pattern):
            path.unlink()
    compile_tex(source, work, engine, web)
    if not web:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / "deck.pdf", output)
        return output
    suffix = "xdv" if engine == "xelatex" else "dvi"
    converter = args.dvisvgm.expanduser().absolute() if args.dvisvgm else os.environ.get("DVISVGM", "dvisvgm")
    conversion_command = [
        converter, "--page=1-", "--bbox=papersize", "--no-fonts",
        f"--output={work / 'slide-%p.svg'}", str(work / f"deck.{suffix}"),
    ]
    env = dict(os.environ, TMPDIR=str(work), TMP=str(work), TEMP=str(work))
    if "--embed-bitmaps" in run([converter, "--help"], source.parent, env):
        conversion_command.insert(1, "--embed-bitmaps")
    try:
        conversion = run(conversion_command, source.parent, env)
    except RuntimeError as error:
        if UNCLOSED_GROUP not in str(error):
            raise
        conversion = str(error)

    # Older dvisvgm versions report this error with a successful exit status.
    if UNCLOSED_GROUP in conversion:
        if engine == "xelatex":
            raise RuntimeError(conversion)
        print("Retrying with the PGF dvips driver after an unclosed SVG group.", file=sys.stderr)
        for page in work.glob("slide-*.svg"):
            page.unlink()
        # Some dvisvgm releases look for libgs.so without a version suffix.
        if "LIBGS" not in env:
            ghostscript = find_library("gs")
            if ghostscript:
                env["LIBGS"] = ghostscript
        compile_tex(source, work, engine, web=True, pgf_driver="dvips")
        conversion = run(conversion_command, source.parent, env)
        if UNCLOSED_GROUP in conversion:
            raise RuntimeError(conversion)
        if "PostScript specials ignored" in conversion:
            raise RuntimeError("The PGF dvips retry needs Ghostscript. Set LIBGS to its shared library.\n"
                               + conversion)
    pages = sorted(work.glob("slide-*.svg"), key=lambda path: int(path.stem.split("-")[1]))
    if not pages:
        raise RuntimeError(f"dvisvgm produced no SVG pages\n{conversion}")
    if re.search(r"(?im)^.*(?:error|warning):", conversion):
        print(conversion, file=sys.stderr)
    document = make_html(source, work, pages, args.placement, args.production)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("runtime.js", "runtime.css"):
        shutil.copyfile(ROOT / "runtime" / name, output / name)
    for ext, asset in (("js", args.js), ("css", args.css)):
        target = output / f"deck.{ext}"
        sidecar = asset or source.with_suffix(f".{ext}")
        if sidecar.is_file() or asset:
            if sidecar.resolve() != target.resolve():
                shutil.copyfile(sidecar, target)
        else:
            target.write_text("", encoding="utf-8")
    (output / "index.html").write_text(document, encoding="utf-8")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(prog="beamerweb")
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("pdf", "build", "serve"):
        command = commands.add_parser(action)
        command.add_argument("source", type=Path)
        command.add_argument("-o", "--output", type=Path, help="output path under _build")
        engines = ("pdflatex", "lualatex", "xelatex") if action == "pdf" else ("latex", "dvilualatex", "xelatex")
        command.add_argument("--engine", choices=engines)
        if action != "pdf":
            command.add_argument("--dvisvgm", type=Path, metavar="PATH",
                                 help="path to dvisvgm, overriding DVISVGM and PATH lookup")
            command.add_argument("--placement", choices=("overlay", "foreign-object"), default="overlay")
            command.add_argument("--js", type=Path)
            command.add_argument("--css", type=Path)
            command.add_argument("--production", action="store_true")
        if action == "serve":
            command.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        output = build(args)
        print(output.resolve(), flush=True)
        if args.action == "serve":
            handler = partial(SimpleHTTPRequestHandler, directory=output)
            with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
                print(f"http://127.0.0.1:{server.server_port}", flush=True)
                server.serve_forever()
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError, ExpatError, TemplateError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0
