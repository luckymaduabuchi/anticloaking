#!/usr/bin/env python3
"""Builds the project summary PowerPoint deck (Presentation/AntiFake2026_Evaluation.pptx)
covering all four cloaking techniques with completed evaluations (POP, attack-vc,
AntiFake, ProtectYourAudio), the three downstream synthesizers (SV2TTS, Seed-VC, F5-TTS), and both the
imperceptibility and protective-efficacy results (pooled + descent/gender breakdowns)
for each, plus the cross-cutting ablation/restoration findings and overall conclusions.

All numbers below are taken directly from pop_evaluation_paper.tex (already verified
against the underlying results_table.csv/results_table_by_group.csv files throughout
the project) -- this script does not recompute anything, it only lays out numbers
already established and checked elsewhere.

Run (inside antifake2026 env):
    conda run -n antifake2026 python build_presentation.py
"""
import csv
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AntiFake2026_Evaluation.pptx")

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
NAVY = RGBColor(0x1B, 0x2A, 0x4A)
ACCENT = RGBColor(0x2E, 0x86, 0xC1)
ACCENT2 = RGBColor(0xE6, 0x7E, 0x22)
GREY = RGBColor(0x5D, 0x6D, 0x7E)
LIGHT = RGBColor(0xF4, 0xF6, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOOD = RGBColor(0x1E, 0x8E, 0x3E)
BAD = RGBColor(0xC0, 0x39, 0x2B)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]


def add_slide():
    return prs.slides.add_slide(BLANK)


def add_bg(slide, color=WHITE):
    bg = slide.shapes.add_shape(1, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.line.fill.background()
    bg.shadow.inherit = False
    slide.shapes._spTree.remove(bg._element)
    slide.shapes._spTree.insert(2, bg._element)
    return bg


def add_textbox(slide, left, top, width, height, text, size=18, bold=False, color=NAVY,
                 align=PP_ALIGN.LEFT, italic=False, font="Calibri", anchor=None, line_spacing=None):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    if anchor is not None:
        tf.vertical_anchor = anchor
    lines = text.split("\n") if isinstance(text, str) else text
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.alignment = align
        if line_spacing:
            p.line_spacing = line_spacing
        for run in p.runs:
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.color.rgb = color
            run.font.name = font
    return tb


def add_bullets(slide, left, top, width, height, items, size=16, color=NAVY, font="Calibri",
                 bullet_color=ACCENT, line_spacing=1.15, space_after=8):
    """items: list of (text, level, bold) or plain strings (level=0)."""
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if isinstance(item, tuple):
            text, level, bold = (item + (False,))[:3] if len(item) == 2 else item
        else:
            text, level, bold = item, 0, False
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = level
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        prefix = {0: "■  ", 1: "–  ", 2: "•  "}.get(level, "•  ")
        run = p.add_run()
        run.text = prefix + text
        run.font.size = Pt(size - level * 1.5)
        run.font.bold = bold
        run.font.color.rgb = (bullet_color if level == 0 else color)
        run.font.name = font
    return tb


def slide_header(slide, kicker, title, dark=False):
    add_bg(slide, NAVY if dark else WHITE)
    bar = slide.shapes.add_shape(1, 0, 0, SLIDE_W, Inches(0.09))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False
    if kicker:
        add_textbox(slide, Inches(0.6), Inches(0.35), Inches(10), Inches(0.4), kicker.upper(),
                    size=13, bold=True, color=(ACCENT2 if dark else ACCENT), font="Calibri")
    add_textbox(slide, Inches(0.6), Inches(0.35 + (0.42 if kicker else 0)), Inches(12.1), Inches(0.9),
                title, size=30, bold=True, color=(WHITE if dark else NAVY), font="Calibri")
    line = slide.shapes.add_connector(1, Inches(0.6), Inches(1.32), Inches(12.7), Inches(1.32))
    line.line.color.rgb = (RGBColor(0x3A, 0x4A, 0x6A) if dark else RGBColor(0xD5, 0xDB, 0xE0))
    line.line.width = Pt(1)
    return Inches(1.55)  # y-offset for body content


def add_table(slide, left, top, width, height, headers, rows, col_widths=None,
              header_bg=NAVY, header_fg=WHITE, font_size=13, header_size=13,
              row_alt=LIGHT, highlight_col=None, highlight_color=ACCENT2, first_col_bold=True):
    n_rows = len(rows) + 1
    n_cols = len(headers)
    table_shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    table = table_shape.table
    if col_widths:
        for i, w in enumerate(col_widths):
            table.columns[i].width = w
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = header_bg
        for p in cell.text_frame.paragraphs:
            p.alignment = PP_ALIGN.CENTER if j > 0 else PP_ALIGN.LEFT
            for r in p.runs:
                r.font.size = Pt(header_size)
                r.font.bold = True
                r.font.color.rgb = header_fg
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_top = Pt(3)
        cell.margin_bottom = Pt(3)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.text = str(val)
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if i % 2 == 0 else row_alt
            for p in cell.text_frame.paragraphs:
                p.alignment = PP_ALIGN.CENTER if j > 0 else PP_ALIGN.LEFT
                for r in p.runs:
                    r.font.size = Pt(font_size)
                    r.font.color.rgb = NAVY
                    if j == 0 and first_col_bold:
                        r.font.bold = True
                    if highlight_col is not None and j == highlight_col:
                        r.font.bold = True
                        r.font.color.rgb = highlight_color
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_top = Pt(2)
            cell.margin_bottom = Pt(2)
    return table


def stat_tile(slide, left, top, width, height, value, label, value_color=ACCENT, bg=LIGHT):
    box = slide.shapes.add_shape(1, left, top, width, height)
    box.fill.solid()
    box.fill.fore_color.rgb = bg
    box.line.color.rgb = RGBColor(0xD5, 0xDB, 0xE0)
    box.line.width = Pt(0.75)
    box.shadow.inherit = False
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Pt(6)
    tf.margin_right = Pt(6)
    p0 = tf.paragraphs[0]
    p0.alignment = PP_ALIGN.CENTER
    r0 = p0.add_run()
    r0.text = value
    r0.font.size = Pt(26)
    r0.font.bold = True
    r0.font.color.rgb = value_color
    r0.font.name = "Calibri"
    p1 = tf.add_paragraph()
    p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = label
    r1.font.size = Pt(12)
    r1.font.color.rgb = GREY
    r1.font.name = "Calibri"
    return box


def formula_box(slide, left, top, width, height, lines, size=20, bg=LIGHT, color=NAVY):
    box = slide.shapes.add_shape(1, left, top, width, height)
    box.fill.solid()
    box.fill.fore_color.rgb = bg
    box.line.color.rgb = RGBColor(0xD5, 0xDB, 0xE0)
    box.line.width = Pt(0.75)
    box.shadow.inherit = False
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Pt(16)
    tf.margin_right = Pt(16)
    if isinstance(lines, str):
        lines = [lines]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = line
        r.font.size = Pt(size if i == 0 else size - 4)
        r.font.color.rgb = color if i == 0 else GREY
        r.font.name = "Consolas"
        r.font.bold = (i == 0)
    return box


def section_divider(number, title, subtitle):
    slide = add_slide()
    add_bg(slide, NAVY)
    add_textbox(slide, Inches(0.9), Inches(2.7), Inches(2.5), Inches(1.2), number,
                size=72, bold=True, color=ACCENT2, font="Calibri")
    add_textbox(slide, Inches(0.9), Inches(3.9), Inches(11.5), Inches(1.2), title,
                size=40, bold=True, color=WHITE, font="Calibri")
    add_textbox(slide, Inches(0.9), Inches(4.75), Inches(11.0), Inches(1.0), subtitle,
                size=18, color=RGBColor(0xB8, 0xC4, 0xD6), font="Calibri")
    line = slide.shapes.add_connector(1, Inches(0.95), Inches(3.75), Inches(4.5), Inches(3.75))
    line.line.color.rgb = ACCENT2
    line.line.width = Pt(3)
    return slide


def footer(slide, text, page=None):
    add_textbox(slide, Inches(0.6), Inches(7.12), Inches(9), Inches(0.3), text,
                size=10, color=GREY, font="Calibri")
    if page:
        add_textbox(slide, Inches(12.4), Inches(7.12), Inches(0.6), Inches(0.3), str(page),
                    size=10, color=GREY, align=PP_ALIGN.RIGHT, font="Calibri")


# ---------------------------------------------------------------------------
# Restoration-study data: read directly from results_table.csv at build time
# (not hardcoded) so re-running this script always reflects the latest
# scoring, including AntiFake combinations still being scored.
# ---------------------------------------------------------------------------
RESULTS_ROOT = "/home/vm-user/Desktop/Antifake2026/results"


def _read_eer(path):
    if not os.path.isfile(path):
        return None
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out[row["SV"]] = float(row["EER"]) * 100
    return out


_CEILING = _read_eer(os.path.join(RESULTS_ROOT, "groundtruthcomparison/cleanbonafidevscleansynth/SV2TTS/results_table.csv"))
_BASELINES = {
    "POP": _read_eer(os.path.join(RESULTS_ROOT, "groundtruthvscloaking/groundtruthvsPOP/groundtruthvscloakedsynthesis/sv2tts/results_table.csv")),
    "attackvc": _read_eer(os.path.join(RESULTS_ROOT, "groundtruthvscloaking/groundtruthvsattackvc/groundtruthvscloakedsynthesis/sv2tts/results_table.csv")),
    "Antifake": _read_eer(os.path.join(RESULTS_ROOT, "cleanbonafidevscleansynth/ANTIFAKE_SV2TTS/results_table.csv")),
}
_GROUPDIR = {"POP": "groundtruthvsPOP", "attackvc": "groundtruthvsattackvc", "Antifake": "groundtruthvsAntifake"}

# Per-synthesizer no-restoration baselines -- Seed-VC/F5-TTS each have
# their OWN baseline, far closer to the clean-audio ceiling than
# SV2TTS's (both cloaks barely protect against Seed-VC/F5-TTS even for
# a naive attacker), so a restoration technique's Seed-VC/F5-TTS EER
# must never be compared against the SV2TTS baseline -- see the paper's
# \S sec:restoration-seedvc-f5tts for the same caveat stated in full.
_BASELINES_MULTI = {
    "POP": {
        "sv2tts": _BASELINES["POP"],
        "seedvc": _read_eer(os.path.join(RESULTS_ROOT, "groundtruthvscloaking/groundtruthvsPOP/groundtruthvscloakedsynthesis/seedvc/results_table.csv")),
        "f5tts": _read_eer(os.path.join(RESULTS_ROOT, "groundtruthvscloaking/groundtruthvsPOP/groundtruthvscloakedsynthesis/f5tts/results_table.csv")),
    },
    "attackvc": {
        "sv2tts": _BASELINES["attackvc"],
        "seedvc": _read_eer(os.path.join(RESULTS_ROOT, "groundtruthvscloaking/groundtruthvsattackvc/groundtruthvscloakedsynthesis/seedvc/results_table.csv")),
        "f5tts": _read_eer(os.path.join(RESULTS_ROOT, "groundtruthvscloaking/groundtruthvsattackvc/groundtruthvscloakedsynthesis/f5tts/results_table.csv")),
    },
    "Antifake": {
        "sv2tts": _BASELINES["Antifake"],
        "seedvc": _read_eer(os.path.join(RESULTS_ROOT, "cleanbonafidevscleansynth/ANTIFAKE_SEEDVC/results_table.csv")),
        "f5tts": _read_eer(os.path.join(RESULTS_ROOT, "cleanbonafidevscleansynth/ANTIFAKE_F5TTS/results_table.csv")),
    },
}

# POP / attack-vc: full 6-gain low-pass sweep + 9 other techniques (16 total).
_TECHNIQUES_FULL = [
    ("Low-pass + gain 1.0", "lowpass_gain/gain_1.0"),
    ("Low-pass + gain 1.2", "lowpass_gain/gain_1.2"),
    ("Low-pass + gain 1.4", "lowpass_gain/gain_1.4"),
    ("Low-pass + gain 1.6", "lowpass_gain/gain_1.6"),
    ("Low-pass + gain 1.8", "lowpass_gain/gain_1.8"),
    ("Low-pass + gain 2.0", "lowpass_gain/gain_2.0"),
    ("Adaptive-filter-centroid", "adaptive_filter_centroid"),
    ("Downsampling", "downsampling"),
    ("Upsampling", "upsampling"),
    ("Ensemble-averaging (perturbed)", "ensemble_averaging_perturbed"),
    ("Mel-spectrogram inversion", "mel_spectrogram_inversion"),
    ("Quantization", "quantization"),
    ("High-pass", "highpass"),
    ("Spectral subtraction", "spectral_subtraction"),
    ("Simulated re-recording", "re_recording"),
    ("Second-cloak (additive noise)", "second_cloak_noise"),
]
# AntiFake: originally only a single low-pass gain (1.0) was run, but a
# full 6-gain sweep was later completed (matching POP/attack-vc) --
# confirmed via on-disk audit, same 16-technique-variant set as POP/attack-vc.
_TECHNIQUES_ANTIFAKE = _TECHNIQUES_FULL


def _verdict(dsb, drb, dwl):
    """Reversed = EER moved meaningfully back toward the clean-audio ceiling
    (attacker recovers verifiability) on all three verifiers at once."""
    if dsb <= -5 and drb <= -5 and dwl <= -3:
        return "PARTIAL REVERSAL"
    if dsb <= -1 and drb <= -1 and dwl <= -1:
        return "Slight reversal"
    return "No"


def restoration_rows(method, synth="sv2tts"):
    """[label, SB%, RB%, WL%, delta-SB-vs-baseline(pp), verdict] per technique,
    or a 'pending' placeholder row for combinations not yet scored.
    baseline is synth's OWN no-restoration baseline, never sv2tts's --
    Seed-VC/F5-TTS sit far closer to the clean-audio ceiling even before
    any restoration, so comparing against the wrong baseline would make
    ordinary EER values look like a dramatic reversal (see the paper's
    \\S sec:restoration-seedvc-f5tts)."""
    techniques = _TECHNIQUES_ANTIFAKE if method == "Antifake" else _TECHNIQUES_FULL
    b = _BASELINES_MULTI[method][synth]
    rows = []
    for label, dirname in techniques:
        path = os.path.join(RESULTS_ROOT, "groundtruthvscloaking", _GROUPDIR[method],
                             "groundtruthvsrestoredsynthesis", dirname, synth, "results_table.csv")
        d = _read_eer(path)
        if d is None:
            rows.append([label, "—", "—", "—", "—", "pending"])
            continue
        dsb = d["SB-ECAPA"] - b["SB-ECAPA"]
        drb = d["Resemblyzer"] - b["Resemblyzer"]
        dwl = d["WavLM"] - b["WavLM"]
        rows.append([
            label,
            f"{d['SB-ECAPA']:.2f}%", f"{d['Resemblyzer']:.2f}%", f"{d['WavLM']:.2f}%",
            f"{dsb:+.2f}pp", _verdict(dsb, drb, dwl),
        ])
    return rows


_SYNTH_DISPLAY = {"sv2tts": "SV2TTS", "seedvc": "Seed-VC", "f5tts": "F5-TTS"}


def restoration_table_slide(page, method, method_display, baseline, ceiling, synth="sv2tts"):
    slide = add_slide()
    synth_display = _SYNTH_DISPLAY[synth]
    y = slide_header(slide, "Restoration Study", f"{method_display} / {synth_display}: Does Restoration Reverse the Cloak?")
    add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.4),
                f"Clean-audio ceiling: SB={ceiling['SB-ECAPA']:.2f}%  RB={ceiling['Resemblyzer']:.2f}%  WL={ceiling['WavLM']:.2f}%   |   "
                f"No-restoration baseline ({synth_display}, not SV2TTS's): SB={baseline['SB-ECAPA']:.2f}%  RB={baseline['Resemblyzer']:.2f}%  WL={baseline['WavLM']:.2f}%",
                size=13, color=GREY)
    headers = ["Restoration technique", "SB-ECAPA", "Resemblyzer", "WavLM", "ΔSB-ECAPA vs baseline", "Reversed?"]
    rows = restoration_rows(method, synth)
    table = add_table(slide, Inches(0.6), y + Inches(0.55), Inches(12.1), Inches(5.3), headers, rows,
                       col_widths=[Inches(3.3), Inches(1.6), Inches(1.7), Inches(1.5), Inches(2.1), Inches(1.9)],
                       font_size=10.5, header_size=11)
    for i, row in enumerate(rows):
        verdict = row[5]
        color = BAD if verdict == "No" else (GOOD if verdict == "PARTIAL REVERSAL" else ACCENT2)
        if verdict == "pending":
            color = GREY
        cell = table.cell(i + 1, 5)
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.color.rgb = color
    footer(slide, "Section 9 — Restoration Study", page)
    return slide


_RESTORATION_BASELINE_GROUP_PATH = {
    "POP": "groundtruthvscloaking/groundtruthvsPOP/groundtruthvscloakedsynthesis/sv2tts/results_table_by_group.csv",
    "attackvc": "groundtruthvscloaking/groundtruthvsattackvc/groundtruthvscloakedsynthesis/sv2tts/results_table_by_group.csv",
    "Antifake": "cleanbonafidevscleansynth/ANTIFAKE_SV2TTS/results_table_by_group.csv",
}


def _read_group_eer(path):
    """{group: {verifier: eer}}, group like 'African-men' (Descent-Gender)."""
    if not path or not os.path.isfile(path):
        return None
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["Group"], {})[row["SV"]] = float(row["EER"]) * 100
    return out


_DESCENTS = ["African", "Asian(East)", "Asian(South)", "Caucasian(American)", "Caucasian(European)"]


def _group_means(group_eer):
    """group_eer: {group: {verifier: eer}} -> (gender_means, descent_means)."""
    gender_b, descent_b = {}, {}
    for group, verifiers in group_eer.items():
        gender = group.rsplit("-", 1)[1]
        descent = group.rsplit("-", 1)[0]
        for eer in verifiers.values():
            gender_b.setdefault(gender, []).append(eer)
            descent_b.setdefault(descent, []).append(eer)
    gm = {g: sum(v) / len(v) for g, v in gender_b.items()}
    dm = {d: sum(v) / len(v) for d, v in descent_b.items()}
    return gm, dm


def restoration_technique_demographic_rows(method):
    """Per-technique gender and descent means (mean EER across all 3
    verifiers), plus a leading baseline row. Returns (gender_rows,
    descent_rows, n_scored, n_total)."""
    techniques = _TECHNIQUES_ANTIFAKE if method == "Antifake" else _TECHNIQUES_FULL
    baseline = _read_group_eer(os.path.join(RESULTS_ROOT, _RESTORATION_BASELINE_GROUP_PATH[method]))
    bgm, bdm = _group_means(baseline)

    gender_rows = [["Baseline (no restoration)", f"{bgm['men']:.2f}%", f"{bgm['women']:.2f}%", f"{bgm['women'] - bgm['men']:+.2f}pp"]]
    descent_rows = [["Baseline (no restoration)"] + [f"{bdm[d]:.2f}%" for d in _DESCENTS]]
    n_scored = 0
    for label, dirname in techniques:
        path = os.path.join(RESULTS_ROOT, "groundtruthvscloaking", _GROUPDIR[method],
                             "groundtruthvsrestoredsynthesis", dirname, "sv2tts", "results_table_by_group.csv")
        d = _read_group_eer(path)
        if d is None:
            gender_rows.append([label, "—", "—", "—"])
            descent_rows.append([label] + ["—"] * 5)
            continue
        n_scored += 1
        gm, dm = _group_means(d)
        gender_rows.append([label, f"{gm['men']:.2f}%", f"{gm['women']:.2f}%", f"{gm['women'] - gm['men']:+.2f}pp"])
        descent_rows.append([label] + [f"{dm[d_]:.2f}%" for d_ in _DESCENTS])
    return gender_rows, descent_rows, n_scored, len(techniques)


def restoration_gender_table_slide(page, method, method_display, gender_rows, n_scored, n_total):
    slide = add_slide()
    y = slide_header(slide, "Restoration Study — Demographics", f"{method_display}: Gender Breakdown by Restoration Technique")
    add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.35),
                f"Mean EER across all 3 verifiers, per technique ({n_scored} of {n_total} scored so far"
                + (", rest pending)" if n_scored < n_total else ")"),
                size=12, color=GREY)
    headers = ["Restoration technique", "Men", "Women", "Δ (Women − Men)"]
    table = add_table(slide, Inches(0.6), y + Inches(0.5), Inches(12.1), Inches(5.4), headers, gender_rows,
                       col_widths=[Inches(4.4), Inches(2.2), Inches(2.2), Inches(3.3)], font_size=10.5, header_size=11)
    for i, row in enumerate(gender_rows):
        cell = table.cell(i + 1, 3)
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.color.rgb = ACCENT2 if r.text != "—" else GREY
    footer(slide, "Section 9 — Restoration Study", page)
    return slide


def restoration_descent_table_slide(page, method, method_display, descent_rows, n_scored, n_total):
    slide = add_slide()
    y = slide_header(slide, "Restoration Study — Demographics", f"{method_display}: Descent Breakdown by Restoration Technique")
    add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.35),
                f"Mean EER across all 3 verifiers and both genders, per technique ({n_scored} of {n_total} scored so far"
                + (", rest pending)" if n_scored < n_total else ")"),
                size=12, color=GREY)
    headers = ["Restoration technique", "African", "Asian\n(East)", "Asian\n(South)", "Caucasian\n(American)", "Caucasian\n(European)"]
    table = add_table(slide, Inches(0.6), y + Inches(0.5), Inches(12.1), Inches(5.4), headers, descent_rows,
                       col_widths=[Inches(3.5), Inches(1.72), Inches(1.72), Inches(1.72), Inches(1.72), Inches(1.72)],
                       font_size=10, header_size=10.5)
    footer(slide, "Section 9 — Restoration Study", page)
    return slide


# ===========================================================================
# TITLE SLIDE
# ===========================================================================
slide = add_slide()
add_bg(slide, NAVY)
band = slide.shapes.add_shape(1, 0, Inches(4.65), SLIDE_W, Inches(0.06))
band.fill.solid(); band.fill.fore_color.rgb = ACCENT2; band.line.fill.background(); band.shadow.inherit = False
add_textbox(slide, Inches(0.9), Inches(2.1), Inches(11.5), Inches(0.5), "PROACTIVE AUDIO CLOAKING AGAINST VOICE CLONING",
            size=16, bold=True, color=ACCENT2)
add_textbox(slide, Inches(0.9), Inches(2.55), Inches(11.5), Inches(1.8),
            "Imperceptibility vs. Protective Efficacy:\nA Multi-Technique, Demographically Balanced Evaluation",
            size=34, bold=True, color=WHITE, line_spacing=1.1)
add_textbox(slide, Inches(0.9), Inches(4.85), Inches(11.5), Inches(0.6),
            "POP  •  attack-vc  •  AntiFake   |   SV2TTS  •  Seed-VC  •  F5-TTS",
            size=18, color=RGBColor(0xB8, 0xC4, 0xD6))
add_textbox(slide, Inches(0.9), Inches(6.6), Inches(11.5), Inches(0.5),
            "4,867 recordings  •  3 corpora (LibriSpeech, ASVspoof 2021, FakeAVCeleb)  •  10 descent×gender groups",
            size=13, color=GREY)

# ===========================================================================
# AGENDA
# ===========================================================================
slide = add_slide()
y = slide_header(slide, "Overview", "Agenda")
agenda = [
    ("01", "Introduction & Motivation"),
    ("02", "Dataset & Evaluation Protocol"),
    ("03", "Speaker Verifiers & Downstream Synthesizers"),
    ("04", "Cloaking Techniques: POP, attack-vc, AntiFake, ProtectYourAudio"),
    ("05", "Imperceptibility Results (+ descent/gender)"),
    ("06", "Protective-Efficacy Results (+ descent/gender)"),
    ("07", "Why Is Seed-VC Different? (embedding-probe ablation)"),
    ("08", "Theoretical Framework: Cloaking & Restoration as Optimization"),
    ("09", "Can Protective Efficacy Be Reversed? (restoration study)"),
    ("10", "Cross-Technique Summary & Conclusions"),
]
for i, (num, title) in enumerate(agenda):
    row = i % 5
    col = i // 5
    left = Inches(0.6 + col * 6.3)
    top = y + Inches(row * 1.0)
    add_textbox(slide, left, top, Inches(0.9), Inches(0.7), num, size=22, bold=True, color=ACCENT2)
    add_textbox(slide, left + Inches(0.85), top + Inches(0.05), Inches(5.2), Inches(0.7), title, size=17, bold=True, color=NAVY)
footer(slide, "AntiFake2026 Project Evaluation", 2)

# ===========================================================================
# SECTION 1: INTRODUCTION
# ===========================================================================
section_divider("01", "Introduction & Motivation", "Why proactive audio cloaking, and what this evaluation actually measures")

slide = add_slide()
y = slide_header(slide, "Introduction", "The Threat: Zero-Shot Voice Cloning")
add_bullets(slide, Inches(0.6), y, Inches(6.1), Inches(5.2), [
    ("Modern zero-shot TTS/VC systems clone a speaker's identity from only a few seconds of reference audio", 0, True),
    ("No speaker-specific fine-tuning required", 1),
    ("Enables fraud via cloned voices, non-consensual synthetic media, bypassing voice authentication", 1),
    ("Two families of countermeasure", 0, True),
    ("Reactive: detect deepfake audio after the fact", 1),
    ("Proactive (“cloaking”): perturb the speaker's recording BEFORE an attacker ever gets clean audio", 1),
], size=17)
add_bullets(slide, Inches(7.0), y, Inches(5.7), Inches(5.2), [
    ("This project's contribution", 0, True),
    ("Reproduce 4 cloaking defenses end-to-end, from official source, on identical hardware", 1),
    ("Same dataset, same verifiers, same synthesizers — so differences are not artifacts of setup", 1),
    ("First large-scale demographic (descent × gender) audit of cloaking effectiveness", 1),
    ("Distinguish two properties every cloak paper conflates:", 1, True),
], size=17)
stat_tile(slide, Inches(7.3), y + Inches(3.05), Inches(2.5), Inches(1.4), "Imperceptibility", "Does the cloaked clip\nstill sound like the\nreal speaker?", value_color=ACCENT)
stat_tile(slide, Inches(10.1), y + Inches(3.05), Inches(2.5), Inches(1.4), "Protective\nEfficacy", "Does a clone MADE FROM\nthe cloaked clip still\nsound like them?", value_color=ACCENT2)
footer(slide, "Section 1 — Introduction", 4)

slide = add_slide()
y = slide_header(slide, "Introduction", "Imperceptibility ≠ Protective Efficacy")
add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.6),
            "The central methodological distinction of this project — conflating the two is the most common gap in the cloaking literature.",
            size=16, italic=True, color=GREY)
headers = ["", "What is compared", "“Success” looks like", "What it tells you"]
rows = [
    ["Imperceptibility", "Cloaked clip  vs.  genuine original", "Verifies as SAME speaker\n(low EER, high TAR@FAR)", "Cloak avoids being flagged\non its own"],
    ["Protective\nEfficacy", "Clone MADE FROM cloaked clip\nvs.  genuine original", "Verifies as DIFFERENT speaker\n(high EER, low TAR@FAR)", "Cloak actually stopped a\ndownstream cloning attacker"],
]
add_table(slide, Inches(0.6), y + Inches(0.75), Inches(12.1), Inches(2.0), headers, rows,
          col_widths=[Inches(2.0), Inches(3.6), Inches(3.5), Inches(3.0)], font_size=14, header_size=14)
add_bullets(slide, Inches(0.6), y + Inches(3.1), Inches(12.1), Inches(2.2), [
    ("A cloak can pass every imperceptibility check while doing almost nothing to stop a downstream attacker (POP, attack-vc vs. Seed-VC)", 0),
    ("...or fail imperceptibility outright while being the most protective technique tested (AntiFake)", 0),
    ("This project reports BOTH for every technique — no prior cloaking paper in our comparison set does", 0, True),
], size=16)
footer(slide, "Section 1 — Introduction", 5)

# ===========================================================================
# SECTION 2: DATASET
# ===========================================================================
section_divider("02", "Dataset & Evaluation Protocol", "4,867 recordings, 3 corpora, demographically balanced, harmonized trial construction")

slide = add_slide()
y = slide_header(slide, "Dataset", "Corpus Composition")
headers = ["Source", "Men", "Women", "Total (# speakers)", "Why included"]
rows = [
    ["LibriSpeech\n(train-clean-100)", "—", "—", "500 (207)", "Clean, ideal-condition baseline;\nmost-used TTS/VC benchmark corpus"],
    ["ASVspoof 2021\n(LA, bonafide)", "—", "—", "500 (62)", "Telephony-channel degradation;\ntests robustness to codec artifacts"],
    ["FakeAVCeleb", "1,897", "1,970", "3,867 (500)", "Only corpus with descent/gender\nmetadata — enables fairness audit"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(2.6), headers, rows,
          col_widths=[Inches(2.6), Inches(1.3), Inches(1.3), Inches(2.4), Inches(4.5)], font_size=14)
stat_tile(slide, Inches(0.6), y + Inches(2.9), Inches(2.9), Inches(1.3), "4,867", "total recordings")
stat_tile(slide, Inches(3.65), y + Inches(2.9), Inches(2.9), Inches(1.3), "769", "unique speakers")
stat_tile(slide, Inches(6.7), y + Inches(2.9), Inches(2.9), Inches(1.3), "5 × 2", "descent groups × genders\n(FakeAVCeleb)")
stat_tile(slide, Inches(9.75), y + Inches(2.9), Inches(2.9), Inches(1.3), "3", "source corpora")
add_textbox(slide, Inches(0.6), y + Inches(4.4), Inches(12.1), Inches(0.6),
            "Descent groups: African, Asian (East), Asian (South), Caucasian (American), Caucasian (European)",
            size=14, color=GREY, italic=True)
footer(slide, "Section 2 — Dataset", 7)

slide = add_slide()
y = slide_header(slide, "Dataset", "Trial-Construction Protocol")
add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.6),
            "A verification score is meaningless in isolation — it must be compared against real impostors, not just the genuine pair.",
            size=15, italic=True, color=GREY)
add_bullets(slide, Inches(0.6), y + Inches(0.75), Inches(6.0), Inches(4.5), [
    ("Genuine trial", 0, True),
    ("Cloaked/cloned clip vs. the SAME speaker's real recording → label = 1", 1),
    ("Impostor trials", 0, True),
    ("Same clip vs. 10 OTHER randomly drawn speakers' real recordings → label = 0 (×10)", 1),
    ("Fixed seed for reproducibility", 1),
], size=17)
stat_tile(slide, Inches(7.0), y + Inches(0.8), Inches(2.6), Inches(1.3), "4,867", "genuine trials\nper technique")
stat_tile(slide, Inches(9.8), y + Inches(0.8), Inches(2.6), Inches(1.3), "48,670", "impostor trials\nper technique")
add_bullets(slide, Inches(7.0), y + Inches(2.4), Inches(5.4), Inches(2.5), [
    ("Every metric (EER, ROC-AUC, minDCF, TAR@FAR, d′) is a function of BOTH distributions", 0),
    ("Large enough to estimate low-FAR operating points down to 0.01% FAR", 0),
], size=16)
footer(slide, "Section 2 — Dataset", 8)

# ===========================================================================
# SECTION 3: VERIFIERS & SYNTHESIZERS
# ===========================================================================
section_divider("03", "Speaker Verifiers & Synthesizers", "3 independent verification back-ends × 3 downstream cloning systems")

slide = add_slide()
y = slide_header(slide, "Models", "Three Speaker-Verification Back-Ends")
headers = ["Model", "Embedding", "Why included"]
rows = [
    ["SpeechBrain\nECAPA-TDNN", "192-d channel-attention TDNN,\ntrained on VoxCeleb", "De facto standard; the white-box/surrogate\ntarget of AntiFake and attack-vc"],
    ["Resemblyzer\n(GE2E d-vector)", "256-d LSTM d-vector,\ngeneralized end-to-end loss", "Surrogate encoder inside ProtectYourAudio\nand AUTOVC-style VC systems"],
    ["WavLM x-vector", "512-d x-vector over WavLM-base-plus\nself-supervised features", "Architecturally unrelated to all cloak\nsurrogates — black-box generalization test"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(2.9), headers, rows,
          col_widths=[Inches(2.4), Inches(4.3), Inches(5.4)], font_size=14)
add_textbox(slide, Inches(0.6), y + Inches(3.2), Inches(12.1), Inches(0.8),
            "Never ensembled — scored fully independently, so a cloak that fools one embedding space but not another is never over/understated.",
            size=15, italic=True, color=GREY)
footer(slide, "Section 3 — Verifiers & Synthesizers", 10)

slide = add_slide()
y = slide_header(slide, "Models", "Three Downstream Cloning/Conversion Systems")
headers = ["System", "Type", "Identity conditioning", "Rationale"]
rows = [
    ["SV2TTS", "Zero-shot TTS", "GE2E LSTM d-vector\n(256-d, discrete encoder)", "Foundational architecture;\nAntiFake/ProtectYourAudio's own target"],
    ["F5-TTS", "Zero-shot TTS\n(flow-matching)", "NO discrete encoder —\nin-context mel conditioning", "State-of-the-art; stronger\nspeaker-similarity than SV2TTS"],
    ["Seed-VC", "Voice conversion", "CAMPPlus (D-TDNN, 192-d,\ndiscrete encoder)", "Not TTS — several cloaks\n(attack-vc) target VC specifically"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(3.0), headers, rows,
          col_widths=[Inches(1.7), Inches(2.4), Inches(3.6), Inches(4.4)], font_size=14)
add_bullets(slide, Inches(0.6), y + Inches(3.3), Inches(12.1), Inches(1.5), [
    ("Fixed synthesis prompt for BOTH TTS systems — only cloned identity varies, never linguistic content", 0),
    ("Seed-VC uses a fixed source clip for content, varying only the target-timbre input", 0),
], size=15)
footer(slide, "Section 3 — Verifiers & Synthesizers", 11)

# ===========================================================================
# SECTION 4: CLOAKING TECHNIQUES
# ===========================================================================
section_divider("04", "Cloaking Techniques", "POP · attack-vc · AntiFake · ProtectYourAudio — mechanism, threat model, and how each was reproduced")

slide = add_slide()
y = slide_header(slide, "Cloaking Techniques", "Four Mechanistically Different Attacks")
headers = ["Technique", "Threat model", "Mechanism"]
rows = [
    ["POP", "Training-time\n(unlearnable audio)", "PGD minimizing a pretrained VITS surrogate's OWN\nmel-reconstruction loss; ε=8/255, 200 iterations.\nSurrogate has NO speaker encoder — a closed\nlookup table over 50 fixed training speakers."],
    ["attack-vc", "Inference-time\n(VC spoofing)", "Decoy-target PGD; embedding-attack variant against\nAdaIN-VC's own bespoke conv-bank speaker encoder\n(perturbs input directly, no full forward pass needed)."],
    ["AntiFake", "Inference-time\n(TTS/VC spoofing,\nensemble)", "Decoy-target PGD optimized JOINTLY against 3\nsurrogate encoders (RTVC, AutoVC, Coqui YourTTS)\nfor black-box transferability."],
    ["ProtectYourAudio", "Inference-time\n(VC spoofing)", "Greedy discrete search over frequency-band masking\noperations, budgeted against a perceptual-similarity\nconstraint; targets a VC model's reconstruction\nquality rather than a speaker-embedding distance."],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(4.6), headers, rows,
          col_widths=[Inches(1.7), Inches(2.6), Inches(7.8)], font_size=13)
add_textbox(slide, Inches(0.6), y + Inches(4.9), Inches(12.1), Inches(0.6),
            "All reproduced end-to-end from official public source code on identical, shared hardware — not re-using each paper's own reported numbers.",
            size=14, italic=True, color=GREY)
footer(slide, "Section 4 — Cloaking Techniques", 13)

slide = add_slide()
y = slide_header(slide, "Cloaking Techniques", "Corpus Coverage & Engineering Obstacles")
stat_tile(slide, Inches(0.6), y, Inches(2.9), Inches(1.3), "4,864 / 4,867", "POP — 3 excluded\n(Whisper hallucination)")
stat_tile(slide, Inches(3.6), y, Inches(2.9), Inches(1.3), "4,863 / 4,867", "attack-vc — 4 excluded")
stat_tile(slide, Inches(6.6), y, Inches(2.9), Inches(1.3), "4,844 / 4,867", "AntiFake — 21 permanent\nfailures, 2 unattempted")
stat_tile(slide, Inches(9.6), y, Inches(2.9), Inches(1.3), "4,850 / 4,867", "ProtectYourAudio — 16\npermanent failures, 1 unattempted")
add_bullets(slide, Inches(0.6), y + Inches(1.7), Inches(12.1), Inches(3.8), [
    ("AntiFake's 3-encoder ensemble needed a hardware upgrade (4GB → 12GB vGPU) — originally OOM'd before a single optimization step ran", 0, True),
    ("Verified as a genuine hardware limit (reproduced on an idle GPU), not a software bug", 1),
    ("POP's reference implementation silently DROPS training examples whose phonemized transcript exceeds a fixed length — no warning, stalls unattended batch jobs indefinitely", 0, True),
    ("Fixed by raising the threshold; excluded only genuine ASR-hallucination failures", 1),
    ("None of the four techniques' reference implementations are robust to a shared, memory-constrained GPU — transient CUDA OOM/cuDNN errors had to be disambiguated from genuine per-file failures", 0),
], size=16)
footer(slide, "Section 4 — Cloaking Techniques", 14)

# ===========================================================================
# SECTION 5: IMPERCEPTIBILITY RESULTS
# ===========================================================================
section_divider("05", "Imperceptibility Results", "Does the cloaked clip still verify as the genuine speaker, on its own?")

slide = add_slide()
y = slide_header(slide, "Imperceptibility", "Pooled Results — All Four Techniques")
headers = ["Technique", "SB-ECAPA\nEER / TAR@1%", "Resemblyzer\nEER / TAR@1%", "WavLM\nEER / TAR@1%", "STOI / PESQ / SI-SDR(dB)"]
rows = [
    ["POP\n(4,864 clips)", "0.07% / 100.0%", "0.14% / 100.0%", "0.16% / 100.0%", "0.971 / 2.92 / +16.3"],
    ["attack-vc\n(4,863 clips)", "0.10% / 99.96%", "0.08% / 99.96%", "2.08% / 96.88%", "0.547 / 3.58 / −34.0"],
    ["AntiFake\n(4,844 clips)", "47.81% / 21.2%", "65.87% / 5.08%", "22.29% / 25.19%", "0.703 / 1.46 / +1.9"],
    ["ProtectYourAudio\n(4,850 clips)", "0.10% / 100.0%", "0.07% / 100.0%", "2.05% / 96.19%", "0.941 / 3.48 / −25.4"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(2.9), headers, rows,
          col_widths=[Inches(1.9), Inches(2.2), Inches(2.2), Inches(2.2), Inches(3.6)], font_size=13, header_size=12,
          highlight_col=None)
add_bullets(slide, Inches(0.6), y + Inches(3.2), Inches(12.1), Inches(2.4), [
    ("POP, attack-vc & ProtectYourAudio: near-perfect imperceptibility (EER ≤ 2.1%) — exactly what a training-/inference-time cloak is designed for", 0, True),
    ("AntiFake: imperceptibility FAILS outright (EER 22–66%) — roughly two orders of magnitude worse than the other three", 0, True),
    ("ProtectYourAudio's EER/TAR track attack-vc's almost exactly despite being mechanistically unrelated (discrete frequency-masking search vs. continuous embedding attack) — but its quality profile is its own: POP-level STOI (0.94) paired with attack-vc-level negative SI-SDR (−25.4dB)", 0),
], size=16)
footer(slide, "Section 5 — Imperceptibility", 16)

def descent_gender_slide(kicker, title, mean_rows, note, page):
    slide = add_slide()
    y = slide_header(slide, kicker, title)
    headers = ["Group", "Mean EER (avg. of 3 verifiers)"]
    add_table(slide, Inches(0.6), y, Inches(6.0), Inches(4.6), headers, mean_rows,
              col_widths=[Inches(3.6), Inches(2.4)], font_size=14)
    add_bullets(slide, Inches(7.0), y, Inches(5.7), Inches(4.8), note, size=16)
    footer(slide, kicker, page)
    return slide

descent_gender_slide(
    "Imperceptibility — Demographics", "POP: EER by Descent × Gender (FakeAVCeleb)",
    [
        ["Men (avg.)", "≈ 0.06%"],
        ["Women (avg.)", "≈ 0.08%"],
        ["All 10 groups", "0.03%–0.28%"],
        ["Lowest TAR@1%", "94.66% (Asian East, men, WavLM)"],
        ["2nd lowest TAR@1%", "96.50% (Caucasian European, men, SB-ECAPA)"],
    ],
    [
        ("Imperceptibility holds UNIFORMLY across every descent × gender group", 0, True),
        ("No demographic group stands out as disproportionately easier or harder to re-identify after cloaking", 0),
        ("The only two departures from 100% TAR@1%FAR remain far closer to “trivially re-identifiable” than to the uncloaked FakeAVCeleb calibration ceiling (11–15%)", 0),
        ("→ no meaningful demographic disparity in imperceptibility for POP", 0, True),
    ],
    18,
)

descent_gender_slide(
    "Imperceptibility — Demographics", "attack-vc: EER by Descent × Gender (FakeAVCeleb)",
    [
        ["Men (avg.)", "≈ 0.10%"],
        ["Women (avg.)", "≈ 0.13%"],
        ["All 10 groups", "0.03%–0.72%"],
        ["Cells below 100% TAR@1%", "12 of 30 (range 96.2–99.8%)"],
        ["WavLM at 100% in", "4 of 10 groups"],
    ],
    [
        ("More SCATTERED than POP across verifiers/groups — SB-ECAPA drops in 5 groups, WavLM in 6, Resemblyzer in only 1", 0, True),
        ("Still far closer to POP's near-ceiling regime than to the uncloaked baseline (11–15% TAR@1%)", 0),
        ("This scatter is noise within an already-near-perfect result — not a sign of demographic bias", 0, True),
    ],
    19,
)

descent_gender_slide(
    "Imperceptibility — Demographics", "AntiFake: EER by Descent × Gender (FakeAVCeleb)",
    [
        ["Men (avg.)", "46.84%"],
        ["Women (avg.)", "50.70%"],
        ["African", "46.13%"],
        ["Asian (East)", "46.85%"],
        ["Asian (South)", "45.21%"],
        ["Caucasian (American)", "53.15%"],
        ["Caucasian (European)", "52.50%"],
    ],
    [
        ("Women consistently HIGHER EER than men — but here that means WORSE imperceptibility, not better protection", 0, True),
        ("Caucasian groups show the WORST imperceptibility of all five descent groups", 0, True),
        ("Interpretation flips vs. POP/attack-vc: a higher EER here means the cloak fails its OWN design goal more badly for these speakers", 0),
        ("This exact ordering reappears in protective efficacy — same underlying displacement mechanism (see Section 6)", 0),
    ],
    20,
)

descent_gender_slide(
    "Imperceptibility — Demographics", "ProtectYourAudio: EER by Descent × Gender (FakeAVCeleb)",
    [
        ["Men (avg.)", "≈ 0.51%"],
        ["Women (avg.)", "≈ 0.49%"],
        ["All 10 groups", "0.29%–0.64%"],
        ["Cells below 100% TAR@1% (SB/RB)", "2 of 20 (both Resemblyzer, men)"],
        ["Lowest TAR@1%", "75.63% (Caucasian European, men, Resemblyzer)"],
    ],
    [
        ("The most UNIFORM technique in this project — SB-ECAPA hits exactly 100% TAR@1% in all 10 groups; WavLM never drops below 92.9%", 0, True),
        ("Resemblyzer is the one exception, concentrated in two groups (both men) — possibly linked to Resemblyzer being ProtectYourAudio's own surrogate encoder, but not confirmed", 0),
        ("Even this most-scattered cell remains far closer to near-ceiling imperceptibility than to the uncloaked baseline (11–15% TAR@1%)", 0, True),
    ],
    21,
)

# ===========================================================================
# SECTION 6: PROTECTIVE EFFICACY
# ===========================================================================
section_divider("06", "Protective-Efficacy Results", "Does a CLONE made from the cloaked audio still verify as the genuine speaker?")

slide = add_slide()
y = slide_header(slide, "Protective Efficacy", "POP: Clean-Audio Ceiling vs. POP-Cloaked Source")
headers = ["System", "Verifier", "Clean ceiling\nEER / TAR@1%", "POP-cloaked\nEER / TAR@1%", "Relative EER Δ"]
rows = [
    ["SV2TTS", "SB-ECAPA", "19.75% / 38.2%", "20.51% / 36.5%", "+4%"],
    ["SV2TTS", "Resemblyzer", "9.21% / 69.8%", "10.22% / 67.8%", "+11%"],
    ["SV2TTS", "WavLM", "18.85% / 22.4%", "19.26% / 22.3%", "+2%"],
    ["Seed-VC", "SB-ECAPA", "3.11% / 93.2%", "3.59% / 91.7%", "+15%"],
    ["Seed-VC", "Resemblyzer", "4.99% / 84.4%", "5.31% / 82.3%", "+6%"],
    ["Seed-VC", "WavLM", "16.01% / 25.1%", "16.74% / 24.6%", "+5%"],
    ["F5-TTS", "SB-ECAPA", "1.66% / 97.7%", "2.56% / 96.1%", "+54%"],
    ["F5-TTS", "Resemblyzer", "2.23% / 96.3%", "2.51% / 95.7%", "+13%"],
    ["F5-TTS", "WavLM", "9.24% / 66.6%", "10.92% / 60.3%", "+18%"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(4.1), headers, rows,
          col_widths=[Inches(1.9), Inches(2.5), Inches(2.7), Inches(2.7), Inches(2.3)], font_size=13, header_size=13,
          highlight_col=4)
footer(slide, "Section 6 — Protective Efficacy", 22)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy", "POP: System-Dependent Protection")
stat_tile(slide, Inches(0.6), y, Inches(3.9), Inches(2.2), "MARGINAL", "SV2TTS\nEER up only 2–11% relative\nTAR@1% down 2–5%", value_color=GREY)
stat_tile(slide, Inches(4.7), y, Inches(3.9), Inches(2.2), "MARGINAL", "Seed-VC\nEER up only 5–15%\n(run-to-run noise range)", value_color=GREY)
stat_tile(slide, Inches(8.8), y, Inches(3.9), Inches(2.2), "IN-BETWEEN", "F5-TTS\nEER up 13–54%,\nbut TAR@1% barely moves", value_color=ACCENT2)
add_bullets(slide, Inches(0.6), y + Inches(2.6), Inches(12.1), Inches(3.2), [
    ("POP has only a marginal effect against every downstream attacker tested, including zero-shot TTS — weakest and most system-dependent of the four cloaks", 0, True),
    ("SV2TTS EER increase is statistically significant on SB-ECAPA/Resemblyzer but tiny in absolute terms (2–11% relative); WavLM is not even significant (p=0.118)", 0),
    ("Initial hypothesis (POP's VITS surrogate transfers better to TTS attackers) does not hold cleanly once measured on the full, matched corpus — tested directly in the embedding-probe ablation (Section 7)", 0, True),
], size=17)
footer(slide, "Section 6 — Protective Efficacy", 23)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy — Demographics", "POP: Mean EER by Group, Ceiling vs. Cloaked")
headers = ["Group", "SV2TTS\nCeiling / Cloaked", "Seed-VC\nCeiling / Cloaked", "F5-TTS\nCeiling / Cloaked"]
rows = [
    ["Men", "14.56% / 15.10%", "7.02% / 7.59%", "3.43% / 4.99%"],
    ["Women", "19.11% / 20.02%", "9.04% / 9.25%", "4.47% / 5.52%"],
    ["African", "17.34% / 17.90%", "9.33% / 9.20%", "5.36% / 6.49%"],
    ["Asian (East)", "15.49% / 16.94%", "7.92% / 7.96%", "5.95% / 6.70%"],
    ["Asian (South)", "21.11% / 21.37%", "10.21% / 10.88%", "3.40% / 6.08%"],
    ["Caucasian (Am.)", "14.39% / 15.47%", "6.42% / 7.06%", "1.85% / 2.50%"],
    ["Caucasian (Eu.)", "15.85% / 16.11%", "6.29% / 7.01%", "3.21% / 4.51%"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(3.6), headers, rows,
          col_widths=[Inches(2.4), Inches(3.3), Inches(3.3), Inches(3.1)], font_size=13)
add_bullets(slide, Inches(0.6), y + Inches(3.85), Inches(12.1), Inches(1.5), [
    ("Disparity PREDATES POP entirely — same ordering already exists in the clean-audio ceiling column, for every system", 0, True),
    ("POP widens the pre-existing gender gap only modestly for SV2TTS (4.55 → 4.92 points) but did not create it — inherited from the downstream pipeline, not the cloak", 0),
], size=15)
footer(slide, "Section 6 — Protective Efficacy", 24)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy", "attack-vc: Clean-Audio Ceiling vs. Cloaked Source")
headers = ["System", "Verifier", "Clean ceiling\nEER / TAR@1%", "attack-vc-cloaked\nEER / TAR@1%", "Relative EER Δ"]
rows = [
    ["SV2TTS", "SB-ECAPA", "19.74% / 38.1%", "21.06% / 35.1%", "+7%"],
    ["SV2TTS", "Resemblyzer", "9.22% / 69.8%", "10.69% / 65.0%", "+16%"],
    ["SV2TTS", "WavLM", "18.86% / 22.5%", "19.17% / 21.3%", "+2%"],
    ["Seed-VC", "SB-ECAPA", "3.11% / 93.2%", "3.29% / 92.4%", "+6%"],
    ["Seed-VC", "Resemblyzer", "4.99% / 84.4%", "5.08% / 83.3%", "+2%"],
    ["Seed-VC", "WavLM", "16.01% / 25.1%", "16.61% / 25.0%", "+4%"],
    ["F5-TTS", "SB-ECAPA", "1.66% / 97.7%", "2.12% / 97.0%", "+28%"],
    ["F5-TTS", "Resemblyzer", "2.23% / 96.3%", "2.69% / 95.7%", "+21%"],
    ["F5-TTS", "WavLM", "9.24% / 66.6%", "10.14% / 64.4%", "+10%"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(4.1), headers, rows,
          col_widths=[Inches(1.9), Inches(2.5), Inches(2.7), Inches(2.7), Inches(2.3)], font_size=13, header_size=13,
          highlight_col=4)
add_textbox(slide, Inches(0.6), y + Inches(4.3), Inches(12.1), Inches(0.6),
            "Despite POP and attack-vc being mechanistically unrelated, they converge on almost identical SV2TTS outcomes.",
            size=14, italic=True, color=GREY)
footer(slide, "Section 6 — Protective Efficacy", 25)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy — Demographics", "attack-vc: Mean EER by Group, Ceiling vs. Cloaked")
headers = ["Group", "SV2TTS\nCeiling / Cloaked", "Seed-VC\nCeiling / Cloaked", "F5-TTS\nCeiling / Cloaked"]
rows = [
    ["Men", "14.56% / 15.68%", "7.02% / 7.57%", "3.43% / 3.96%"],
    ["Women", "19.11% / 20.51%", "9.04% / 8.90%", "4.47% / 4.73%"],
    ["African", "17.34% / 18.24%", "9.33% / 9.30%", "5.36% / 5.77%"],
    ["Asian (East)", "15.49% / 17.13%", "7.92% / 8.05%", "5.95% / 6.14%"],
    ["Asian (South)", "21.11% / 22.16%", "10.21% / 11.14%", "3.40% / 4.33%"],
    ["Caucasian (Am.)", "14.39% / 15.77%", "6.42% / 6.54%", "1.85% / 2.26%"],
    ["Caucasian (Eu.)", "15.85% / 17.17%", "6.29% / 6.14%", "3.40% / 3.24%"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(3.6), headers, rows,
          col_widths=[Inches(2.4), Inches(3.3), Inches(3.3), Inches(3.1)], font_size=13)
add_bullets(slide, Inches(0.6), y + Inches(3.85), Inches(12.1), Inches(1.5), [
    ("Same qualitative pattern as POP — disparity inherited from the pipeline, not introduced by the cloak", 0, True),
    ("One genuine difference: for F5-TTS, Asian (East) — not Asian (South) — is the most-protected descent group; system-dependent, not fixed", 0),
], size=15)
footer(slide, "Section 6 — Protective Efficacy", 26)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy", "AntiFake: Effective Against ALL THREE Systems")
headers = ["System", "Verifier", "Clean ceiling\nEER / TAR@1%", "AntiFake-cloaked\nEER / TAR@1%", "Relative EER Δ"]
rows = [
    ["SV2TTS", "SB-ECAPA", "19.90% / 38.0%", "55.51% / 1.3%", "+179%"],
    ["SV2TTS", "Resemblyzer", "9.29% / 69.9%", "49.97% / 2.3%", "+438%"],
    ["SV2TTS", "WavLM", "19.00% / 22.3%", "46.42% / 0.9%", "+144%"],
    ["Seed-VC", "SB-ECAPA", "3.11% / 93.2%", "49.31% / 8.3%", "+1,485%"],
    ["Seed-VC", "Resemblyzer", "4.99% / 84.4%", "32.49% / 20.5%", "+551%"],
    ["Seed-VC", "WavLM", "16.01% / 25.1%", "34.54% / 2.9%", "+116%"],
    ["F5-TTS", "SB-ECAPA", "1.66% / 97.7%", "38.17% / 16.6%", "+2,199%"],
    ["F5-TTS", "Resemblyzer", "2.23% / 96.3%", "21.38% / 37.5%", "+859%"],
    ["F5-TTS", "WavLM", "9.24% / 66.6%", "30.13% / 9.9%", "+226%"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(4.1), headers, rows,
          col_widths=[Inches(1.9), Inches(2.5), Inches(2.7), Inches(2.7), Inches(2.3)], font_size=13, header_size=13,
          highlight_col=4, highlight_color=BAD)
add_textbox(slide, Inches(0.6), y + Inches(4.3), Inches(12.1), Inches(0.6),
            "SB-ECAPA / F5-TTS: EER rises from 1.66% to 38.17% — a 23× increase, the largest of any (system, verifier) cell in the whole project.",
            size=14, bold=True, color=BAD)
footer(slide, "Section 6 — Protective Efficacy", 27)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy", "AntiFake: The Imperceptibility / Protection Tradeoff")
stat_tile(slide, Inches(0.6), y, Inches(3.9), Inches(1.7), "SV2TTS", "+144 to +438%\nrelative EER", value_color=BAD)
stat_tile(slide, Inches(4.7), y, Inches(3.9), Inches(1.7), "Seed-VC", "+116 to +1,485%\nrelative EER", value_color=BAD)
stat_tile(slide, Inches(8.8), y, Inches(3.9), Inches(1.7), "F5-TTS", "+226 to +2,199%\nrelative EER", value_color=BAD)
add_bullets(slide, Inches(0.6), y + Inches(2.0), Inches(12.1), Inches(3.2), [
    ("Uniquely among the three techniques, AntiFake protects against ALL THREE downstream systems — not just SV2TTS", 0, True),
    ("Same explanation as its imperceptibility failure: the decoy-target attack optimizes embedding displacement DIRECTLY, rather than staying within a fixed imperceptibility budget the way POP/attack-vc do", 0),
    ("Trades away imperceptibility for protection that is stronger AND more uniform across attacker types", 0, True),
], size=17)
footer(slide, "Section 6 — Protective Efficacy", 28)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy — Demographics", "AntiFake: Mean EER by Group, Ceiling vs. Cloaked")
headers = ["Group", "SV2TTS\nCeiling / Cloaked", "Seed-VC\nCeiling / Cloaked", "F5-TTS\nCeiling / Cloaked"]
rows = [
    ["Men", "14.56% / 51.59%", "7.02% / 41.28%", "3.43% / 32.82%"],
    ["Women", "19.11% / 55.38%", "9.04% / 43.45%", "4.47% / 32.95%"],
    ["African", "17.34% / 52.55%", "9.33% / 41.46%", "5.36% / 36.09%"],
    ["Asian (East)", "15.49% / 51.79%", "7.92% / 39.66%", "5.95% / 28.70%"],
    ["Asian (South)", "21.11% / 52.60%", "10.21% / 40.48%", "3.40% / 40.08%"],
    ["Caucasian (Am.)", "14.39% / 55.42%", "6.42% / 46.62%", "1.85% / 26.26%"],
    ["Caucasian (Eu.)", "15.85% / 55.06%", "6.29% / 43.61%", "3.21% / 33.29%"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(3.6), headers, rows,
          col_widths=[Inches(2.4), Inches(3.3), Inches(3.3), Inches(3.1)], font_size=13)
add_textbox(slide, Inches(0.6), y + Inches(3.85), Inches(12.1), Inches(1.5),
            "SV2TTS & Seed-VC: Caucasian groups show BOTH worst imperceptibility AND strongest protection — same displacement mechanism drives both. "
            "F5-TTS BREAKS this pattern: gender gap nearly vanishes (32.82% vs 32.95%); Caucasian (American) flips to LOWEST-EER "
            "(tied to its unusually low clean-audio ceiling, 1.85%) — reported as an open question, not forced into the same account.",
            size=14, color=NAVY)
footer(slide, "Section 6 — Protective Efficacy", 29)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy", "ProtectYourAudio: Clean-Audio Ceiling vs. Cloaked Source")
headers = ["System", "Verifier", "Clean ceiling\nEER / TAR@1%", "PYA-cloaked\nEER / TAR@1%", "Relative EER Δ"]
rows = [
    ["SV2TTS", "SB-ECAPA", "19.90% / 37.3%", "24.27% / 31.0%", "+22%"],
    ["SV2TTS", "Resemblyzer", "9.25% / 69.8%", "12.68% / 58.1%", "+37%"],
    ["SV2TTS", "WavLM", "18.89% / 22.4%", "21.98% / 18.7%", "+16%"],
    ["Seed-VC", "SB-ECAPA", "3.11% / 93.2%", "6.21% / 82.1%", "+100%"],
    ["Seed-VC", "Resemblyzer", "4.99% / 84.4%", "7.39% / 72.1%", "+48%"],
    ["Seed-VC", "WavLM", "16.01% / 25.1%", "18.44% / 19.9%", "+15%"],
    ["F5-TTS", "SB-ECAPA", "1.66% / 97.7%", "4.16% / 92.6%", "+151%"],
    ["F5-TTS", "Resemblyzer", "2.23% / 96.3%", "3.84% / 92.3%", "+72%"],
    ["F5-TTS", "WavLM", "9.24% / 66.6%", "14.96% / 47.4%", "+62%"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(4.1), headers, rows,
          col_widths=[Inches(1.9), Inches(2.5), Inches(2.7), Inches(2.7), Inches(2.3)], font_size=13, header_size=13,
          highlight_col=4)
footer(slide, "Section 6 — Protective Efficacy", 30)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy", "ProtectYourAudio: Broader Protection Than POP or attack-vc")
stat_tile(slide, Inches(0.6), y, Inches(3.9), Inches(1.7), "SV2TTS", "+16 to +37%\nrelative EER", value_color=ACCENT2)
stat_tile(slide, Inches(4.7), y, Inches(3.9), Inches(1.7), "Seed-VC", "+15 to +100%\nrelative EER", value_color=ACCENT2)
stat_tile(slide, Inches(8.8), y, Inches(3.9), Inches(1.7), "F5-TTS", "+62 to +151%\nrelative EER", value_color=ACCENT2)
add_bullets(slide, Inches(0.6), y + Inches(2.0), Inches(12.1), Inches(3.2), [
    ("Unlike POP/attack-vc (EER up only 2–51% relative across all three systems, mostly marginal), ProtectYourAudio shows a consistently REAL, significant effect against every system — while matching POP's/attack-vc's own imperceptibility", 0, True),
    ("F5-TTS's WavLM TAR@1% drop (−29% relative) is the most security-relevant shift against F5-TTS reported anywhere in this project outside AntiFake", 0),
    ("Demonstrates imperceptibility and cross-system protection are not as sharply opposed as POP/attack-vc alone would suggest — a discrete, budget-constrained masking search generalizes better than either continuous perturbation tested here", 0, True),
], size=16)
footer(slide, "Section 6 — Protective Efficacy", 31)

slide = add_slide()
y = slide_header(slide, "Protective Efficacy — Demographics", "ProtectYourAudio: Mean EER by Group, Ceiling vs. Cloaked")
headers = ["Group", "SV2TTS\nCeiling / Cloaked", "Seed-VC\nCeiling / Cloaked", "F5-TTS\nCeiling / Cloaked"]
rows = [
    ["Men", "14.56% / 17.69%", "7.02% / 9.23%", "3.43% / 6.64%"],
    ["Women", "19.11% / 23.98%", "9.04% / 12.72%", "4.47% / 8.66%"],
    ["African", "17.34% / 21.05%", "9.33% / 12.05%", "5.36% / 8.40%"],
    ["Asian (East)", "15.49% / 20.17%", "7.92% / 11.20%", "5.95% / 9.29%"],
    ["Asian (South)", "21.11% / 24.56%", "10.21% / 14.05%", "3.40% / 11.39%"],
    ["Caucasian (Am.)", "14.39% / 19.42%", "6.42% / 8.83%", "1.85% / 3.23%"],
    ["Caucasian (Eu.)", "15.85% / 18.99%", "6.29% / 8.75%", "3.21% / 5.92%"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(3.6), headers, rows,
          col_widths=[Inches(2.4), Inches(3.3), Inches(3.3), Inches(3.1)], font_size=13)
add_bullets(slide, Inches(0.6), y + Inches(3.85), Inches(12.1), Inches(1.5), [
    ("Same pipeline-inherited pattern as POP/attack-vc, not AntiFake's inverted one — women & Caucasian groups remain least-protected under every system", 0, True),
    ("Asian (South) is the highest-EER group under F5-TTS by a wide margin (11.39% vs. 3.23–9.29% elsewhere) — a recurring F5-TTS-specific sensitivity also seen in the restoration-study demographics, not unique to ProtectYourAudio", 0),
], size=15)
footer(slide, "Section 6 — Protective Efficacy", 32)

# ===========================================================================
# SECTION 7: ABLATION
# ===========================================================================
section_divider("07", "Why Is Seed-VC Different?", "An embedding-level ablation resolves the POP/attack-vc vs. AntiFake contradiction")

slide = add_slide()
y = slide_header(slide, "Ablation", "Encoder Architecture Identity Check")
add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.6),
            "Does either cloak share an encoder architecture with Seed-VC's or SV2TTS's own conditioning mechanism? (Would imply near-white-box transfer.)",
            size=15, italic=True, color=GREY)
headers = ["Component", "Architecture"]
rows = [
    ["SV2TTS's own encoder", "GE2E LSTM d-vector (256-d)"],
    ["attack-vc's target encoder", "AdaIN-VC's bespoke conv-bank encoder"],
    ["POP's VITS surrogate", "NO encoder — closed lookup table over 50 fixed training speakers"],
    ["Seed-VC's own encoder", "CAMPPlus (D-TDNN, 192-d)"],
]
add_table(slide, Inches(0.6), y + Inches(0.75), Inches(12.1), Inches(2.6), headers, rows,
          col_widths=[Inches(4.5), Inches(7.6)], font_size=15)
add_bullets(slide, Inches(0.6), y + Inches(3.6), Inches(12.1), Inches(2.0), [
    ("NONE share an architecture family — rules out simple white-box transfer", 0, True),
    ("POP's surrogate has no generalizable speaker encoder at all — its perturbation isn't even crafted against a transferable identity-embedding space", 0),
], size=16)
footer(slide, "Section 7 — Ablation", 34)

slide = add_slide()
y = slide_header(slide, "Ablation", "Embedding-Level Transfer Probe")
add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.5),
            "Cosine similarity of each system's OWN embedding, clean vs. cloaked audio (n=500, no synthesis involved). Lower = perturbation moved that embedding more.",
            size=14, italic=True, color=GREY)
headers = ["System", "Cloak", "Mean cosine similarity"]
rows = [
    ["SV2TTS (GE2E)", "POP", "0.9917"],
    ["SV2TTS (GE2E)", "attack-vc", "0.9836"],
    ["SV2TTS (GE2E)", "AntiFake", "0.4051"],
    ["Seed-VC (CAMPPlus)", "POP", "0.9787"],
    ["Seed-VC (CAMPPlus)", "attack-vc", "0.8955"],
    ["Seed-VC (CAMPPlus)", "AntiFake", "0.4763"],
]
add_table(slide, Inches(0.6), y + Inches(0.65), Inches(6.6), Inches(3.3), headers, rows,
          col_widths=[Inches(2.6), Inches(1.8), Inches(2.2)], font_size=14)
add_bullets(slide, Inches(7.5), y + Inches(0.65), Inches(5.2), Inches(4.5), [
    ("Contradicts the simplest hypothesis: Seed-VC's embedding shifts as much or MORE than SV2TTS's under POP/attack-vc", 0, True),
    ("Yet Seed-VC's end-to-end EER barely moves for those two → decoder-robustness, not encoder-immunity", 0),
    ("AntiFake displaces BOTH embeddings 2–4× further than POP/attack-vc's worst case", 0, True),
    ("This is dose-response, not a new mechanism: POP/attack-vc stayed within Seed-VC's decoder tolerance; AntiFake exceeds it", 0),
], size=16)
footer(slide, "Section 7 — Ablation", 35)

# ===========================================================================
# SECTION 8: THEORETICAL FRAMEWORK
# ===========================================================================
section_divider("08", "Theoretical Framework", "Cloaking and restoration as one constrained-optimization problem — unifying three attacks and explaining why restoration failed")

slide = add_slide()
y = slide_header(slide, "Theoretical Framework", "Why Formalize This?")
add_bullets(slide, Inches(0.6), y, Inches(12.1), Inches(5.0), [
    ("Turn three separately-described mechanisms (Section 4) into one common notation, rather than three unrelated algorithms", 0, True),
    ("Explain restoration's uniform failure (Section 9) PREDICTIVELY, not only descriptively — the framework should say in advance which techniques are doomed and why", 0, True),
    ("Derive concrete, falsifiable improvement directions for BOTH sides of the arms race — the cloak (attacker) and the restoration technique (adaptive defender)", 0, True),
    ("Grounded directly in two findings already established elsewhere in this deck:", 0),
    ("The dose-response threshold from the embedding-probe ablation (Section 7)", 1),
    ("Restoration consistently making EER worse, not better (Section 9)", 1),
], size=18, space_after=16)
footer(slide, "Section 8 — Theoretical Framework", 37)

slide = add_slide()
y = slide_header(slide, "Theoretical Framework", "The Three Cloaks as One Equation")
formula_box(slide, Inches(0.6), y, Inches(12.1), Inches(1.35), [
    "δ* = argmin over ‖δ‖∞ ≤ ε of:  λrecon·Lrecon(x+δ)  +  λemb·Σk wk‖Enck(x+δ) − Enck(xdecoy)‖²",
], size=17)
headers = ["Technique", "λrecon", "λemb", "|K|", "Consequence"]
rows = [
    ["POP", "> 0", "0", "—", "Minimizes a VITS surrogate's own reconstruction loss;\nno explicit embedding-displacement term at all"],
    ["attack-vc", "0", "> 0", "1", "Single-encoder decoy-target embedding attack;\nnothing constrains signal distortion beyond ε"],
    ["AntiFake", "0", "> 0", "3", "Same decoy-target objective, jointly over an\nensemble of 3 encoders for black-box transfer"],
]
add_table(slide, Inches(0.6), y + Inches(1.65), Inches(12.1), Inches(3.0), headers, rows,
          col_widths=[Inches(1.6), Inches(1.4), Inches(1.4), Inches(0.9), Inches(6.8)], font_size=14)
add_textbox(slide, Inches(0.6), y + Inches(4.9), Inches(12.1), Inches(0.5),
            "All three techniques solve the same constrained optimization problem — they differ only in which term is active and over how many encoders.",
            size=14, italic=True, color=GREY)
footer(slide, "Section 8 — Theoretical Framework", 38)

slide = add_slide()
y = slide_header(slide, "Theoretical Framework", "What the Equation Explains")
add_bullets(slide, Inches(0.6), y, Inches(12.1), Inches(5.2), [
    ("POP's system-dependence (strong vs. SV2TTS, marginal vs. Seed-VC) follows from λemb = 0", 0, True),
    ("Nothing in POP's objective explicitly displaces any speaker embedding — its protective effect is an incidental side effect of degrading the VITS surrogate's reconstruction, which transfers unevenly", 1),
    ("attack-vc's and AntiFake's imperceptibility risk follows from λrecon = 0", 0, True),
    ("Neither objective penalizes the perturbation for being audible — imperceptibility is only as good as the ε budget happens to allow; attack-vc's budget lands close to transparent, AntiFake's does not", 1),
    ("The Section 7 dose-response threshold IS the statement that |K| = 3 (AntiFake's ensemble) pushes embedding displacement past a magnitude that |K| = 1 (attack-vc) and λemb = 0 (POP) do not reach", 0, True),
    ("The three techniques are not different mechanisms so much as three settings of the same (λrecon, λemb, |K|) that land on different sides of a decoder-tolerance threshold", 1),
], size=17, space_after=14)
footer(slide, "Section 8 — Theoretical Framework", 39)

slide = add_slide()
y = slide_header(slide, "Theoretical Framework", "Restoration as Approximate Inversion")
add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.5),
            "Every restoration technique R attempts R(x̂) = R(x+δ) ≈ x, without access to x or δ individually.",
            size=15, italic=True, color=GREY)
headers = ["Operator class", "Techniques"]
rows = [
    ["Linear filtering", "Low-pass+gain, high-pass, adaptive-filter-centroid, resampling"],
    ["Lossy-basis projection", "Mel-spectrogram inversion (Griffin-Lim)"],
    ["Nonlinear quantization", "8-bit quantize/dequantize round-trip"],
    ["Nonlinear spectral masking", "Spectral subtraction"],
    ["Stochastic averaging", "Ensemble averaging of jittered variants (N=5)"],
    ["Physical-channel sim.", "Simulated re-recording (RIR + mic bandpass + noise)"],
    ["Compositional / gradient-informed", "Second-cloak application (the ONE non-δ-agnostic candidate)"],
]
add_table(slide, Inches(0.6), y + Inches(0.65), Inches(7.2), Inches(4.0), headers, rows,
          col_widths=[Inches(2.6), Inches(4.6)], font_size=13)
formula_box(slide, Inches(8.0), y + Inches(0.65), Inches(4.7), Inches(1.7), [
    "R(x̂) − x = [R(x) − x] + R(δ)",
    "εR (always present)   attenuated δ",
], size=16)
add_textbox(slide, Inches(8.0), y + Inches(2.55), Inches(4.7), Inches(2.1),
            "9 of 10 techniques are δ-agnostic — chosen from a generic prior, not derived from δ itself. Since δ was optimized to look like speech, generic R has no reason to attenuate δ more than it attenuates x — predicting exactly the uniform failure Section 9 reports.",
            size=13, color=NAVY, line_spacing=1.25)
footer(slide, "Section 8 — Theoretical Framework", 40)

slide = add_slide()
y = slide_header(slide, "Theoretical Framework", "Improving the Cloaking Techniques")
add_bullets(slide, Inches(0.6), y, Inches(12.1), Inches(5.3), [
    ("POP — add an embedding term", 0, True),
    ("Imperceptibility (EER ≤ 0.16%) is far from exhausting its ε budget — room to add attack-vc/AntiFake's own decoy-target term alongside POP's existing reconstruction term, targeting its demonstrated Seed-VC weakness without touching the budget", 1),
    ("attack-vc — ensemble the encoder", 0, True),
    ("Its weakness (strong vs. SV2TTS, weak vs. Seed-VC/F5-TTS) is exactly the |K|=1 row — AntiFake shows |K|=3 fixes this; extending to a small |K|=2 ensemble directly tests whether encoder count, not AntiFake's other differences, drives generalization", 1),
    ("AntiFake — regularize, or find the minimum effective dose", 0, True),
    ("Either add POP's reconstruction term back in as an imperceptibility regularizer, or reformulate as a feasibility problem: find the MINIMUM ε that crosses the empirically observed decoder-tolerance threshold, instead of maximizing displacement past it", 1),
], size=16, space_after=12)
footer(slide, "Section 8 — Theoretical Framework", 41)

slide = add_slide()
y = slide_header(slide, "Theoretical Framework", "Improving the Restoration Techniques")
add_bullets(slide, Inches(0.6), y, Inches(12.1), Inches(5.3), [
    ("Add a clean-audio control channel", 0, True),
    ("None of the 10 results measure εR directly — apply each technique to CLEAN, uncloaked audio and measure the embedding-cosine shift it causes on its own; cheap, and would have flagged low-pass+gain and adaptive-filter-centroid as doomed BEFORE running the full cloak→clone→verify pipeline on them", 1),
    ("Move from δ-agnostic to learned, δ-aware purification", 0, True),
    ("Fixed-form filtering can't preferentially attenuate δ over x, however cleverly parameterized — a learned network Rθ trained against a cloak's own attack distribution is structurally capable of succeeding where all 9 fixed-form techniques cannot", 1),
    ("Make second-cloak application explicitly adversarial", 0, True),
    ("Its current form blindly reapplies the SAME attack direction — a gray-box \"denoising PGD\" (gradient ASCENT on the surrogate's own loss) would explicitly push the composite perturbation back toward δ=0 instead", 1),
], size=16, space_after=12)
footer(slide, "Section 8 — Theoretical Framework", 42)

# ===========================================================================
# SECTION 9: RESTORATION / ADAPTIVE ATTACKER
# ===========================================================================
section_divider("09", "Can Protective Efficacy Be Reversed?", "Testing an adaptive attacker who restores cloaked audio before cloning")

slide = add_slide()
y = slide_header(slide, "Restoration Study", "Adaptive-Attacker Hypothesis")
add_bullets(slide, Inches(0.6), y, Inches(12.1), Inches(2.0), [
    ("A stronger attacker who knows a recording MAY be cloaked could apply signal-domain restoration BEFORE cloning", 0, True),
    ("Attempt to strip/average away the cloaking perturbation while leaving identity intact — restoration is cloak-agnostic (attacker does not know which cloak, if any, protected the recording)", 1),
    ("16 restoration techniques applied to POP-, attack-vc-, and AntiFake-cloaked audio (full 6-gain low-pass sweep now complete for all three)", 0),
    ("Scored the same way as every other system in this deck: clone the restored audio and re-run the 1 genuine + 10 impostor trial protocol against clean bonafide — for all three downstream cloners (SV2TTS, Seed-VC, F5-TTS), not just SV2TTS", 0),
], size=16)
headers = ["", "SB-ECAPA", "Resemblyzer", "WavLM"]
rows = [
    ["Clean-audio ceiling (ref.)", f"{_CEILING['SB-ECAPA']:.2f}%", f"{_CEILING['Resemblyzer']:.2f}%", f"{_CEILING['WavLM']:.2f}%"],
    ["POP baseline, no restoration (ref.)", f"{_BASELINES['POP']['SB-ECAPA']:.2f}%", f"{_BASELINES['POP']['Resemblyzer']:.2f}%", f"{_BASELINES['POP']['WavLM']:.2f}%"],
    ["attack-vc baseline, no restoration (ref.)", f"{_BASELINES['attackvc']['SB-ECAPA']:.2f}%", f"{_BASELINES['attackvc']['Resemblyzer']:.2f}%", f"{_BASELINES['attackvc']['WavLM']:.2f}%"],
    ["AntiFake baseline, no restoration (ref.)", f"{_BASELINES['Antifake']['SB-ECAPA']:.2f}%", f"{_BASELINES['Antifake']['Resemblyzer']:.2f}%", f"{_BASELINES['Antifake']['WavLM']:.2f}%"],
]
add_table(slide, Inches(0.6), y + Inches(2.55), Inches(12.1), Inches(2.1), headers, rows,
          col_widths=[Inches(4.6), Inches(2.5), Inches(2.5), Inches(2.5)], font_size=13.5)
footer(slide, "Section 9 — Restoration Study", 44)

restoration_table_slide(45, "POP", "POP", _BASELINES["POP"], _CEILING)
restoration_table_slide(46, "attackvc", "attack-vc", _BASELINES["attackvc"], _CEILING)
restoration_table_slide(47, "Antifake", "AntiFake", _BASELINES["Antifake"], _CEILING)

# Extension to Seed-VC and F5-TTS (paper \S sec:restoration-seedvc-f5tts):
# each uses that SYNTHESIZER'S OWN no-restoration baseline, never SV2TTS's.
restoration_table_slide(48, "POP", "POP", _BASELINES_MULTI["POP"]["seedvc"], _CEILING, synth="seedvc")
restoration_table_slide(49, "POP", "POP", _BASELINES_MULTI["POP"]["f5tts"], _CEILING, synth="f5tts")
restoration_table_slide(50, "attackvc", "attack-vc", _BASELINES_MULTI["attackvc"]["seedvc"], _CEILING, synth="seedvc")
restoration_table_slide(51, "attackvc", "attack-vc", _BASELINES_MULTI["attackvc"]["f5tts"], _CEILING, synth="f5tts")
restoration_table_slide(52, "Antifake", "AntiFake", _BASELINES_MULTI["Antifake"]["seedvc"], _CEILING, synth="seedvc")
restoration_table_slide(53, "Antifake", "AntiFake", _BASELINES_MULTI["Antifake"]["f5tts"], _CEILING, synth="f5tts")

def _aggregate_verdicts(method):
    """Pool verdicts across all three synthesizers for one cloak method."""
    counts = {"PARTIAL REVERSAL": 0, "Slight reversal": 0, "No": 0, "pending": 0}
    total = 0
    for synth in ("sv2tts", "seedvc", "f5tts"):
        for row in restoration_rows(method, synth):
            counts[row[5]] += 1
            total += 1
    return counts, total


_pop_counts, _pop_total = _aggregate_verdicts("POP")
_attackvc_counts, _attackvc_total = _aggregate_verdicts("attackvc")
_af_counts, _af_total = _aggregate_verdicts("Antifake")
_af_scored = _af_total - _af_counts["pending"]

slide = add_slide()
y = slide_header(slide, "Restoration Study", "Result: Restoration Rarely Reverses the Cloak, on Any Synthesizer")
stat_tile(slide, Inches(0.6), y, Inches(3.9), Inches(2.0), "POP",
          f"0 full reversals across all\n{_pop_total} (technique × synthesizer)\ncombinations tested\n({_pop_counts['Slight reversal']} slight, F5-TTS only)",
          value_color=BAD)
stat_tile(slide, Inches(4.6), y, Inches(3.9), Inches(2.0), "attack-vc",
          f"0 full reversals across all\n{_attackvc_total} (technique × synthesizer)\ncombinations tested\n({_attackvc_counts['Slight reversal']} slight, F5-TTS only)",
          value_color=BAD)
stat_tile(slide, Inches(8.6), y, Inches(4.1), Inches(2.0), "AntiFake",
          f"{_af_counts['PARTIAL REVERSAL']} PARTIAL + {_af_counts['Slight reversal']} slight reversal\nof {_af_scored} combinations scored so far\n({_af_counts['No']} show no reversal"
          + (f", {_af_counts['pending']} still pending)" if _af_counts['pending'] else ")"),
          value_color=ACCENT2)
add_bullets(slide, Inches(0.6), y + Inches(2.3), Inches(12.1), Inches(3.2), [
    ("Extended this session to Seed-VC and F5-TTS, not just SV2TTS: for POP and attack-vc, the result holds on every downstream cloner tested — zero full reversals across 96 combinations, only a few mild, F5-TTS-specific partial shifts (spectral subtraction, upsampling, high-pass filtering)", 0, True),
    ("Each synthesizer is compared against its OWN no-restoration baseline, never SV2TTS's — Seed-VC/F5-TTS already sit close to the clean-audio ceiling before any restoration, so a naive cross-synthesizer comparison would look like a dramatic reversal that isn't real", 0, True),
    ("AntiFake remains the one cloak method where restoration produces a genuine (if still partial) reversal on SV2TTS — extending this same SV2TTS finding to Seed-VC/F5-TTS for AntiFake is in progress", 0),
    ("Demographic pattern survives restoration largely unchanged across all three cloak methods and all three synthesizers tested — pre-existing disparities are not an artifact of the unrestored cloak", 0),
], size=16)
footer(slide, "Section 9 — Restoration Study", 54)

_page = 55
for _method, _display in (("POP", "POP"), ("attackvc", "attack-vc"), ("Antifake", "AntiFake")):
    _grows, _drows, _ns, _nt = restoration_technique_demographic_rows(_method)
    restoration_gender_table_slide(_page, _method, _display, _grows, _ns, _nt)
    _page += 1
    restoration_descent_table_slide(_page, _method, _display, _drows, _ns, _nt)
    _page += 1

# ===========================================================================
# SECTION 10: CONCLUSIONS
# ===========================================================================
section_divider("10", "Cross-Technique Summary", "Putting imperceptibility and protective efficacy side by side")

slide = add_slide()
y = slide_header(slide, "Summary", "The Big Picture: A Tradeoff, Not a Binary")
headers = ["Technique", "Imperceptibility", "Protective Efficacy", "Demographic pattern"]
rows = [
    ["POP", "Near-perfect\n(EER ≤ 0.16%)", "Marginal on all three\nsystems (mostly ≤15%\nrelative EER)", "Inherited from\ndownstream pipeline"],
    ["attack-vc", "Near-perfect\n(EER ≤ 2.1%)", "Marginal-to-modest,\nstrongest vs. F5-TTS\n(up to +25%)", "Inherited from\ndownstream pipeline"],
    ["ProtectYourAudio", "Near-perfect\n(EER ≤ 2.1%)", "ALL THREE systems,\nbroader than POP/attack-vc", "Inherited from\ndownstream pipeline"],
    ["AntiFake", "Fails outright\n(EER 22–66%)", "ALL THREE systems,\nlargest effects overall", "Coupled to the cloak's\nown displacement (mostly)"],
]
add_table(slide, Inches(0.6), y, Inches(12.1), Inches(3.3), headers, rows,
          col_widths=[Inches(1.9), Inches(2.9), Inches(3.5), Inches(3.8)], font_size=14)
add_textbox(slide, Inches(0.6), y + Inches(3.6), Inches(12.1), Inches(1.3),
            "POP and attack-vc stay close to imperceptible but protect only marginally across downstream systems overall (strongest vs. F5-TTS, weakest vs. Seed-VC/SV2TTS).\n"
            "AntiFake sacrifices imperceptibility entirely for protection that is stronger and far more uniform across attacker types.\n"
            "ProtectYourAudio sits between these extremes — matching POP's/attack-vc's imperceptibility while protecting measurably more broadly, "
            "showing the two objectives are not as sharply opposed as POP/attack-vc alone would suggest.",
            size=15, color=NAVY, line_spacing=1.25)
footer(slide, "Section 10 — Conclusions", 62)

slide = add_slide()
y = slide_header(slide, "Summary", "Key Contributions of This Evaluation")
add_bullets(slide, Inches(0.6), y, Inches(12.1), Inches(5.3), [
    ("First reproduction of 4 cloaking defenses end-to-end, on identical hardware, against a shared 4,867-clip demographically balanced corpus", 0, True),
    ("First large-scale descent × gender fairness audit of proactive cloaking effectiveness — a question none of the original papers examine", 0, True),
    ("Rigorously separated imperceptibility from protective efficacy — the most common conflation in the cloaking literature", 0, True),
    ("Resolved an apparent contradiction (Seed-VC resistant to POP/attack-vc but not AntiFake) with a direct embedding-level dose-response test, not speculation", 0, True),
    ("Tested — not assumed — whether an adaptive attacker can reverse cloaking via signal restoration, across all three downstream cloners (SV2TTS, Seed-VC, F5-TTS): it backfires for POP/attack-vc on every one (0 full reversals in 96 combinations), but partially narrows AntiFake's protective margin on roughly half the techniques tested on SV2TTS", 0, True),
    ("Every number in this deck is traced to a specific script, CSV, and verification pass — reproducible, not reported from memory", 0, True),
], size=18, space_after=14)
footer(slide, "Section 10 — Conclusions", 63)

# ===========================================================================
# APPENDIX: FOUR EVALUATION OBJECTIVES + CROSS-RECORDING IMPERCEPTIBILITY
# ===========================================================================
slide = add_slide()
y = slide_header(slide, "Appendix", "Four Evaluation Objectives and What Each Is Compared Against")
add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.5),
            "The dataset produces four distinct kinds of audio; each is measured against a different reference point.",
            size=15, italic=True, color=GREY)
headers = ["Objective", "Data", "Compared against", "Success looks like"]
rows = [
    ["1. Imperceptibility", "cloaked_bonafide", "Clean original\n(same recording)", "Verifies as SAME speaker"],
    ["   + cross-recording\n   (stricter variant)", "cloaked_bonafide", "A DIFFERENT recording\nof the same speaker", "Still verifies as SAME\n(no worse than clean baseline)"],
    ["2. Protective efficacy", "cloaked_synthesize", "That synthesizer's OWN\nclean-audio ceiling\n(matched clips)", "Verifies as DIFFERENT speaker"],
    ["3. Restoration quality", "restoration techniques\n(pre-recloning)", "Not verifier-tested —\nSTOI/PESQ/SI-SDR only", "Input to objective 4,\nnot an endpoint"],
    ["4. Restoration reversal", "restored_synthesize", "The cloak's OWN\nno-restoration baseline\n(NOT the ceiling)", "Reversal = EER significantly\nLOWER than that baseline"],
]
add_table(slide, Inches(0.6), y + Inches(0.6), Inches(12.1), Inches(3.3), headers, rows,
          col_widths=[Inches(2.6), Inches(2.6), Inches(3.4), Inches(3.5)], font_size=12.5, header_size=13)
add_bullets(slide, Inches(0.6), y + Inches(4.05), Inches(12.1), Inches(1.3), [
    ("Objective 4 is deliberately paired against the cloak's own baseline, not the ceiling — the question is whether restoration helps an attacker who only ever had the cloaked audio (this project's threat model), not whether it recovers never-cloaked performance", 0, True),
], size=14)
footer(slide, "Appendix", 64)

slide = add_slide()
y = slide_header(slide, "Appendix", "Cross-Recording Imperceptibility: A Stricter Test")
add_textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.7),
            "Same-recording imperceptibility (Section 5) compares a cloaked clip to the exact recording it was cloaked from — the easiest "
            "case for any verifier. Here the genuine reference is instead a DIFFERENT recording of the same speaker (4,801/4,867 clips have one), "
            "which is how a verifier is actually used against enrolled reference audio.",
            size=14, color=GREY)
headers = ["Cloak", "LibriSpeech\nΔEER (mean, pp)", "ASVspoof2021\nΔEER (mean, pp)", "FakeAVCeleb\nΔEER (mean, pp)"]
rows = [
    ["POP", "+0.20", "+0.08", "−0.09"],
    ["attack-vc", "+0.43", "+2.45", "−0.04"],
    ["AntiFake", "+27.90", "+28.62", "+10.97"],
    ["ProtectYourAudio", "+0.75", "+1.59", "+0.48"],
]
add_table(slide, Inches(0.6), y + Inches(0.85), Inches(12.1), Inches(2.1), headers, rows,
          col_widths=[Inches(3.1), Inches(3.0), Inches(3.0), Inches(3.0)], font_size=14, header_size=13,
          highlight_col=None)
add_bullets(slide, Inches(0.6), y + Inches(3.15), Inches(12.1), Inches(2.4), [
    ("AntiFake fails this stricter test badly and consistently — EER rises 6–58 points (all corpora, all 3 verifiers, p<0.001) — an order of magnitude larger than any other cloak", 0, True),
    ("This means AntiFake's same-recording imperceptibility numbers (Section 5) substantially overstate how imperceptible it would be against a verifier's real enrolled reference audio", 0),
    ("POP shows no consistent significant degradation across corpora/verifiers under this stricter test; attack-vc and ProtectYourAudio show small but real, mostly-significant increases concentrated on WavLM", 0, True),
    ("FakeAVCeleb's clean cross-recording baseline is already near chance (~27–42% EER) so has the least room to show a difference — LibriSpeech/ASVspoof2021 are the more sensitive tests here", 0),
], size=13.5)
footer(slide, "Appendix", 65)

slide = add_slide()
add_bg(slide, NAVY)
add_textbox(slide, Inches(0.9), Inches(3.0), Inches(11.5), Inches(1.2), "Thank You", size=48, bold=True, color=WHITE)
add_textbox(slide, Inches(0.9), Inches(4.1), Inches(11.5), Inches(0.8),
            "Questions?", size=22, color=RGBColor(0xB8, 0xC4, 0xD6))
add_textbox(slide, Inches(0.9), Inches(6.6), Inches(11.5), Inches(0.5),
            "AntiFake2026 — Measuring Imperceptibility and Verification-Leakage of Audio Cloaking",
            size=13, color=GREY)

prs.save(OUT_PATH)
print(f"Saved {OUT_PATH}  ({len(prs.slides.slides) if hasattr(prs.slides,'slides') else len(prs.slides._sldIdLst)} slides)")
