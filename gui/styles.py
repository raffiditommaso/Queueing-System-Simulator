"""
Centralized Qt Style Sheets (QSS) and HTML/CSS styling definitions
for the Queueing System Simulator GUI.
"""

MAIN_STYLESHEET = """
    QMainWindow { background-color: #11111b; }
    QWidget { color: #cdd6f4; font-family: 'Segoe UI', Arial, sans-serif; }
    QGroupBox {
        border: 1px solid #313244;
        border-radius: 4px;
        margin-top: 8px;
        font-weight: bold;
        background-color: #1e1e2e;
        padding: 6px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 6px;
        color: #89b4fa;
    }
    QPushButton {
        background-color: #313244;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 4px 8px;
        font-weight: bold;
        color: #cdd6f4;
    }
    QPushButton:hover { background-color: #45475a; }
    QPushButton:pressed { background-color: #585b70; }
    QPushButton#btnRun {
        border: 2px solid #a6e3a1;
        background-color: #1e1e2e;
        color: #a6e3a1;
        font-weight: bold;
    }
    QPushButton#btnRun:hover {
        background-color: #a6e3a1;
        color: #11111b;
    }
    QPushButton#btnStop {
        border: 2px solid #f38ba8;
        background-color: #1e1e2e;
        color: #f38ba8;
        font-weight: bold;
    }
    QPushButton#btnStop:hover {
        background-color: #f38ba8;
        color: #11111b;
    }
    QPushButton#btnContinue {
        border: 2px solid #89b4fa;
        background-color: #1e1e2e;
        color: #89b4fa;
        font-weight: bold;
    }
    QPushButton#btnContinue:hover {
        background-color: #89b4fa;
        color: #11111b;
    }
    QPushButton#btnReset {
        border: 2px solid #cba6f7;
        background-color: #1e1e2e;
        color: #cba6f7;
        font-weight: bold;
    }
    QPushButton#btnReset:hover {
        background-color: #cba6f7;
        color: #11111b;
    }
    QComboBox, QSpinBox, QDoubleSpinBox {
        background-color: #181825;
        border: 1px solid #313244;
        border-radius: 4px;
        padding: 3px 6px;
        color: #cdd6f4;
    }
    /* Remove spinbox arrows completely */
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
        width: 0px;
        height: 0px;
        border: none;
    }
    QTabWidget::pane { border: 1px solid #313244; background-color: #181825; border-radius: 4px; }
    QTabBar::tab {
        background-color: #1e1e2e;
        color: #a6adc8;
        padding: 6px 14px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QTabBar::tab:selected { background-color: #313244; color: #cdd6f4; font-weight: bold; }
    QTableWidget { background-color: #181825; gridline-color: #313244; border: none; }
    QHeaderView::section { background-color: #1e1e2e; color: #89b4fa; font-weight: bold; border: 1px solid #313244; padding: 4px; }
"""

ZOOM_VIEW_STYLESHEET = """
    QGraphicsView {
        border: none;
        background-color: #11111b;
    }
    QScrollBar:vertical {
        background: #181825;
        width: 10px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #45475a;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover {
        background: #585b70;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar:horizontal {
        background: #181825;
        height: 10px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: #45475a;
        min-width: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #585b70;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
"""

QUESTION_BTN_STYLE = (
    "QPushButton { background-color: #313244; color: #89b4fa; font-size: 13px; font-weight: bold; "
    "border: 1px solid #45475a; border-radius: 4px; padding: 0px; } "
    "QPushButton:hover { background-color: #45475a; color: #ffffff; border-color: #89b4fa; } "
    "QPushButton:pressed { background-color: #585b70; }"
)

METRIC_QUESTION_BTN_STYLE = (
    "QPushButton { background-color: #313244; color: #89b4fa; font-size: 12px; font-weight: bold; "
    "border: 1px solid #45475a; border-radius: 4px; padding: 0px; } "
    "QPushButton:hover { background-color: #45475a; color: #ffffff; border-color: #89b4fa; } "
    "QPushButton:pressed { background-color: #585b70; }"
)

DIALOG_ZOOM_BTN_STYLE = (
    "QPushButton { background-color: #313244; color: #cdd6f4; font-size: 11px; font-weight: bold; "
    "border: 1px solid #45475a; border-radius: 4px; padding: 2px 8px; } "
    "QPushButton:hover { background-color: #45475a; color: #ffffff; } "
    "QPushButton:pressed { background-color: #585b70; }"
)

PLAYBACK_RUN_STYLE = (
    "QPushButton { border: 2px solid #a6e3a1; background-color: #1e1e2e; color: #a6e3a1; "
    "font-weight: bold; border-radius: 4px; } "
    "QPushButton:hover { background-color: #a6e3a1; color: #11111b; } "
    "QPushButton:pressed { background-color: #89d882; color: #11111b; }"
)

PLAYBACK_STOP_STYLE = (
    "QPushButton { border: 2px solid #f38ba8; background-color: #1e1e2e; color: #f38ba8; "
    "font-weight: bold; border-radius: 4px; } "
    "QPushButton:hover { background-color: #f38ba8; color: #11111b; } "
    "QPushButton:pressed { background-color: #eb7093; color: #11111b; }"
)

PLAYBACK_CONTINUE_STYLE = (
    "QPushButton { border: 2px solid #89b4fa; background-color: #1e1e2e; color: #89b4fa; "
    "font-weight: bold; border-radius: 4px; } "
    "QPushButton:hover { background-color: #89b4fa; color: #11111b; } "
    "QPushButton:pressed { background-color: #74a2f2; color: #11111b; }"
)

PLAYBACK_RESET_STYLE = (
    "QPushButton { border: 2px solid #cba6f7; background-color: #1e1e2e; color: #cba6f7; "
    "font-weight: bold; border-radius: 4px; } "
    "QPushButton:hover { background-color: #cba6f7; color: #11111b; } "
    "QPushButton:pressed { background-color: #b48bf0; color: #11111b; }"
)



def get_theory_html_css(zoom_factor: float = 1.0) -> str:
    """
    Generate authentic IEEEtran conference paper (10pt, Times New Roman, booktabs)
    styling matching LaTeX:
    \\documentclass[10pt,conference]{IEEEtran}
    \\usepackage{amsmath,amssymb,amsfonts,booktabs}
    """
    base_pt = round(10.0 * zoom_factor, 1)
    title_pt = round(16.0 * zoom_factor, 1)
    sec_pt = round(10.0 * zoom_factor, 1)
    sub_pt = round(9.0 * zoom_factor, 1)
    table_pt = round(9.0 * zoom_factor, 1)
    meta_pt = round(8.5 * zoom_factor, 1)

    return f"""
    <style>
        body {{
            font-family: 'Times New Roman', Times, 'Nimbus Roman No9 L', serif;
            font-size: {base_pt}pt;
            color: #000000;
            background-color: #ffffff;
            margin: 10px 16px;
            line-height: 1.48;
        }}
        h1 {{
            font-family: 'Times New Roman', Times, serif;
            font-size: {title_pt}pt;
            font-weight: bold;
            color: #000000;
            text-align: center;
            margin-top: 6px;
            margin-bottom: 8px;
            border: none;
            padding-bottom: 0px;
            letter-spacing: -0.2px;
        }}
        .meta-line {{
            font-family: 'Times New Roman', Times, serif;
            font-size: {meta_pt}pt;
            font-style: italic;
            color: #333333;
            text-align: center;
            margin-top: 4px;
            margin-bottom: 18px;
            border-bottom: 0.75pt solid #000000;
            padding-bottom: 6px;
        }}
        h2 {{
            font-family: 'Times New Roman', Times, serif;
            font-size: {sec_pt}pt;
            font-weight: bold;
            text-align: left;
            color: #000000;
            margin-top: 18px;
            margin-bottom: 8px;
            border-bottom: 0.5pt solid #bbbbbb;
            padding-bottom: 2px;
            page-break-after: avoid;
            break-after: avoid;
        }}
        h3 {{
            font-family: 'Times New Roman', Times, serif;
            font-size: {sec_pt}pt;
            font-weight: bold;
            font-style: italic;
            color: #000000;
            margin-top: 14px;
            margin-bottom: 6px;
            border: none;
            padding-bottom: 0px;
            page-break-after: avoid;
            break-after: avoid;
        }}
        p {{
            font-family: 'Times New Roman', Times, serif;
            font-size: {base_pt}pt;
            text-align: justify;
            margin-top: 0px;
            margin-bottom: 10px;
            line-height: 1.48;
        }}
        p.no-indent, .where-label {{
            text-indent: 0;
        }}
        .eq-table {{
            width: 100%;
            margin-top: 12px;
            margin-bottom: 12px;
            border-collapse: collapse;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .eq-num {{
            font-family: 'Times New Roman', Times, serif;
            font-size: {base_pt}pt;
            color: #000000;
            text-align: right;
            padding-right: 6px;
        }}
        .where-label {{
            margin-top: 6px;
            margin-bottom: 6px;
            font-style: italic;
            font-size: {sub_pt}pt;
        }}
        ul, ol {{
            margin-top: 6px;
            margin-bottom: 14px;
            padding-left: 22px;
        }}
        li {{
            font-family: 'Times New Roman', Times, serif;
            font-size: {base_pt}pt;
            margin-bottom: 6px;
            text-align: justify;
            line-height: 1.46;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        /* Formal LaTeX booktabs style: heavy top/bottom rules, midrule below headers */
        table.book-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
            margin-bottom: 22px;
            font-family: 'Times New Roman', Times, serif;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        table.book-table th {{
            border-top: 1.5pt solid #000000;
            border-bottom: 0.75pt solid #000000;
            background-color: transparent;
            color: #000000;
            font-weight: bold;
            text-align: left;
            padding: 5px 8px;
            font-size: {table_pt}pt;
        }}
        table.book-table td {{
            border: none;
            padding: 5px 8px;
            color: #000000;
            font-size: {table_pt}pt;
            background-color: transparent;
        }}
        table.book-table tr.bottom-rule td {{
            border-bottom: 1.5pt solid #000000;
        }}
        /* Academic Remark / Example environment (amsthm style, seamless paper white background) */
        .example-box {{
            background-color: #ffffff;
            border-left: 2pt solid #000000;
            padding: 6px 0px 6px 14px;
            margin-top: 16px;
            margin-bottom: 18px;
            font-size: {base_pt}pt;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .example-title {{
            font-weight: bold;
            font-style: italic;
            color: #000000;
            margin-top: 0px;
            margin-bottom: 8px;
            font-size: {base_pt}pt;
        }}
        .example-box ol, .example-box ul {{
            margin-top: 6px;
            margin-bottom: 6px;
            padding-left: 18px;
        }}
        .example-box li {{
            margin-bottom: 6px;
            line-height: 1.46;
        }}
    </style>
    """


# Default constant for backward compatibility in package imports
THEORY_HTML_CSS = get_theory_html_css(1.0)