import unittest
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
import jhora.ui.horo_chart_tabs as horo_chart_tabs
from jhora.tests.ui_tests.test_helpers import ( BaseUITestCase, find_tab_index_by_widget, log, wait, check, wait_until,
                           table_has_any_nonempty_cell, click_button_and_accept_dialog)

class TestYogaTab(BaseUITestCase):
    def test_yoga_tab_comprehensive(self):
        tab_name = "Yoga Tab: "
        log(f"=== {tab_name} Test Yoga List/text ===")
        main_window = self.main_window

        # 1. Show Main Window and compute Horoscope Context
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)
        
        # 2. Extract App Variables
        yoga_list  = getattr(main_window, "_yoga_list", None)
        yoga_text  = getattr(main_window, "_yoga_text", None)
        
        # 3. Dynamic Tab Index Resolution
        fallback_idx = getattr(horo_chart_tabs, "_yoga_tab_start", 20)
        tab_index = find_tab_index_by_widget(main_window, yoga_list, default_index=fallback_idx)

        log(f"Switching to {tab_name} at index {tab_index}")
        main_window.tabWidget.setCurrentIndex(tab_index)
        wait(800)
        check(main_window.tabWidget.currentIndex() == tab_index, f"Switched to {tab_name} viewport")

        # 4. Scroll througth yoga list
        yoga_count = yoga_list.count()
        for y in range(yoga_count):
            yoga_list.setCurrentRow(y)
            yoga_names = yoga_list.currentItem().text().split("\n")
            check(yoga_names != '',f"{tab_name} contains {yoga_names} at index {y}")
            check(yoga_text != '', f"{tab_name} yogas contain description")
            wait(800)
        log(f"=== {tab_name} Test Completed Successfully ===")

if __name__ == "__main__":
    unittest.main()