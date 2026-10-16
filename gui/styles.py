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
    base_pt = round(9.5 * zoom_factor, 1)
    title_pt = round(11.5 * zoom_factor, 1)
    sec_pt = round(10.0 * zoom_factor, 1)
    sub_pt = round(9.0 * zoom_factor, 1)
    table_pt = round(8.8 * zoom_factor, 1)
    meta_pt = round(8.0 * zoom_factor, 1)

    return f"""
    <style>
        body {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {base_pt}pt;
            color: #181818;
            background-color: #ffffff;
            margin: 10px 18px;
            line-height: 1.50;
        }}
        h1, .doc-title {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {title_pt}pt;
            font-weight: bold;
            color: #111111;
            text-align: center;
            margin-top: 2px;
            margin-bottom: 4px;
            line-height: 1.25;
            background-color: #ffffff;
        }}
        .meta-line {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {meta_pt}pt;
            font-style: italic;
            color: #444444;
            text-align: center;
            margin-top: 1px;
            margin-bottom: 10px;
            padding-bottom: 4px;
            line-height: 1.25;
            background-color: #ffffff;
        }}
        h2, .sec-title {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {sec_pt}pt;
            font-weight: bold;
            text-align: left;
            color: #111111;
            margin-top: 10px;
            margin-bottom: 4px;
            padding-bottom: 2px;
            page-break-after: avoid;
            break-after: avoid;
            background-color: #ffffff;
        }}
        h3, .subsec-title {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {sub_pt}pt;
            font-weight: bold;
            font-style: italic;
            color: #111111;
            margin-top: 8px;
            margin-bottom: 3px;
            page-break-after: avoid;
            break-after: avoid;
            background-color: #ffffff;
        }}
        p, .def-paragraph {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {base_pt}pt;
            text-align: left;
            margin-top: 0px;
            margin-bottom: 9px;
            line-height: 1.56;
        }}
        .eq-table {{
            width: 100%;
            margin-top: 8px;
            margin-bottom: 8px;
            border-collapse: collapse;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .eq-num {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {sub_pt}pt;
            color: #181818;
            text-align: right;
            padding-right: 6px;
            white-space: nowrap;
        }}
        .where-label {{
            font-family: 'Cambria', 'Georgia', serif;
            margin-top: 4px;
            margin-bottom: 3px;
            font-style: italic;
            font-size: {sub_pt}pt;
            page-break-after: avoid;
            break-after: avoid;
        }}
        ul, ol, .param-list {{
            margin-top: 4px;
            margin-bottom: 12px;
            padding-left: 22px;
        }}
        li {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {base_pt}pt;
            margin-bottom: 5px;
            text-align: left;
            line-height: 1.50;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        table.book-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            margin-bottom: 18px;
            font-family: 'Cambria', 'Georgia', serif;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        table.book-table th {{
            border-top: 1.5pt solid #111111;
            border-bottom: 0.75pt solid #111111;
            color: #111111;
            font-weight: bold;
            text-align: left;
            padding: 5px 8px;
            font-size: {table_pt}pt;
        }}
        table.book-table td {{
            border: none;
            padding: 4px 8px;
            color: #181818;
            font-size: {table_pt}pt;
        }}
        table.book-table tr.bottom-rule td {{
            border-bottom: 1.5pt solid #111111;
        }}
        .example-box {{
            background-color: #ffffff;
            border-left: 2pt solid #222222;
            padding: 6px 10px 6px 12px;
            margin-top: 12px;
            margin-bottom: 14px;
            font-size: {base_pt}pt;
            font-family: 'Cambria', 'Georgia', serif;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .example-title {{
            font-family: 'Cambria', 'Georgia', serif;
            font-weight: bold;
            font-style: italic;
            color: #111111;
            margin-top: 0px;
            margin-bottom: 6px;
            font-size: {base_pt}pt;
            background-color: #ffffff;
        }}
        div, span, b, strong, i, em {{
            font-family: 'Cambria', 'Georgia', serif;
        }}
    </style>
    """


# Default constant for backward compatibility in package imports
THEORY_HTML_CSS = get_theory_html_css(1.0)