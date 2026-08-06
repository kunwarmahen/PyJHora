# src/jhora/ui_tests/test_bhava_tab.py

from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import QComboBox
from jhora.tests.ui_tests.test_helpers import (
    BaseUITestCase,
    log,
    check,
    wait,
    wait_until,
    mouse_click,
    table_has_any_nonempty_cell,
    find_visible_dialog,
    reject_visible_dialog,
)

class TestBhavaTab(BaseUITestCase):
    """Bhava Tab testing suite optimized for native Eclipse PyUnit runner execution."""

    def test_bhava_tab_defaults_and_updates(self):
        log("=== Bhaava Test 1: Defaults and Updates ===")
        main_window = self.main_window

        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        check(main_window.isVisible(), "Main window is visible after show()")

        log("Calling compute_horoscope()")
        main_window.compute_horoscope()
        wait(1500)
        check(main_window.isVisible(), "Main window remains visible after compute")

        tab_widget = main_window.tabWidget
        log("Switching to Bhaava tab (index 1)")
        tab_widget.setCurrentIndex(1)
        wait(800)

        check(main_window.isVisible(), "Main window is visible on Bhaava tab")

        # Basic Bhaava widgets exist
        check(main_window._bhava_chart_combo is not None, "_bhava_chart_combo exists")
        check(main_window._bhava_method_combo is not None, "_bhava_method_combo exists")
        check(main_window._bhava_chart_option_button is not None, "_bhava_chart_option_button exists")
        check(main_window._bhava_option_info_label is not None, "_bhava_option_info_label exists")
        check(main_window._bhava_table is not None, "_bhava_table exists")

        # Default chart index
        check(main_window._bhava_chart_combo.currentIndex() == 0,
              "Default Bhaava chart combo index is 0")

        # Bhaava table has some content
        check(table_has_any_nonempty_cell(main_window._bhava_table),
              "Bhaava table/grid has non-empty content after compute")

        # Change bhava method combo one by one
        method_combo = main_window._bhava_method_combo
        for i in range(method_combo.count()):
            log(f"Changing _bhava_method_combo to index {i}")
            method_combo.setCurrentIndex(i)
            wait(500)

            check(main_window.isVisible(),
                  f"Main window visible after _bhava_method_combo index {i}")
            check(table_has_any_nonempty_cell(main_window._bhava_table),
                  f"Bhaava table/grid still has content after method index {i}")

        # Now move on to chart_combo
        chart_combo = main_window._bhava_chart_combo
        for i in range(chart_combo.count()):
            log(f"Changing _bhava_chart_combo to index {i}")
            chart_combo.setCurrentIndex(i)
            wait(800)

            check(main_window.isVisible(),
                  f"Main window visible after _bhava_chart_combo index {i}")
            check(table_has_any_nonempty_cell(main_window._bhava_table),
                  f"Bhaava table/grid still has content after chart index {i}")

            label_text = main_window._bhava_option_info_label.text().strip()

            if i == 0:
                check(not main_window._bhava_chart_option_button.isEnabled(),
                      "Bhaava chart option button disabled for default chart index 0")
                check(label_text == "" or not main_window._bhava_option_info_label.isVisible(),
                      "Bhaava option info label empty/hidden for default chart index 0")
            else:
                check(main_window._bhava_chart_option_button.isEnabled(),
                      f"Bhaava chart option button enabled for chart index {i}")
                check(label_text != "",
                      f"Bhaava option info label non-empty for chart index {i}")


    def test_bhava_chart_options_button_opens_dialog(self):
        log("=== Bhaava Test 2: Options Button Opens Dialog ===")
        main_window = self.main_window

        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        check(main_window.isVisible(), "Main window is visible after show()")

        log("Calling compute_horoscope()")
        main_window.compute_horoscope()
        wait(1500)
        check(main_window.isVisible(), "Main window remains visible after compute")

        tab_widget = main_window.tabWidget
        log("Switching to Bhaava tab (index 1)")
        tab_widget.setCurrentIndex(1)
        wait(800)

        chart_combo = main_window._bhava_chart_combo
        if chart_combo.count() <= 1:
            log("Bhaava chart combo has <= 1 item; skipping dialog-open test")
            return

        log("Selecting first non-default Bhaava chart (index 1)")
        chart_combo.setCurrentIndex(1)
        wait(800)

        button = main_window._bhava_chart_option_button
        check(button.isVisible(), "Bhaava chart option button is visible")
        check(button.isEnabled(), "Bhaava chart option button is enabled")

        dialog_seen = {"value": False}

        def handle_dialog():
            if find_visible_dialog() is not None:
                log("[INFO] Bhaava options dialog detected; rejecting/closing it")
                dialog_seen["value"] = True
                reject_visible_dialog()
            else:
                log("[INFO] No active modal dialog found by timer callback")

        QtCore.QTimer.singleShot(300, handle_dialog)

        log("Clicking Bhaava chart option button")
        mouse_click(button, QtCore.Qt.MouseButton.LeftButton)
        wait(1200)

        check(dialog_seen["value"], "Bhaava chart options dialog opened")
        check(main_window.isVisible(), "Main window still visible after dialog closes")


if __name__ == "__main__":
    import unittest
    unittest.main()