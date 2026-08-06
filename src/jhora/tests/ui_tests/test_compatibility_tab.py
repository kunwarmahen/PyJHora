import unittest
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
import jhora.ui.horo_chart_tabs as horo_chart_tabs
from jhora.tests.ui_tests.test_helpers import ( BaseUITestCase, find_tab_index_by_widget, log, wait, check, wait_until,
                           table_has_any_nonempty_cell, click_button_and_accept_dialog)

class TestCompatibilityTab(BaseUITestCase):
    def test_compatibility_tab_comprehensive(self):
        tab_name = "Compatibility Tab: "
        log(f"=== {tab_name} Test Yoga List/text  ===")
        main_window = self.main_window

        # 1. Show Main Window and compute Horoscope Context
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)
        
        # 2. Extract App Variables
        comp_list  = getattr(main_window, "_matching_star_list", None)
        comp_tables = getattr(main_window,"_comp_results_table", None)
        _mahendra_porutham_checkbox = getattr(main_window,"_mahendra_porutham_checkbox", None)
        _vedha_porutham_checkbox = getattr(main_window,"_vedha_porutham_checkbox", None)
        _rajju_porutham_checkbox = getattr(main_window,"_rajju_porutham_checkbox", None)
        _sthree_dheerga_porutham_checkbox = getattr(main_window,"_sthree_dheerga_porutham_checkbox", None)
        comp_count_before = comp_list.count()
        # Check widget elements exist
        check(comp_list is not None, f"{tab_name} List exists")
        check(comp_tables[0] is not None, f"{tab_name} Table1 exists")
        check(comp_tables[1] is not None, f"{tab_name} Table2 exists")
        check(comp_tables[2] is not None, f"{tab_name} Table3 exists")
        check1 = _mahendra_porutham_checkbox.isChecked()
        log(f"{tab_name} _mahendra_porutham_checkbox Before is Checked? {check1}")
        check2 = not check1
        _mahendra_porutham_checkbox.setChecked(check2)
        check(_mahendra_porutham_checkbox.isChecked() == check2,
              f"{tab_name} _mahendra_porutham_checkbox After is Checked? {check2}")

        check1 = _vedha_porutham_checkbox.isChecked()
        log(f"{tab_name} _vedha_porutham_checkbox Before is Checked? {check1}")
        check2 = not check1
        _vedha_porutham_checkbox.setChecked(check2)
        check(_vedha_porutham_checkbox.isChecked() == check2,
              f"{tab_name} _vedha_porutham_checkbox After is Checked? {check2}")
        
        check1 = _rajju_porutham_checkbox.isChecked()
        log(f"{tab_name} _rajju_porutham_checkbox Before is Checked? {check1}")
        check2 = not check1
        _rajju_porutham_checkbox.setChecked(check2)
        check(_rajju_porutham_checkbox.isChecked() == check2,
              f"{tab_name} _rajju_porutham_checkbox After is Checked? {check2}")

        check1 = _sthree_dheerga_porutham_checkbox.isChecked()
        log(f"{tab_name} _sthree_dheerga_porutham_checkbox Before is Checked? {check1}")
        check2 = not check1
        _sthree_dheerga_porutham_checkbox.setChecked(check2)
        check(_sthree_dheerga_porutham_checkbox.isChecked() == check2,
              f"{tab_name} _sthree_dheerga_porutham_checkbox After is Checked? {check2}")
        
        # 3. Dynamic Tab Index Resolution
        fallback_idx = getattr(horo_chart_tabs, "_compatibility_tab_start", 23)
        tab_index = find_tab_index_by_widget(main_window, comp_tables[0], default_index=fallback_idx)

        log(f"Switching to {tab_name} at index {tab_index}")
        main_window.tabWidget.setCurrentIndex(tab_index)
        wait(800)
        check(main_window.tabWidget.currentIndex() == tab_index, f"Switched to {tab_name} viewport")

        # Compute again and check compatibility count
        main_window.compute_horoscope()
        wait(1500)
        comp_count_after = comp_list.count()
        check(comp_count_after != comp_count_before,
              f"{tab_name} New Count: {comp_count_after} differnt than Old Count: {comp_count_before}")
        
        # 4. Scroll througth yoga list
        comp_count = comp_list.count()
        for c in range(comp_count):
            comp_list.setCurrentRow(c)
            comp_names = comp_list.currentItem().text().split("\n")
            check(comp_names != '',f"{tab_name} contains {comp_names} at index {c}")
            for cn,c_name in enumerate(comp_names):
                c_names = c_name.split("-")
                h_name_exp = c_names[0]+"-Quarter- "+c_names[1]
                h_name_act = comp_tables[cn].horizontalHeaderItem(0).text()
                check(h_name_exp == h_name_act, f"{tab_name} {h_name_exp} == {h_name_act}")
            wait(800)
        log(f"=== {tab_name} Test Completed Successfully ===")

if __name__ == "__main__":
    unittest.main()