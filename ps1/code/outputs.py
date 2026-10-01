"""Reproducible JSON, NPZ, LaTeX/Markdown table and PDF/PNG figure writers."""
import json
import os
from pathlib import Path
import tempfile

import numpy as np


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def save_solution(directory, name, model, result, pi=None, diagnostics=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    arrays = {"grid": model.grid, "V": result["V"], "G": result["G"],
              "consumption": result["consumption"], "trace": result["trace"]}
    if pi is not None:
        arrays["pi"] = pi
    if diagnostics is not None:
        arrays.update({key: diagnostics[key] for key in ("E", "cEE", "slack", "upper", "next_consumption")})
    np.savez_compressed(directory / f"{name}.npz", **arrays)
    write_json(directory / f"{name}.json", {"settings": model.settings(), **result["metadata"],
               **({"euler_statistics": diagnostics["statistics"]} if diagnostics is not None else {})})


def write_tables(directory, tables):
    """Rewrite the complete table collection from structured rows."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    markdown = []
    def escape(value):
        text = str(value)
        for old, new in (("_", r"\_"), ("%", r"\%"), ("&", r"\&"), ("#", r"\#")):
            text = text.replace(old, new)
        return text
    for name, title, headers, rows in tables:
        latex = [r"\begin{tabular}{" + "l" * len(headers) + "}", r"\hline",
                 " & ".join(map(escape, headers)) + r" \\", r"\hline"]
        latex.extend(" & ".join(map(escape, row)) + r" \\" for row in rows)
        latex.extend([r"\hline", r"\end{tabular}"])
        (directory / f"{name}.tex").write_text("\n".join(latex) + "\n")
        markdown.extend([f"## {title}", "", "| " + " | ".join(headers) + " |",
                         "| " + " | ".join(["---"] * len(headers)) + " |"])
        markdown.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
        markdown.append("")
    (directory / "tables.md").write_text("\n".join(markdown))


def save_figure(figure, directory, name):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    figure.savefig(directory / f"{name}.pdf", bbox_inches="tight")
    figure.savefig(directory / f"{name}.png", dpi=180, bbox_inches="tight")


def plotting():
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ps1-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt
