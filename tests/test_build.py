import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from xml.dom import minidom

from beamerweb.cli import inline_svg, main

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo.tex"


class BuildTests(unittest.TestCase):
    def test_svg_references_keep_namespaces_and_are_local_to_page(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "slide.svg"
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" '
                'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="-72 -72 96 54">'
                '<defs><path id="glyph"/><clipPath id="clip"/></defs>'
                '<g data-web-id="formula" clip-path="url(#clip)">'
                '<use xlink:href="#glyph"/></g></svg>'
            )
            result = minidom.parseString(inline_svg(path, 3))
            use = result.getElementsByTagName("use")[0]
            self.assertEqual(use.getAttributeNS("http://www.w3.org/1999/xlink", "href"), "#bw3-glyph")
            group = result.getElementsByTagName("g")[0]
            self.assertEqual(group.getAttribute("clip-path"), "url(#bw3-clip)")
            self.assertEqual(group.getAttribute("data-web-id"), "formula")
            self.assertEqual(result.documentElement.getAttribute("viewBox"), "-72 -72 96 54")

    def test_demo_web_and_pdf(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            dist = root / "web"
            self.assertEqual(main(["build", str(DEMO), "-o", str(dist)]), 0)
            html = (dist / "index.html").read_text()
            self.assertEqual(html.count("<svg "), 4)
            self.assertNotIn("<img", html)
            self.assertIn('data-web-id="vertex-v"', html)
            self.assertNotIn("Static value:", html)
            payload = re.search(r'<script id="bw-metadata"[^>]+>(.*?)</script>', html)[1]
            pages = json.loads(payload)
            self.assertEqual([(page["frame"], page["overlay"]) for page in pages],
                             [(1, 1), (1, 2), (2, 1), (3, 1)])
            self.assertEqual(pages[2]["frameTitle"], "TikZ network")
            self.assertEqual((dist / "deck.js").read_bytes(), DEMO.with_suffix(".js").read_bytes())

            pdf = root / "demo.pdf"
            self.assertEqual(main(["pdf", str(DEMO), "-o", str(pdf)]), 0)
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
            if shutil.which("pdftotext"):
                text = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True)
                self.assertIn("Static value: λ = 0.43", text)
                self.assertIn("Canvas motion demo (web edition).", text)

    def test_rounded_madrid_blocks(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "rounded.tex"
            source.write_text(r"""
\documentclass{beamer}
\usetheme{Madrid}
\begin{document}
\begin{frame}{Madrid}
\begin{block}{Rounded block}
  \webid{marker}{Hello}
\end{block}
\end{frame}
\end{document}
""")
            dist = root / "dist"
            self.assertEqual(main(["build", str(source), "-o", str(dist)]), 0)
            self.assertIn('data-web-id="marker"', (dist / "index.html").read_text())

    def test_plain_beamer_does_not_require_package_directive(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "my slides.tex"
            source.write_text(r"""
\documentclass{beamer}
\begin{document}
\begin{frame}{Visibility and metadata}
\uncover<2->{\webwidget{later}}
\end{frame}
\end{document}
""")
            self.assertEqual(main(["build", str(source), "-o", str(root / "dist")]), 0)
            html = (root / "dist" / "index.html").read_text()
            self.assertIn('visibility="hidden"', html)
            self.assertEqual(html.count('data-web-widget="later"'), 2)
            self.assertIn("Visibility and metadata", html)


if __name__ == "__main__":
    unittest.main()
