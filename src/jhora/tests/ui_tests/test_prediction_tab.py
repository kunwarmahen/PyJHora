import unittest
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
import jhora.ui.horo_chart_tabs as horo_chart_tabs
from jhora.tests.ui_tests.test_helpers import ( BaseUITestCase, find_tab_index_by_widget, log, wait, check, wait_until,
                           table_has_any_nonempty_cell, click_button_and_accept_dialog)

class TestPredictionTab(BaseUITestCase):
    def test_prediction_tab_comprehensive(self):
        tab_name = "Prediction Tab: "
        log(f"=== {tab_name} Tests  ===")
        main_window = self.main_window

        # 1. Show Main Window and compute Horoscope Context
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)
        
        # 2. Extract App Variables
        prediction_list  = getattr(main_window, "_prediction_list", None)
        prediction_text  = getattr(main_window, "_prediction_text", None)
        
        # 3. Dynamic Tab Index Resolution
        fallback_idx = getattr(horo_chart_tabs, "_prediction_tab_start", 22)
        tab_index = find_tab_index_by_widget(main_window, prediction_list, default_index=fallback_idx)

        log(f"Switching to {tab_name} at index {tab_index}")
        main_window.tabWidget.setCurrentIndex(tab_index)
        wait(800)
        check(main_window.tabWidget.currentIndex() == tab_index, f"Switched to {tab_name} viewport")

        # 4. Scroll througth yoga list
        prediction_count = prediction_list.count()
        for p in range(prediction_count):
            prediction_list.setCurrentRow(p)
            prediction_names = prediction_list.currentItem().text().split("\n")
            check(prediction_names != '',f"{tab_name} contains {prediction_names} at index {p}")
            check(prediction_text != '', f"{tab_name} predictions contain description")
            wait(800)
        log(f"=== {tab_name} Test Completed Successfully ===")

if __name__ == "__main__":
    unittest.main()