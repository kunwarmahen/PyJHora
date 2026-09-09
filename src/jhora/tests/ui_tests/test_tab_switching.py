# src/jhora/ui_tests/test_tab_switching.py

import unittest
from PyQt6 import QtCore

from jhora.tests.ui_tests.test_helpers import (
    BaseUITestCase,
    log,
    check,
    wait,
    wait_until,
)


class TestTabSwitching(BaseUITestCase):
    """Tab Switching testing suite optimized for native Eclipse PyUnit runner execution."""

    def test_compute_then_switch_all_tabs(self):
        log("=== Step 2 Test 1: Compute and switch all tabs ===")
        main_window = self.main_window

        log("Showing main window")
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        check(main_window.isVisible(), "Main window is visible after show()")

        log("Calling compute_horoscope()")
        main_window.compute_horoscope()
        wait(1500)
        check(main_window.isVisible(), "Main window remains visible after compute_horoscope()")

        tab_widget = main_window.tabWidget
        check(tab_widget is not None, "tabWidget exists")
        check(tab_widget.count() > 0, f"tabWidget has tabs (count={tab_widget.count()})")

        for i in range(tab_widget.count()):
            title = tab_widget.tabText(i)
            log(f"Switching to tab index {i}, title={title!r}")
            tab_widget.setCurrentIndex(i)
            wait(700)

            check(main_window.isVisible(), f"Main window visible after switching to tab {i}")
            check(tab_widget.currentIndex() == i, f"Current tab index is {i}")
            check(tab_widget.currentWidget() is not None, f"Current widget exists for tab {i}")

    def test_tab_titles_exist_after_compute(self):
        """Companion smoke test: after compute, tab titles should not all be blank."""
        log("=== Step 2 Test 2: Tab titles exist after compute ===")
        main_window = self.main_window

        log("Showing main window")
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        check(main_window.isVisible(), "Main window is visible after show()")

        log("Calling compute_horoscope()")
        main_window.compute_horoscope()
        wait(1500)
        check(main_window.isVisible(), "Main window remains visible after compute_horoscope()")

        tab_widget = main_window.tabWidget
        check(tab_widget is not None, "tabWidget exists")
        check(tab_widget.count() > 0, f"tabWidget has tabs (count={tab_widget.count()})")

        non_blank_titles = 0
        for i in range(tab_widget.count()):
            title = tab_widget.tabText(i).strip()
            if title:
                non_blank_titles += 1

        log(f"Found {non_blank_titles} non-blank tab titles out of {tab_widget.count()} total tabs")
        check(non_blank_titles > 0, "At least one tab title is non-blank after compute")


if __name__ == "__main__":
    unittest.main()