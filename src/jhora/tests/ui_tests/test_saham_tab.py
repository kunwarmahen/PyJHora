# src/jhora/ui_tests/test_saham_tab.py

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

class TestSahamTab(BaseUITestCase):
    """Saham Tab testing suite optimized for native Eclipse PyUnit runner execution."""

    def test_saham_tab_comprehensive(self):
        log("=== Saham Tab: Comprehensive Multi-Index & Chart Option Dialog Test ===")
        main_window = self.main_window

        # 1. Initialize and compute horoscope context
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)

        # 2. Extract layout variables safely
        chart_combo = getattr(main_window, "_saham_chart_combo", None)
        option_btn  = getattr(main_window, "_saham_chart_option_button", None)
        info_lbl    = getattr(main_window, "_saham_option_info_label", None)
        table1      = getattr(main_window, "_saham_table1", None)
        table2      = getattr(main_window, "_saham_table2", None)

        check(chart_combo is not None, "Saham chart combobox element exists")
        check(option_btn  is not None, "Saham options button element exists")
        check(info_lbl    is not None, "Saham option info label element exists")
        check(table1      is not None, "Saham data table 1 element exists")
        check(table2      is not None, "Saham data table 2 element exists")

        if chart_combo is None or option_btn is None:
            log("[FAIL] Critical core interactive widgets missing context target matching.")
            return

        # 3. Dynamic Tab Index Resolution
        fallback_idx = getattr(horo_chart_tabs, "_saham_tab_start", 8)
        saham_index = find_tab_index_by_widget(main_window, chart_combo, default_index=fallback_idx)

        log(f"Switching to Saham tab at index {saham_index}")
        main_window.tabWidget.setCurrentIndex(saham_index)
        wait(800)
        check(main_window.tabWidget.currentIndex() == saham_index, "Switched to Saham tab viewport")

        # 4. Verify initial table contents
        check(table_has_any_nonempty_cell(table1), "Saham table 1 contains data initially")
        check(table_has_any_nonempty_cell(table2), "Saham table 2 contains data initially")

        # 5. Loop through every item in the Saham chart combobox
        total_charts = chart_combo.count()
        log(f"Detected {total_charts} chart choices in Saham combo dropdown. Starting matrix test...")

        for i in range(total_charts):
            chart_name = chart_combo.itemText(i)
            log(f"--- Testing Saham Chart Index {i}: '{chart_name}' ---")

            chart_combo.setCurrentIndex(i)
            wait(500)

            check(table_has_any_nonempty_cell(table1),
                  f"Saham table 1 holds data for index {i}")
            check(table_has_any_nonempty_cell(table2),
                  f"Saham table 2 holds data for index {i}")

            if i == 0:
                check(not option_btn.isEnabled(),
                      f"Saham option button correctly DISABLED for index 0 ('{chart_name}')")
                check(info_lbl.text().strip() == "",
                      "Saham chart info label empty for index 0")
            else:
                check(option_btn.isEnabled(),
                      f"Saham option button correctly ENABLED for index {i} ('{chart_name}')")
                check(info_lbl.text().strip() != "",
                      f"Saham chart info label populated for index {i}")

                # Click option button and accept the modal dialog
                click_button_and_accept_dialog(
                    option_btn,
                    label=f"Saham chart option '{chart_name}' (index {i})",
                )

                check(table_has_any_nonempty_cell(table1),
                      f"Saham table 1 retains data after processing index {i}")
                check(table_has_any_nonempty_cell(table2),
                      f"Saham table 2 retains data after processing index {i}")

        log("=== Saham Tab Test Completed Successfully ===")


if __name__ == "__main__":
    import unittest
    unittest.main()
