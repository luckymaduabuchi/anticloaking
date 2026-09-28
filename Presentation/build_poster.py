#!/usr/bin/env python3
"""Builds a single-slide, print-size (3ft x 4ft, portrait) research poster
summarizing the AntiFake2026 project, following the ISU ECpE poster
guidelines (sans-serif fonts only, no text shadows, 54pt title / >=40pt
headers / >=32pt body / >=24pt captions, one consistent bullet style,
consistent left alignment, logos/nameplate + acknowledgments/references
at the bottom, dark-background avoided).

Author name(s), lab/center name, email addresses, and the ISU/ECpE
nameplate image are all left as explicit bracketed placeholders -- this
script has no access to those (the paper itself still has
\\todo{Author names} unfilled) and does not fabricate them.

Run (inside antifake2026 env):
    conda run -n antifake2026 python build_poster.py
"""
import os

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

FONT = "Calibri"

NAVY = RGBColor(0x16, 0x1E, 0x33)
DARK_TEXT = RGBColor(0x20, 0x20, 0x20)
CARDINAL = RGBColor(0xC8, 0x10, 0x2E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF1, 0xF1, 0xF1)
MID_GRAY = RGBColor(0x9A, 0x9A, 0x9A)
GOAL_GREEN = RGBColor(0x1F, 0x7A, 0x3D)
GOAL_RED = RGBColor(0xB0, 0x22, 0x22)
GOAL_BLUE = RGBColor(0x1F, 0x4E, 0x8C)
GOAL_GREEN_FILL = RGBColor(0xE3, 0xF3, 0xE7)
GOAL_RED_FILL = RGBColor(0xFB, 0xE6, 0xE6)
GOAL_BLUE_FILL = RGBColor(0xE4, 0xEC, 0xF7)

TITLE_SZ = Pt(54)
HEADER_SZ = Pt(40)
BODY_SZ = Pt(32)
CAPTION_SZ = Pt(24)

prs = Presentation()
prs.slide_width = Inches(36)
prs.slide_height = Inches(48)
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout

PAGE_W = 36.0
PAGE_H = 48.0


def rect(x, y, w, h, fill=None, line=None, line_w=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.shadow.inherit = False
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = line_w or Pt(1)
    return shp


def _set_run(run, size, color, bold=False, italic=False, font=FONT):
    run.font.name = font
    run.font.size = size
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    # belt-and-suspenders: no shadow, explicit east-asian/cs font too
    rPr = run._r.get_or_add_rPr()
    rPr.set('dirty', '0')
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", font)


def textbox(x, y, w, h, text, size=BODY_SZ, color=DARK_TEXT, bold=False, italic=False,
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=FONT, line_spacing=1.08):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        r = p.add_run()
        r.text = line
        _set_run(r, size, color, bold=bold, italic=italic, font=font)
    return box


def bullets(x, y, w, h, items, size=BODY_SZ, color=DARK_TEXT, bullet_color=CARDINAL,
            line_spacing=1.05, space_after=Pt(10)):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = line_spacing
        p.space_after = space_after
        r1 = p.add_run()
        r1.text = "•  "
        _set_run(r1, size, bullet_color, bold=True)
        r2 = p.add_run()
        r2.text = item
        _set_run(r2, size, color)
    return box


def section_header(x, y, w, number, title):
    bar_h = 0.85
    label = f"{number}.  {title}" if number else title
    rect(x, y, w, bar_h, fill=CARDINAL)
    textbox(x + 0.15, y, w - 0.3, bar_h, label, size=HEADER_SZ,
            color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    return y + bar_h + 0.25


def simple_table(x, y, w, col_widths, rows, header=True, font_size=CAPTION_SZ,
                  row_heights=None, header_fill=NAVY, header_color=WHITE):
    n_rows = len(rows)
    n_cols = len(col_widths)
    total_h = sum(row_heights) if row_heights else 0.9 * n_rows
    gtable = slide.shapes.add_table(n_rows, n_cols, Inches(x), Inches(y), Inches(w),
                                     Inches(total_h)).table
    for c, cw in enumerate(col_widths):
        gtable.columns[c].width = Inches(cw)
    if row_heights:
        for r, rh in enumerate(row_heights):
            gtable.rows[r].height = Inches(rh)
    for r, row in enumerate(rows):
        for c, cell_text in enumerate(row):
            cell = gtable.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            is_header = header and r == 0
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if is_header else (WHITE if r % 2 == 1 else LIGHT_GRAY)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = cell_text
            _set_run(run, font_size, header_color if is_header else DARK_TEXT, bold=is_header)
    # thin gray borders
    return gtable


def flow_box(x, y, w, h, label, fill, text_color=WHITE, size=Pt(20)):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.shadow.inherit = False
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = WHITE
    shp.line.width = Pt(1.5)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.06)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    p.line_spacing = 0.95
    run = p.add_run()
    run.text = label
    _set_run(run, size, text_color, bold=True)
    return shp


def flow_arrow(x, y, w, h, fill=MID_GRAY):
    shp = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.shadow.inherit = False
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    return shp


# ===========================================================================
# HEADER: title, authors, affiliation, thin rule
# ===========================================================================
textbox(1.0, 0.6, 34.0, 1.5,
        "Security Analysis of Anti-Cloaking Schemes",
        size=TITLE_SZ, color=NAVY, bold=True, align=PP_ALIGN.CENTER, line_spacing=1.02)

textbox(1.0, 2.55, 34.0, 0.65, "Lucky Onyekwelu-Udoka  ·  Guan Yong", size=Pt(34), color=DARK_TEXT,
        bold=True, align=PP_ALIGN.CENTER)
textbox(1.0, 3.25, 34.0, 0.55, "Digital Forensics Research Group",
        size=Pt(28), color=DARK_TEXT, align=PP_ALIGN.CENTER)
textbox(1.0, 3.75, 34.0, 0.55,
        "Department of Electrical and Computer Engineering · Iowa State University",
        size=Pt(28), color=DARK_TEXT, align=PP_ALIGN.CENTER)
textbox(1.0, 4.25, 34.0, 0.55, "lucky@iastate.edu  ·  guan@iastate.edu",
        size=Pt(28), color=DARK_TEXT, align=PP_ALIGN.CENTER)

rect(1.0, 5.85, 34.0, 0.06, fill=CARDINAL)

COL_TOP = 6.25
LCOL_X, RCOL_X = 1.0, 18.4
COL_W = 16.6

# ===========================================================================
# LEFT COLUMN, SECTION 1: INTRODUCTION & MOTIVATION
# ===========================================================================
y = section_header(LCOL_X, COL_TOP, COL_W, 1, "Introduction & Motivation")
y2 = textbox(LCOL_X, y, COL_W, 3.0,
        "Zero-shot voice-cloning systems can reproduce a speaker's identity from "
        "only a few seconds of reference audio, lowering the barrier to voice "
        "fraud and non-consensual synthetic media. Proactive (“cloaking”) "
        "defenses perturb a recording before it is ever published, so that any "
        "later cloning attempt fails. We reproduce four representative cloaking "
        "defenses end to end, from official source code, on identical hardware "
        "and one shared evaluation protocol, and answer three questions kept "
        "carefully separate: does the cloak stay imperceptible, does it actually "
        "stop a downstream cloning attacker, and can an adaptive attacker undo it?",
        size=BODY_SZ, color=DARK_TEXT, line_spacing=1.08)
y = y + 3.05

# ===========================================================================
# LEFT COLUMN, SECTION 2: DATASET & CORPUS
# ===========================================================================
y = section_header(LCOL_X, y, COL_W, 2, "Dataset & Corpus")
textbox(LCOL_X, y, COL_W, 1.9,
        "4,867 recordings pooled from three independent public corpora. The "
        "FakeAVCeleb subset carries descent × gender metadata, balanced "
        "across 5 descent groups and 2 genders — enabling the first "
        "large-scale fairness audit of cloaking effectiveness.",
        size=BODY_SZ, color=DARK_TEXT, line_spacing=1.06)
y += 1.95
simple_table(LCOL_X, y, COL_W, [8.8, 3.9, 3.9],
             rows=[
                 ["Corpus", "Recordings", "Demographics"],
                 ["LibriSpeech", "500", "—"],
                 ["ASVspoof 2021", "500", "—"],
                 ["FakeAVCeleb", "3,867", "5 descent × 2 gender"],
                 ["Total", "4,867", "769 speakers"],
             ],
             font_size=CAPTION_SZ, row_heights=[0.7, 0.62, 0.62, 0.62, 0.62])
y += (0.7 + 0.62 * 4) + 0.35

# ===========================================================================
# LEFT COLUMN, SECTION 3: CLOAKING TECHNIQUES
# ===========================================================================
y = section_header(LCOL_X, y, COL_W, 3, "Four Cloaking Techniques Reproduced")
simple_table(LCOL_X, y, COL_W, [5.6, 4.2, 6.8],
             rows=[
                 ["Technique (source paper)", "Threat model", "Mechanism"],
                 ["Mitigating Unauthorized\nSpeech Synthesis [1]\n(“POP”)", "Training-time\n(unlearnable audio)",
                  "PGD perturbation minimizing a pretrained VITS surrogate's own "
                  "reconstruction loss; ε = 8/255."],
                 ["Defending Your Voice [2]\n(“attack-vc”)", "Inference-time\n(VC spoofing)",
                  "Decoy-target embedding attack against AdaIN-VC's own speaker "
                  "encoder."],
                 ["AntiFake [3]", "Inference-time\n(TTS/VC, ensemble)",
                  "Decoy-target attack optimized jointly against 3 surrogate "
                  "encoders (RTVC, AutoVC, YourTTS)."],
                 ["Protecting Your Voice from\nSpeech Synthesis Attacks [4]\n(“ProtectYourAudio”)", "Inference-time\n(VC spoofing)",
                  "Greedy discrete search over frequency-band masking, budgeted "
                  "against a perceptual-similarity constraint."],
             ],
             font_size=CAPTION_SZ, row_heights=[0.7, 2.0, 1.5, 1.7, 2.2])
y += (0.7 + 2.0 + 1.5 + 1.7 + 2.2) + 0.4

# ===========================================================================
# LEFT COLUMN, SECTION 3.5: KEY CONTRIBUTIONS
# ===========================================================================
y = section_header(LCOL_X, y, COL_W, 4, "Key Contributions")
bullets(LCOL_X, y, COL_W, 9.0, [
    "First reproduction of four cloaking defenses end to end, on identical "
    "hardware, against one shared 4,867-clip demographically balanced corpus.",
    "First large-scale descent × gender fairness audit of proactive-cloaking "
    "effectiveness — a question none of the four original papers examine.",
    "Rigorous separation of imperceptibility, protective efficacy, and "
    "restorability — three properties routinely conflated in the "
    "cloaking literature.",
    "A restoration study spanning 143 (technique × cloak × downstream "
    "system) combinations scored so far, with paired cluster-bootstrap "
    "significance testing whether an adaptive attacker can undo each cloak "
    "with generic signal processing (ProtectYourAudio's combinations are "
    "still incoming).",
    "A unified constrained-optimization framework explaining, predictively, "
    "why restoration succeeds for some techniques and not others.",
], size=BODY_SZ)

# ===========================================================================
# RIGHT COLUMN, SECTION 5: EVALUATION FRAMEWORK (3-goal diagram)
# ===========================================================================
y = section_header(RCOL_X, COL_TOP, COL_W, 5, "Evaluation Framework")
textbox(RCOL_X, y, COL_W, 1.15,
        "Speaker identity is judged by a verifier, not waveform equality. "
        "Three questions are asked of every cloak, kept strictly separate:",
        size=BODY_SZ, color=DARK_TEXT, line_spacing=1.05)
y += 1.25

goal_rows = [
    ("Goal 1: Imperceptibility", GOAL_GREEN, GOAL_GREEN_FILL,
     ["Original\naudio x", "Cloak\nC", "Cloaked\nC(x)", "Verifier"],
     "A good cloak should still sound like / verify as the real speaker: C(x) ≈ x."),
    ("Goal 2: Protective Efficacy", GOAL_RED, GOAL_RED_FILL,
     ["Cloaked\nC(x)", "Attacker\nclones (S)", "Clone\nS(C(x))", "Verifier"],
     "Security goal: the resulting clone should NOT match the real speaker: S(C(x)) ≠ x."),
    ("Goal 3: Restorability", GOAL_BLUE, GOAL_BLUE_FILL,
     ["Cloaked\nC(x)", "Restore\nR", "Attacker\nclones (S)", "Verifier"],
     "Adaptive-attacker goal: if restoration + cloning matches the real speaker again, "
     "restoration succeeded: S(R(C(x))) ≈ x."),
]

for title, accent, fill, nodes, caption in goal_rows:
    rect(RCOL_X, y, COL_W, 0.55, fill=fill, line=accent, line_w=Pt(1.5))
    textbox(RCOL_X + 0.15, y, COL_W - 0.3, 0.55, title, size=Pt(26), color=accent,
            bold=True, anchor=MSO_ANCHOR.MIDDLE)
    y += 0.65
    n = len(nodes)
    box_w = 3.1
    arrow_w = 0.55
    gap = 0.12
    total_w = n * box_w + (n - 1) * arrow_w + (n - 1) * gap * 2
    bx = RCOL_X + (COL_W - total_w) / 2
    by = y
    box_h = 1.35
    for i, node in enumerate(nodes):
        flow_box(bx, by, box_w, box_h, node, fill=accent, text_color=WHITE, size=Pt(18))
        bx += box_w + gap
        if i < n - 1:
            flow_arrow(bx, by + box_h / 2 - 0.18, arrow_w, 0.36, fill=accent)
            bx += arrow_w + gap
    y += box_h + 0.2
    textbox(RCOL_X, y, COL_W, 0.85, caption, size=CAPTION_SZ, color=DARK_TEXT,
            italic=True, align=PP_ALIGN.CENTER, line_spacing=1.0)
    y += 0.95

# ===========================================================================
# RIGHT COLUMN, SECTION 6: KEY RESULTS
# ===========================================================================
y = section_header(RCOL_X, y, COL_W, 6, "Key Results")
simple_table(RCOL_X, y, COL_W, [3.6, 2.9, 3.6, 3.1, 3.4],
             rows=[
                 ["Technique", "Imperceptibility\nEER", "Quality\nSTOI/PESQ/SI-SDR",
                  "Protective Efficacy\n(relative EER ↑)", "Restoration\n(full reversals)"],
                 ["POP", "≤ 0.16%", "0.971 / 2.92 / +16.3 dB",
                  "SV2TTS 2–11%\nSeed-VC 5–15%\nF5-TTS 14–51%", "0 / 48"],
                 ["attack-vc", "≤ 2.1%", "0.547 / 3.58 / −34.0 dB",
                  "SV2TTS 2–16%\nSeed-VC 2–6%\nF5-TTS 10–26%", "1 / 48\n(isolated)"],
                 ["ProtectYourAudio", "≤ 2.1%", "0.941 / 3.48 / −25.4 dB",
                  "SV2TTS 16–37%\nSeed-VC 15–100%\nF5-TTS 62–151%", "[in progress —\nresults incoming]"],
                 ["AntiFake", "22–66%\n(fails)", "0.703 / 1.46 / +1.9 dB",
                  "SV2TTS 144–438%\nSeed-VC 117–558%\nF5-TTS 229–2,202%", "12 / 47"],
             ],
             font_size=CAPTION_SZ,
             row_heights=[0.95, 1.35, 1.35, 1.55, 1.75])
y += (0.95 + 1.35 * 2 + 1.55 + 1.75) + 0.35

bullets(RCOL_X, y, COL_W, 4.2, [
    "POP, attack-vc, and ProtectYourAudio are all near-perfectly imperceptible "
    "(EER ≤ 2.1%); AntiFake's decoy-target attack is not budget-constrained "
    "and fails imperceptibility outright.",
    "POP and attack-vc protect only marginally against SV2TTS/Seed-VC "
    "(mostly ≤ 16% relative EER) and more clearly against F5-TTS. AntiFake "
    "protects strongly against all three systems, at the cost of being audible.",
    "ProtectYourAudio matches POP/attack-vc's imperceptibility while "
    "protecting measurably more broadly and consistently across all three "
    "systems — imperceptibility and cross-system protection are not as "
    "sharply opposed as POP/attack-vc alone would suggest.",
], size=BODY_SZ)
y += 4.3

# ===========================================================================
# RIGHT COLUMN, SECTION 7: RESTORATION STUDY & CONCLUSION
# ===========================================================================
y = section_header(RCOL_X, y, COL_W, 7, "Restoration Study & Conclusion")
bullets(RCOL_X, y, COL_W, 8.0, [
    "Ten generic, cloak-agnostic restoration techniques (filtering, "
    "resampling, quantization, spectral subtraction, simulated re-recording, "
    "ensemble averaging, …) applied before cloning, tested with paired "
    "cluster-bootstrap significance on matched clips — POP and attack-vc: "
    "48 (technique × downstream system) combinations each; AntiFake: 47. "
    "ProtectYourAudio: in progress, results incoming.",
    "POP: 0/48 combinations fully reversed; attack-vc: 1/48 (an isolated "
    "F5-TTS case) — most restoration attempts leave the attacker measurably "
    "worse off than doing nothing.",
    "AntiFake: 12/47 combinations show a full, statistically significant "
    "reversal (all three verifiers agree) and 22 more show a partial "
    "reversal — restoration is a real threat to AntiFake specifically, "
    "unlike POP/attack-vc.",
    "Demographic disparities in protection are largely inherited from the "
    "downstream cloning/verification pipeline itself, not introduced by the "
    "cloaks — except AntiFake, whose decoy attack couples imperceptibility "
    "failure directly to protection strength.",
    "Conclusion: a discrete, budget-constrained perturbation search "
    "(ProtectYourAudio) can generalize across downstream cloning systems "
    "better than a continuous perturbation of similar imperceptibility, and "
    "resists restoration far better than AntiFake's decoy attack — a "
    "distinction future cloak designs may be able to exploit deliberately.",
], size=BODY_SZ)

# ===========================================================================
# FOOTER: acknowledgments, references, nameplate, QR placeholder
# ===========================================================================
FOOTER_Y = 38.6
rect(1.0, FOOTER_Y - 0.3, 34.0, 0.05, fill=CARDINAL)

ack_y = section_header(1.0, FOOTER_Y, 16.6, "", "Acknowledgments")
textbox(1.0, ack_y, 16.6, 1.3,
        "[Funding source / sponsor name] · [Grant or award number]. "
        "Computed on shared, resource-constrained lab hardware.",
        size=Pt(28), color=DARK_TEXT, line_spacing=1.05)

ref_y = section_header(18.4, FOOTER_Y, 16.6, "", "References")
textbox(18.4, ref_y, 16.6, 2.3,
        "[1] Zhang et al., “Mitigating Unauthorized Speech Synthesis for Voice "
        "Protection,” ACM LAMPS, 2024.  "
        "[2] Yu et al., “AntiFake,” ACM CCS, 2023.  "
        "[3] Liu et al., “Protecting Your Voice from Speech Synthesis "
        "Attacks,” ACSAC, 2023.  "
        "[4] Huang et al., “Defending Your Voice,” IEEE SLT, 2021.",
        size=CAPTION_SZ, color=DARK_TEXT, line_spacing=1.15)

BOTTOM_Y = 44.4
plate = rect(1.0, BOTTOM_Y, 22.0, 2.2, fill=LIGHT_GRAY, line=MID_GRAY, line_w=Pt(1))
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isu_ecpe_logo.jpeg")
logo_sz = 2.0
slide.shapes.add_picture(LOGO_PATH, Inches(1.1), Inches(BOTTOM_Y + (2.2 - logo_sz) / 2),
                          Inches(logo_sz), Inches(logo_sz))
textbox(3.3, BOTTOM_Y, 19.5, 2.2,
        "Iowa State University\nDepartment of Electrical and Computer Engineering",
        size=Pt(28), color=DARK_TEXT, bold=True, align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.15)

qr = rect(23.4, BOTTOM_Y, 11.6, 2.2, fill=WHITE, line=MID_GRAY, line_w=Pt(1))
textbox(23.6, BOTTOM_Y, 11.2, 2.2,
        "[QR code → full paper PDF]",
        size=CAPTION_SZ, color=MID_GRAY, italic=True, align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE)

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AntiFake2026_Poster.pptx")
prs.save(out_path)
print(f"Saved {out_path}")

# ---------------------------------------------------------------------------
# Sanity check: make sure nothing was placed off the 36x48in canvas.
# ---------------------------------------------------------------------------
max_right = 0.0
max_bottom = 0.0
for shp in slide.shapes:
    right = (shp.left + shp.width) / 914400.0
    bottom = (shp.top + shp.height) / 914400.0
    max_right = max(max_right, right)
    max_bottom = max(max_bottom, bottom)
print(f"max_right={max_right:.2f}in (canvas {PAGE_W}in), max_bottom={max_bottom:.2f}in (canvas {PAGE_H}in)")
if max_right > PAGE_W or max_bottom > PAGE_H:
    print("WARNING: content overflows the canvas bounds!")
