# src/jhora/tests/ui_tests/test_amsa_tab.py

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
    table_has_any_nonempty_cell,
    click_button_and_accept_dialog,
)

class TestAmsaTab(BaseUITestCase):
    """Amsa Tab testing suite optimized for native Eclipse PyUnit runner execution."""

    def test_amsa_tab_comprehensive(self):
        tab_name = "Amsa Tab:"
        log(f"=== {tab_name} Comprehensive Multi-Index & Ruler Matrix Test ===")
        main_window = self.main_window

        # 1. Show Main Window and compute Horoscope Context
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)

        # 2. Extract layout variables safely
        chart_combo  = getattr(main_window, "_amsa_chart_combo", None)
        option_button = getattr(main_window, "_amsa_chart_option_button", None)
        info_label   = getattr(main_window, "_amsa_option_info_label", None)
        ruler_table1 = getattr(main_window, "_amsa_ruler_table1", None)
        ruler_table2 = getattr(main_window, "_amsa_ruler_table2", None)

        check(chart_combo   is not None, f"{tab_name} chart combobox element exists")
        check(option_button is not None, f"{tab_name} options button element exists")
        check(info_label    is not None, f"{tab_name} ption info label element exists")
        check(ruler_table1  is not None, f"{tab_name} ruler table 1 element exists")
        check(ruler_table2  is not None, f"{tab_name} ruler table 2 element exists")

        if chart_combo is None or option_button is None:
            log("[FAIL] Critical core variables missing context target matching.")
            return

        # 3. Dynamic Tab Index Resolution
        fallback_idx = getattr(horo_chart_tabs, "_amsa_ruler_tab_start", 6)
        amsa_index = find_tab_index_by_widget(main_window, chart_combo, default_index=fallback_idx)

        log(f"Switching to {tab_name} at index {amsa_index}")
        main_window.tabWidget.setCurrentIndex(amsa_index)
        wait(800)
        check(main_window.tabWidget.currentIndex() == amsa_index, f"Switched to {tab_name} viewport")

        # 4. Verify initial table contents
        check(table_has_any_nonempty_cell(ruler_table1), f"{tab_name} ruler table 1 has data initially")
        check(table_has_any_nonempty_cell(ruler_table2), f"{tab_name} ruler table 2 has data initially")

        # 5. Loop through every item in the Amsa chart combobox
        total_charts = chart_combo.count()
        log(f"Detected {total_charts} chart choices in {tab_name} combo dropdown. Starting matrix test...")

        for i in range(total_charts):
            chart_name = chart_combo.itemText(i)
            log(f"--- Testing {tab_name} Chart Index {i}: '{chart_name}' ---")

            chart_combo.setCurrentIndex(i)
            wait(500)

            option_button_check = option_button.isEnabled()
            check(option_button_check,
                  f"Options button correctly ENABLED for chart option '{chart_name}' (Index {i})")
            check(table_has_any_nonempty_cell(ruler_table1),
                  f"table 1 holds data for chart index {i}")
            check(table_has_any_nonempty_cell(ruler_table2),
                  f"table 2 holds data for chart index {i}")
            # Click option button and accept the modal dialog
            click_button_and_accept_dialog(
                option_button,
                label=f"{tab_name} chart option '{chart_name}' (index {i})",
            )

        log("=== Amsa Tab Test Completed Successfully ===")


if __name__ == "__main__":
    import unittest
    unittest.main()
