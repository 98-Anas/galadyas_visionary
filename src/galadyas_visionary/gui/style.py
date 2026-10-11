"""The studio's look: one quiet dark style, an accent used sparingly."""

BG, PANEL, RAISED, BORDER = "#0e1015", "#141720", "#1b1f2a", "#262b38"
TEXT, MUTED, ACCENT = "#e6e9f0", "#8b93a7", "#7aa2f7"

QSS = f"""
* {{ font-family: "Inter"; font-size: 10pt; color: {TEXT}; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#heading {{ font-size: 11pt; font-weight: 600; }}
QLabel#muted, QLabel#hint {{ color: {MUTED}; }}
QLabel#hint {{ font-size: 9pt; }}
QLabel#section {{ color: {MUTED}; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px; }}
QToolBar {{ background: {BG}; border: none; padding: 6px 10px; spacing: 6px; }}
QToolBar QToolButton {{ padding: 6px 12px; border-radius: 6px; }}
QToolBar QToolButton:hover {{ background: {RAISED}; }}
QPushButton, QToolButton {{ background: {RAISED}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 12px; }}
QPushButton:hover, QToolButton:hover {{ border-color: #3a4256; }}
QPushButton:pressed, QToolButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: #555c6e; }}
QPushButton#primary {{ background: {ACCENT}; color: #0b0d12; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #8fb1fa; }}
QPushButton#primary:disabled {{ background: #3a4256; color: #8b93a7; }}
QToolButton#flat {{ background: transparent; border: none; padding: 4px 8px; }}
QToolButton#flat:hover {{ background: {RAISED}; }}
QLineEdit, QPlainTextEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 8px;
    selection-background-color: #34446b; }}
QLineEdit:focus, QPlainTextEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {RAISED}; border: 1px solid {BORDER}; selection-background-color: #2a3550; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 10px 10px; border-radius: 8px; margin: 2px 0; }}
QListWidget::item:hover {{ background: {RAISED}; }}
QListWidget::item:selected {{ background: #222a3d; color: {TEXT}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 8px 14px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom-color: {ACCENT}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
QProgressBar {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}
QStatusBar {{ background: {BG}; color: {MUTED}; }}
QMenu {{ background: {RAISED}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: #2a3550; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QSplitter::handle {{ background: transparent; }}
QToolTip {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; }}
"""
