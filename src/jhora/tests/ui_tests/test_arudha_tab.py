import unittest
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
import jhora.ui.horo_chart_tabs as horo_chart_tabs
from jhora.tests.ui_tests.test_helpers import ( BaseUITestCase, find_tab_index_by_widget, log, wait, check, wait_until,
                           table_has_any_nonempty_cell, click_button_and_accept_dialog)

class TestArudhaTab(BaseUITestCase):
    def test_arudha_tab_comprehensive(self):
        tab_name = "Arudha Tab: "
        log(f"=== {tab_name} Test Chart Combo and its methods ===")
        main_window = self.main_window

        # 1. Show Main Window and compute Horoscope Context
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)

        # 2. Extract layout variables safely
        chart_combo  = getattr(main_window, "_arudha_chart_combo", None)
        option_button = getattr(main_window, "_arudha_chart_option_button", None)
        info_label   = getattr(main_window, "_arudha_option_info_label", None)
        table1 = getattr(main_window, "_graha_arudha_table", None)
        table2 = getattr(main_window, "_bhava_arudha_table", None)
        arudha_combo = getattr(main_window,"_bhava_arudha_combo",None)

        check(chart_combo   is not None, f"{tab_name} chart combobox element exists")
        check(option_button is not None, f"{tab_name} options button element exists")
        check(info_label    is not None, f"{tab_name} option info label element exists")
        check(table1  is not None, f"{tab_name} table 1 element exists")
        check(table2  is not None, f"{tab_name} table 2 element exists")
        check(arudha_combo  is not None, f"{tab_name} Arudha Combo element exists")

        if chart_combo is None or option_button is None:
            log("[FAIL] Critical core variables missing context target matching.")
            return

        # 3. Dynamic Tab Index Resolution
        fallback_idx = getattr(horo_chart_tabs, "_graha_arudha_tab_start", 10)
        tab_index = find_tab_index_by_widget(main_window, chart_combo, default_index=fallback_idx)

        log(f"Switching to {tab_name} at index {tab_index}")
        main_window.tabWidget.setCurrentIndex(tab_index)
        wait(800)
        check(main_window.tabWidget.currentIndex() == tab_index, f"Switched to {tab_name} viewport")

        # 4. Verify initial table contents
        check(table_has_any_nonempty_cell(table1), f"{tab_name} table 1 has data initially")
        check(table_has_any_nonempty_cell(table2), f"{tab_name} table 2 has data initially")

        # 5. Loop through every item in the Amsa chart combobox
        total_charts = chart_combo.count()
        arudha_count = arudha_combo.count()
        log(f"Detected {total_charts} chart choices in {tab_name} combo dropdown. Starting matrix test...")

        for i in range(total_charts):
            chart_name = chart_combo.itemText(i)
            log(f"--- Testing {tab_name} Chart Index {i}: '{chart_name}' ---")

            chart_combo.setCurrentIndex(i)
            wait(500)
            option_button_check = not option_button.isEnabled() if i ==0 else option_button.isEnabled()
            check(option_button_check,
                  f"Options button correctly ENABLED for chart option '{chart_name}' (Index {i})")
            if i > 0: 
                # Click option button and accept the modal dialog
                click_button_and_accept_dialog(
                    option_button,
                    label=f"{tab_name} chart option '{chart_name}' (index {i})",
                )
            check(table_has_any_nonempty_cell(table1),
                  f"table 1 holds data for chart index {i}")
            for a in range(arudha_count):
                arudha_combo.setCurrentIndex(a)
                wait(500)
                arudha_name = arudha_combo.itemText(a)
                check(table_has_any_nonempty_cell(table2),
                      f"table 2 holds {arudha_name} data for {chart_name}")

        log(f"=== {tab_name} Test Completed Successfully ===")

if __name__ == "__main__":
    unittest.main()