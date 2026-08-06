# src/jhora/ui_tests/test_chakra_tab.py

from PyQt6 import QtCore
import jhora.ui.horo_chart_tabs as horo_chart_tabs
from jhora.tests.ui_tests.test_helpers import (
    BaseUITestCase,
    find_tab_index_by_widget,
    log,
    check,
    wait,
    wait_until,
    mouse_click,
    click_button_and_accept_dialog,
)

class TestChakraTab(BaseUITestCase):
    """Chakra Tab testing suite optimized for native Eclipse PyUnit runner execution."""

    def test_chakra_tab_comprehensive(self):
        log("=== Chakra Tab: Comprehensive Multi-Index & Option Group Matrix Test ===")
        main_window = self.main_window

        # 1. Show Main Window and compute Horoscope Context
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)

        # 2. Extract layout variables safely
        chart_combo   = getattr(main_window, "_chakra_chart_combo", None)
        option_button = getattr(main_window, "_chakra_chart_option_button", None)
        info_label    = getattr(main_window, "_chakra_option_info_label", None)
        options_group = getattr(main_window, "_chakra_options_group", None)

        check(chart_combo   is not None, "Chakra chart combobox element exists")
        check(option_button is not None, "Chakra options button element exists")
        check(info_label    is not None, "Chakra option info label element exists")

        # 3. Dynamic Tab Index Resolution
        fallback_idx = getattr(horo_chart_tabs, "_chakra_tab_start", 5)
        chakra_index = find_tab_index_by_widget(main_window, chart_combo, default_index=fallback_idx)

        log(f"Switching to Chakra tab at index {chakra_index}")
        main_window.tabWidget.setCurrentIndex(chakra_index)
        wait(800)
        check(main_window.tabWidget.currentIndex() == chakra_index, "Switched to Chakra tab viewport")

        # 4. Loop through every item in the Chakra chart combobox
        total_charts = chart_combo.count()
        log(f"Detected {total_charts} chart choices in Chakra combo dropdown. Starting matrix test...")

        for i in range(total_charts):
            chart_name = chart_combo.itemText(i)
            log(f"--- Testing Chakra Chart Index {i}: '{chart_name}' ---")

            chart_combo.setCurrentIndex(i)
            wait(300)

            # Index 0 (Rasi) disables the options dialog button
            if i == 0 or "rasi" in chart_name.lower():
                check(not option_button.isEnabled(),
                      f"Options button correctly DISABLED for Rasi base chart at index {i}")
                continue

            check(option_button.isEnabled(),
                  f"Options button correctly ENABLED for chart option '{chart_name}'")

            initial_label_text = info_label.text().strip()
            log(f"Initial layout label text: '{initial_label_text}'")

            # Click option button and accept the modal dialog
            click_button_and_accept_dialog(
                option_button,
                label=f"Chakra chart option '{chart_name}' (index {i})",
                wait_ms=800,
            )

            # 5. Navigate through every radio button in the QButtonGroup
            if options_group is not None:
                radio_buttons = options_group.buttons()
                log(f"Navigating {len(radio_buttons)} radio buttons in the chakra options sub-group...")
                for radio_idx, radio_button in enumerate(radio_buttons):
                    radio_text = radio_button.text()
                    log(f"Toggling radio item {radio_idx}: '{radio_text}'")
                    mouse_click(radio_button, QtCore.Qt.MouseButton.LeftButton)
                    wait(300)
                    check(radio_button.isChecked(),
                          f"Radio sub-option button '{radio_text}' successfully toggled and checked")
            else:
                log("[FAIL] _chakra_options_group not found on main_window context")
                check(False, "Chakra options group is missing")

        log("=== Chakra Tab Test Completed Successfully ===")


if __name__ == "__main__":
    import unittest
    unittest.main()
