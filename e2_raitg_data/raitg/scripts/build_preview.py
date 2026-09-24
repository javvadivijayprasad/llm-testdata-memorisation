"""Build a plain-class preview PDF from test_case_generation_paper.tex.

The canonical paper uses IEEEtran.cls (required by the venue and matched
to the rest of the research series). IEEEtran.cls is not distributed
with base TeX Live, so for environments that lack it this script
produces a plain `article` class version of the paper for local preview.

The output is `test_case_generation_paper_preview.pdf` — NOT the
canonical submission artefact. Run `compile_all.bat` on the host
(MiKTeX / TeX Live with texlive-publishers) to build the real PDF.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "test_case_generation_paper.tex"
DEST = ROOT / "test_case_generation_paper_preview_v2.tex"


def transform(tex: str) -> str:
    tex = tex.replace(
        r"\documentclass[conference]{IEEEtran}",
        r"\documentclass[11pt,letterpaper]{article}"
        "\n"
        r"\usepackage[margin=1in]{geometry}"
        "\n"
        r"\usepackage{titlesec}"
        "\n"
        r"\titleformat*{\section}{\Large\bfseries}"
        "\n"
        r"\titleformat*{\subsection}{\large\bfseries}"
        "\n"
        r"\titleformat*{\subsubsection}{\normalsize\bfseries}"
    )

    # microtype expansion is incompatible with the bitmap typewriter font
    # shipped with bare TeX Live in this preview environment; disable it
    # for the preview only. The canonical IEEEtran build keeps microtype on.
    tex = tex.replace(r"\usepackage{microtype}", r"% microtype disabled in preview")

    # Replace IEEEtran author block with stock LaTeX equivalent
    tex = re.sub(
        r"\\author\{[^}]*\\IEEEauthorblockN\{([^}]+)\}[^}]*\\IEEEauthorblockA\{([^}]+)\}[^}]*\}",
        lambda m: "\\author{" + m.group(1) + r"\\" + m.group(2).replace(r"\\", r"\\") + "}",
        tex,
        flags=re.DOTALL,
    )

    # IEEEkeywords -> simple bold Keywords line
    tex = re.sub(
        r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}",
        lambda m: r"\noindent\textbf{Keywords:} " + m.group(1).strip() + r"\vspace{6pt}",
        tex,
        flags=re.DOTALL,
    )

    return tex


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    DEST.write_text(transform(src), encoding="utf-8")
    print("Wrote preview source:", DEST.name)

    # Run pdflatex twice for cross-refs
    for pass_no in (1, 2):
        print(f"pdflatex pass {pass_no}...")
        proc = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", DEST.name],
            cwd=ROOT, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            tail = "\n".join(proc.stdout.splitlines()[-60:])
            print(tail)
            raise SystemExit(f"pdflatex failed on pass {pass_no}")

    pdf = DEST.with_suffix(".pdf")
    if pdf.exists():
        print("Preview PDF:", pdf)
    else:
        raise SystemExit("PDF not produced")


if __name__ == "__main__":
    main()
