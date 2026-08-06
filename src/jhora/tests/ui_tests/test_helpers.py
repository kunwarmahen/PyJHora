# src/jhora/ui_tests/test_helpers.py

import sys
import time
import unittest
from pathlib import Path
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import QDialog, QMenu, QDialogButtonBox, QPushButton, QComboBox, QApplication
from PyQt6.QtTest import QTest

# --- Path Injection Setup ---
# Automatically resolve 'src' workspace location relative to this file
current_dir = Path(__file__).resolve().parent
while current_dir.name != "src" and current_dir.parent != current_dir:
    current_dir = current_dir.parent

if current_dir.name == "src" and str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

_STOP_ON_FAIL = False   # Stop execution if test failure noted

# --- Log Tracking Mechanics ---
_CHECK_STATS = {
    "checks_run": 0,
    "checks_passed": 0,
    "checks_failed": 0,
}

_LOG_FILE_PATH = Path("test_log.txt")


def _write_line(text):
    """Append one line to test_log.txt using UTF-8."""
    with _LOG_FILE_PATH.open("a", encoding="utf-8") as f:
        f.write(text + "\n")
        f.flush()


def log(msg):
    _write_line(f"[TESTLOG-{_CHECK_STATS['checks_run']+1}] {msg}")


def check(condition, description):
    _CHECK_STATS["checks_run"] += 1
    test_id = _CHECK_STATS["checks_run"]

    _write_line(f"[CHECK-{test_id}] {description}")

    if not condition:
        _CHECK_STATS["checks_failed"] += 1
        _write_line(f"[FAIL-{test_id}]  {description}")
        if _STOP_ON_FAIL: raise AssertionError(description)
    else:
        _CHECK_STATS["checks_passed"] += 1
        _write_line(f"[PASS-{test_id}]  {description}")


def get_check_stats():
    return dict(_CHECK_STATS)


def reset_check_stats():
    _CHECK_STATS["checks_run"] = 0
    _CHECK_STATS["checks_passed"] = 0
    _CHECK_STATS["checks_failed"] = 0
    _LOG_FILE_PATH.write_text("", encoding="utf-8")


# --- Native Automation Replacements for qtbot ---

def wait(ms):
    """Native replacement for qtbot.wait()."""
    QTest.qWait(ms)


def wait_until(condition_callable, timeout=5000):
    """Native event loop pump replacing qtbot.waitUntil()."""
    start_time = time.time() * 1000
    while not condition_callable():
        QTest.qWait(25)  # Processes events safely without freezing UI thread
        if (time.time() * 1000) - start_time > timeout:
            raise TimeoutError("Timed out waiting for target interface condition.")


def mouse_click(widget, button, pos=None):
    """Native wrapper for QTest mouse interactions."""
    if pos is None:
        QTest.mouseClick(widget, button)
    else:
        QTest.mouseClick(widget, button, QtCore.Qt.KeyboardModifier.NoModifier, pos)


def key_clicks(widget, text):
    """Native wrapper for QTest key stroke entry."""
    QTest.keyClicks(widget, text)


# --- Reusable UI Application Lifecycle Setup ---

class BaseUITestCase(unittest.TestCase):
    """
    Core test fixture class replacing conftest.py logic.
    Manages explicit allocation/deallocation of PyQt6 UI components.
    """
    @classmethod
    def setUpClass(cls):
        reset_check_stats()
        
        # Core runtime initialization configuration
        from jhora import config
        import jhora.ui.horo_chart_tabs as horo_chart_tabs
        config.initialize_runtime(force_reload=True, silent=False)
        horo_chart_tabs.config = config
        
        # Maintain exactly one active instance of QApplication across the run execution
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        from jhora.ui.horo_chart_tabs import ChartTabbed
        self.main_window = ChartTabbed()

    def tearDown(self):
        # Force local C++ interface widgets cleanup instantly to prevent Windows memory creep
        if hasattr(self, "main_window"):
            self.main_window.close()
            self.main_window.deleteLater()
        QApplication.instance().processEvents()

    @classmethod
    def tearDownClass(cls):
        # Outputs test execution stats summary at completion
        stats = get_check_stats()
        _write_line(
            f"[CHECK-SUMMARY] "
            f"checks_run={stats['checks_run']}, "
            f"checks_passed={stats['checks_passed']}, "
            f"checks_failed={stats['checks_failed']}"
        )


# --- Refactored GUI/Dialog Shared Helpers ---

def find_visible_dialog():
    app = QtWidgets.QApplication.instance()
    dialogs = [w for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]
    return dialogs[-1] if dialogs else None


def visible_dialogs():
    app = QtWidgets.QApplication.instance()
    return [w for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]


def visible_menus():
    app = QtWidgets.QApplication.instance()
    return [w for w in app.allWidgets() if isinstance(w, QMenu) and w.isVisible()]


def close_visible_menus():
    for m in visible_menus():
        try:
            m.close()
        except Exception:
            pass


def close_active_modal_dialog_if_any():
    dlg = QtWidgets.QApplication.activeModalWidget()
    if isinstance(dlg, QDialog):
        log("Active modal dialog detected; closing it with reject()")
        dlg.reject()


def accept_visible_dialog():
    dlg = find_visible_dialog()
    if dlg is None:
        return False

    button_boxes = dlg.findChildren(QDialogButtonBox)
    for box in button_boxes:
        for b_type in (QDialogButtonBox.StandardButton.Ok, QDialogButtonBox.StandardButton.Close, QDialogButtonBox.StandardButton.Cancel):
            btn = box.button(b_type)
            if btn is not None:
                btn.click()
                return True

    for btn in dlg.findChildren(QPushButton):
        txt = btn.text().replace("&", "").strip().lower()
        if txt in ("ok", "accept", "yes", "close", "cancel"):
            btn.click()
            return True

    if hasattr(dlg, "accept"):
        dlg.accept()
    else:
        dlg.close()
    return True


def reject_visible_dialog():
    dlg = find_visible_dialog()
    if dlg is None:
        return False

    button_boxes = dlg.findChildren(QDialogButtonBox)
    for box in button_boxes:
        for b_type in (QDialogButtonBox.StandardButton.Close, QDialogButtonBox.StandardButton.Cancel, QDialogButtonBox.StandardButton.Ok):
            btn = box.button(b_type)
            if btn is not None:
                btn.click()
                return True

    for btn in dlg.findChildren(QPushButton):
        txt = btn.text().replace("&", "").strip().lower()
        if txt in ("close", "cancel", "ok", "accept", "yes"):
            btn.click()
            return True

    if hasattr(dlg, "reject"):
        dlg.reject()
    else:
        dlg.close()
    return True


def table_has_any_nonempty_cell(widget):
    if hasattr(widget, "rowCount") and hasattr(widget, "columnCount") and hasattr(widget, "item"):
        for r in range(widget.rowCount()):
            for c in range(widget.columnCount()):
                item = widget.item(r, c)
                if item is not None and item.text().strip():
                    return True
        return False

    if hasattr(widget, "labels"):
        for row in widget.labels:
            for label in row:
                if label is not None and label.text().strip():
                    return True
        return False

    raise AssertionError(f"Unsupported grid-like widget type: {type(widget).__name__}")


def handle_options_dialog(result):
    dlg = find_visible_dialog()
    if dlg is None:
        log("No visible options dialog found")
        return

    result["dialog_seen"] = True
    log("Options dialog detected")

    combos = [c for c in dlg.findChildren(QComboBox) if c.isEnabled() and c.count() > 1]
    if combos:
        combo = combos[0]
        old_index = combo.currentIndex()
        new_index = 1 if old_index == 0 and combo.count() > 1 else 0
        if new_index != old_index:
            log(f"Changing first dialog combo from {old_index} to {new_index}")
            combo.setCurrentIndex(new_index)
            result["combo_changed"] = True
            wait(300)

    log("Accepting options dialog")
    accept_visible_dialog()
    result["dialog_closed"] = True


def find_tab_index_by_widget(main_window, target_widget, default_index):
    tab_widget = getattr(main_window, "tabWidget", None)
    if tab_widget is None or target_widget is None:
        return default_index

    for i in range(tab_widget.count()):
        page = tab_widget.widget(i)
        if page is None:
            continue
        if page is target_widget or page.isAncestorOf(target_widget):
            return i

    return default_index


# ---------------------------------------------------------------------------
# Shared modal dialog interceptor
# ---------------------------------------------------------------------------

def intercept_and_accept_modal(dialog_state: dict):
    """
    Generic modal dialog interceptor used across all tab tests.

    Finds the active modal (or any visible top-level QDialog as fallback),
    marks it as seen, accepts it, and marks it as closed.

    Args:
        dialog_state: dict with keys 'seen' and 'closed' (both bool).
                      Updated in-place by this function.
    """
    dlg = QtWidgets.QApplication.activeModalWidget()
    if dlg is None:
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                dlg = widget
                break
    if dlg is None:
        return

    dialog_state["seen"] = True
    log(f"[DIALOG] Intercepted modal: {type(dlg).__name__}. Accepting.")

    # Prefer explicit _accept_button if the dialog exposes one
    if hasattr(dlg, "_accept_button") and dlg._accept_button is not None:
        dlg._accept_button.click()
    elif hasattr(dlg, "accept"):
        dlg.accept()
    else:
        dlg.close()

    dialog_state["closed"] = True


# ---------------------------------------------------------------------------
# Shared button-click + dialog-accept sequence
# ---------------------------------------------------------------------------

def click_button_and_accept_dialog(
    button,
    label: str,
    delay_ms: int = 350,
    wait_ms: int = 1200,
) -> dict:
    """
    Click a button, intercept the modal dialog it opens, accept it,
    and assert both 'seen' and 'closed'.

    Args:
        button:    The QPushButton (or any clickable widget) to click.
        label:     Human-readable description used in check() messages.
        delay_ms:  How long (ms) to wait before the interceptor fires.
        wait_ms:   How long (ms) to wait after the click for the dialog
                   to appear and be dismissed.

    Returns:
        dialog_state dict with keys 'seen' and 'closed'.
    """
    dialog_state = {"seen": False, "closed": False}
    QtCore.QTimer.singleShot(
        delay_ms,
        lambda: intercept_and_accept_modal(dialog_state),
    )
    mouse_click(button, QtCore.Qt.MouseButton.LeftButton)
    wait(wait_ms)
    check(dialog_state["seen"],   f"Modal dialog appeared for: {label}")
    check(dialog_state["closed"], f"Modal dialog closed for:   {label}")
    return dialog_state

def arm_dialog_hunter(handler_func, delay_ms=300):
    """
    Arms an asynchronous hunter that will execute handler_func 
    after delay_ms without blocking the main thread.
    """
    QtCore.QTimer.singleShot(delay_ms, handler_func)
    
# ---------------------------------------------------------------------------
# Shared context-menu event poster
# ---------------------------------------------------------------------------

def post_context_menu_event(widget):
    """
    Post a right-click context menu event to *widget* at its centre.

    Uses postEvent (async) so the caller must process events or wait
    after calling this function.

    Args:
        widget: Any QWidget that handles QContextMenuEvent.
    """
    from PyQt6 import QtGui
    widget.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    widget.activateWindow()
    widget.raise_()
    QtWidgets.QApplication.processEvents()

    pos = widget.rect().center()
    event = QtGui.QContextMenuEvent(
        QtGui.QContextMenuEvent.Reason.Mouse,
        pos,
        widget.mapToGlobal(pos),
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    QtWidgets.QApplication.postEvent(widget, event)
    QtWidgets.QApplication.processEvents()