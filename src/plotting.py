"""Shared chart and table styling so every figure in figures/ looks the same,
plus the helpers that write figures/ and results/."""
import textwrap

import matplotlib

matplotlib.use("Agg")  # figures are written to disk, never shown, so no display is needed
import matplotlib.pyplot as plt

from config import FIGURES_DIR, RESULTS_DIR


def set_chart_title(ax, title, note=None, pad=6):
    """Bold title with an optional smaller note underneath.

    Matplotlib has one title slot per axes, so the note takes that slot and the
    title is anchored just above it; that keeps both left-aligned with the axes.
    """
    if note is None:
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=pad)
        return
    note_text = ax.set_title(note, loc="left", fontsize=10, color="#444444", pad=pad)
    ax.annotate(title, xy=(0, 1), xycoords=note_text, xytext=(0, 4), textcoords="offset points",
                ha="left", va="bottom", fontsize=13, fontweight="bold")


def save_figure(fig, file_name):
    """Save to figures/ at print resolution and free the figure's memory."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / file_name, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_result(table, file_name, index=True):
    """Save an analysis table to results/ so the numbers behind each chart can be
    checked without rerunning the pipeline."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(RESULTS_DIR / file_name, index=index)


def save_table_png(cells, file_name, title, note=None, cell_colors=None, bold_first_col=True):
    """Render a DataFrame of display strings as a table image.

    Column widths follow the longest entry in each column, and headers wrap at
    18 characters, so tables with long call type names stay readable.
    """
    col_labels = ["\n".join(textwrap.fill(line, 18, break_long_words=False) for line in str(col).split("\n")) for col in cells.columns]
    cell_text = cells.astype(str).values.tolist()
    col_chars = [max(len(text) for text in [*label.split("\n"), *cells.iloc[:, i].astype(str)]) for i, label in enumerate(col_labels)]
    col_widths = [max(chars, 8) for chars in col_chars]
    fig, ax = plt.subplots(figsize=(0.13 * sum(col_widths) + 0.6, 0.5 * len(cells) + 1.25))
    ax.axis("off")
    set_chart_title(ax, title, note, pad=12)
    drawn = ax.table(cellText=cell_text, colLabels=col_labels, cellLoc="center", bbox=[0, 0, 1, 1],
                     colWidths=[w / sum(col_widths) for w in col_widths])
    drawn.auto_set_font_size(False)
    drawn.set_fontsize(10)
    header_lines = max(label.count("\n") + 1 for label in col_labels)
    for (row, col), cell in drawn.get_celld().items():
        cell.set_edgecolor("#dddddd")
        if row == 0:
            cell.set_height(0.6 + 0.45 * header_lines)
            cell.set_facecolor("#f2f2f2")
            cell.set_text_props(weight="bold", fontsize=9)
        else:
            cell.set_height(1)
            if col == 0 and bold_first_col:
                cell.set_text_props(weight="bold")
            if cell_colors is not None and cell_colors[row - 1][col] is not None:
                cell.set_facecolor(cell_colors[row - 1][col])
    save_figure(fig, file_name)
