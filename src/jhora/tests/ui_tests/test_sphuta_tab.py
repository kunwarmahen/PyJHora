# src/jhora/ui_tests/test_sphuta_tab.py

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

class TestSphutaTab(BaseUITestCase):
    """Sphuta/Varnada Tab testing suite optimized for native Eclipse PyUnit runner execution."""

    def test_sphuta_tab_comprehensive(self):
        log("=== Sphuta Tab: Comprehensive Multi-Index & Dual Option Dialog Test ===")
        main_window = self.main_window

        # 1. Initialize and compute horoscope context
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)

        # 2. Extract layout variables safely
        chart_combo  = getattr(main_window, "_sphuta_chart_combo", None)
        sphuta_btn   = getattr(main_window, "_sphuta_chart_option_button", None)
        sphuta_lbl   = getattr(main_window, "_sphuta_option_info_label", None)
        varnada_btn  = getattr(main_window, "_varnada_option_button", None)
        varnada_lbl  = getattr(main_window, "_varnada_option_info_label", None)
        sphuta_table = getattr(main_window, "_sphuta_table", None)

        check(chart_combo  is not None, "Sphuta chart combobox element exists")
        check(sphuta_btn   is not None, "Sphuta options button element exists")
        check(sphuta_lbl   is not None, "Sphuta option info label element exists")
        check(varnada_btn  is not None, "Varnada options button element exists")
        check(varnada_lbl  is not None, "Varnada option info label element exists")
        check(sphuta_table is not None, "Sphuta data table element exists")

        if chart_combo is None or sphuta_btn is None or varnada_btn is None:
            log("[FAIL] Critical core interactive widgets missing context target matching.")
            return

        # 3. Dynamic Tab Index Resolution
        fallback_idx = getattr(horo_chart_tabs, "_sphuta_tab_start", 7)
        sphuta_index = find_tab_index_by_widget(main_window, chart_combo, default_index=fallback_idx)

        log(f"Switching to Sphuta tab at index {sphuta_index}")
        main_window.tabWidget.setCurrentIndex(sphuta_index)
        wait(800)
        check(main_window.tabWidget.currentIndex() == sphuta_index, "Switched to Sphuta tab viewport")

        # 4. Verify initial table contents
        check(table_has_any_nonempty_cell(sphuta_table), "Sphuta table contains data initially")

        # 5. Loop through every item in the Sphuta chart combobox
        total_charts = chart_combo.count()
        log(f"Detected {total_charts} chart choices in Sphuta combo dropdown. Starting matrix test...")

        for i in range(total_charts):
            chart_name = chart_combo.itemText(i)
            log(f"--- Testing Sphuta Chart Index {i}: '{chart_name}' ---")

            chart_combo.setCurrentIndex(i)
            wait(500)

            # Baseline checks common across all indices
            check(varnada_btn.isEnabled(),
                  f"Varnada option button correctly ENABLED for index {i}")
            check(varnada_lbl.text().strip() != "",
                  f"Varnada info label populated for index {i}")
            check(table_has_any_nonempty_cell(sphuta_table),
                  f"Sphuta table holds data for index {i}")

            if i == 0:
                check(not sphuta_btn.isEnabled(),
                      f"Sphuta option button correctly DISABLED for index 0 ('{chart_name}')")
                check(sphuta_lbl.text().strip() == "",
                      "Sphuta chart info label empty for index 0")
            else:
                check(sphuta_btn.isEnabled(),
                      f"Sphuta option button correctly ENABLED for index {i} ('{chart_name}')")
                check(sphuta_lbl.text().strip() != "",
                      f"Sphuta chart info label populated for index {i}")

                # Dialog 1: Sphuta chart options
                click_button_and_accept_dialog(
                    sphuta_btn,
                    label=f"Sphuta chart option '{chart_name}' (index {i})",
                )

            # Dialog 2: Varnada options (always run for every index)
            click_button_and_accept_dialog(
                varnada_btn,
                label=f"Varnada option for chart '{chart_name}' (index {i})",
            )

            check(table_has_any_nonempty_cell(sphuta_table),
                  f"Sphuta table retains data after processing index {i}")

        log("=== Sphuta Tab Test Completed Successfully ===")


if __name__ == "__main__":
    import unittest
    unittest.main()
