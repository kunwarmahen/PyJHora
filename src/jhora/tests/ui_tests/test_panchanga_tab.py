# src/jhora/ui_tests/test_panchanga_tab.py

from PyQt6 import QtCore
from jhora.tests.ui_tests.test_helpers import BaseUITestCase, log, check, wait, wait_until, mouse_click, key_clicks

def _enter_place_and_select_first_completer_item(main_window, place_text="Chennai"):
    """Type into the Place field and select the first item from the completer popup via QTest."""
    place_edit = main_window._place_text
    completer = place_edit.completer()
    popup = completer.popup()
    
    # Record previous values
    prev_lat = main_window._lat_text.text()
    prev_long = main_window._long_text.text()
    prev_tz = main_window._tz_text.text()
    
    log(f"Typing place text: {place_text}")
    place_edit.clear()
    place_edit.setFocus()
    key_clicks(place_edit, place_text)

    check(completer is not None, "QCompleter exists on place widget")

    wait_until(
        lambda: popup is not None and popup.model() is not None and popup.model().rowCount() > 0,
        timeout=5000
    )
    check(popup.model().rowCount() > 0, "Completer popup has at least one item")

    log("Selecting first item from place completer via popup click")
    first_index = popup.model().index(0, 0)
    popup.setCurrentIndex(first_index)
    popup.scrollTo(first_index)

    rect = popup.visualRect(first_index)
    check(rect.isValid(), "Completer popup visual rect for first item is valid")

    mouse_click(
        popup.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=rect.center()
    )
    wait(500)

    # Wait for fields update
    wait_until(
        lambda: (
            main_window._lat_text.text().strip() != prev_lat
            and main_window._long_text.text().strip() != prev_long
            and main_window._tz_text.text().strip() != prev_tz
        ),
        timeout=8000
    )

    check(main_window._lat_text.text().strip() != prev_lat, "Latitude: " + main_window._lat_text.text())
    check(main_window._long_text.text().strip() != prev_long, "Longitude: " + main_window._long_text.text())
    check(main_window._tz_text.text().strip() != prev_tz, "Timezone: " + main_window._tz_text.text())


class TestPanchangaTab(BaseUITestCase):
    """Panchanga Tab testing suite optimized for native Eclipse PyUnit runner execution."""

    def test_panchanga_place_and_compute(self):
        log("=== Panchanga Test: Place entry + compute ===")
        main_window = self.main_window

        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        check(main_window.isVisible(), "Main window is visible after show()")

        # Stay on Panchanga tab
        main_window.tabWidget.setCurrentIndex(0)
        wait(300)

        # 1. HERE WE PASS "Chennai" TO ENTER THE TEXT
        _enter_place_and_select_first_completer_item(main_window, "Chennai")

        # Enter DOB
        log("Entering date of birth")
        main_window._dob_text.clear()
        main_window._dob_text.setText("1996,12,7")
        check(main_window._dob_text.text().strip() == "1996,12,7", "DOB field updated")

        # Enter TOB
        log("Entering time of birth")
        main_window._tob_text.clear()
        main_window._tob_text.setText("10:34:00")
        check(main_window._tob_text.text().strip() == "10:34:00", "TOB field updated")

        # Click Show Chart
        log("Clicking Show Chart button")
        mouse_click(main_window._compute_button, QtCore.Qt.MouseButton.LeftButton)

        # Stay on Panchanga tab and wait for compute to finish
        main_window.tabWidget.setCurrentIndex(0)

        def _info1_ready():
            txt = main_window.panchanga_info_dialog._info_label1.toPlainText().strip()
            return txt != ""

        wait_until(_info1_ready, timeout=10000)

        info1 = main_window.panchanga_info_dialog._info_label1.toPlainText().strip()
        info2 = main_window.panchanga_info_dialog._info_label2.toPlainText().strip()
        info3 = main_window.panchanga_info_dialog._info_label3.toPlainText().strip()

        check(info1 != "", "_info_label1 populated after compute")
        check(info2 != "", "_info_label2 populated after compute")
        check(info3 != "", "_info_label3 populated after compute")

        first_line = info1.splitlines()[0].strip() if info1.splitlines() else info1
        
        # 2. ADDED: VISUAL LOG ASSURANCE FOR LAT/LONG VERIFICATION
        log(f"Visual assurance - First line of info_label1: {first_line}")
        
        # 3. HERE WE CHECK THAT IT MATCHES "Place: Chennai"
        check(
            first_line.startswith("Place: Chennai"),
            f"_info_label1 starts with 'Place: Chennai' (actual first line: {first_line!r})"
        )
        wait(1000)


if __name__ == "__main__":
    import unittest
    unittest.main()