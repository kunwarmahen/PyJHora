import unittest
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
import jhora.ui.horo_chart_tabs as horo_chart_tabs
from jhora.tests.ui_tests.test_helpers import ( BaseUITestCase, find_tab_index_by_widget, log, wait, check, wait_until,
                           table_has_any_nonempty_cell, click_button_and_accept_dialog)

class TestDoshaTab(BaseUITestCase):
    def test_dosha_tab_comprehensive(self):
        tab_name = "Dosha Tab: "
        log(f"=== {tab_name} Test Yoga List/text  ===")
        main_window = self.main_window

        # 1. Show Main Window and compute Horoscope Context
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)
        
        # 2. Extract App Variables
        dosha_list  = getattr(main_window, "_dosha_list", None)
        dosha_text  = getattr(main_window, "_dosha_text", None)
        
        # 3. Dynamic Tab Index Resolution
        fallback_idx = getattr(horo_chart_tabs, "_dosha_tab_start", 21)
        tab_index = find_tab_index_by_widget(main_window, dosha_list, default_index=fallback_idx)

        log(f"Switching to {tab_name} at index {tab_index}")
        main_window.tabWidget.setCurrentIndex(tab_index)
        wait(800)
        check(main_window.tabWidget.currentIndex() == tab_index, f"Switched to {tab_name} viewport")

        # 4. Scroll througth yoga list
        dosha_count = dosha_list.count()
        for y in range(dosha_count):
            dosha_list.setCurrentRow(y)
            dosha_names = dosha_list.currentItem().text().split("\n")
            check(dosha_names != '',f"{tab_name} contains {dosha_names} at index {y}")
            check(dosha_text != '', f"{tab_name} doshas contain description")
            wait(800)
        log(f"=== {tab_name} Test Completed Successfully ===")

if __name__ == "__main__":
    unittest.main()