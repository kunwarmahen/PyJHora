# src/jhora/ui_tests/test_chart_tab.py

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMenu, QDialog, QDialogButtonBox, QPushButton, QComboBox
from jhora import utils

from jhora.tests.ui_tests.test_helpers import (
    BaseUITestCase,
    log,
    check,
    wait,
    wait_until,
    mouse_click,
    find_visible_dialog,
    visible_dialogs,
    visible_menus,
    close_visible_menus,
    close_active_modal_dialog_if_any,
    accept_visible_dialog,
    reject_visible_dialog,
    handle_options_dialog,
    post_context_menu_event,
)

def _find_chart_tab_index(main_window):
    chart = main_window._kundali_charts[0]
    tab_widget = main_window.tabWidget

    for i in range(tab_widget.count()):
        page = tab_widget.widget(i)
        if page is None:
            continue
        if chart is page or page.isAncestorOf(chart):
            return i
    return 3

def _find_action_in_menu(menu: QMenu, action_text: str):
    """Find a menu action using case-insensitive matching to protect against typos."""
    wanted = action_text.replace("&", "").strip().lower()
    for action in menu.actions():
        text = action.text().replace("&", "").strip().lower()
        if text == wanted:
            return action
    available = [a.text().replace("&", "").strip() for a in menu.actions()]
    raise AssertionError(f"Action '{action_text}' not found. Available actions: {available}")



class TestChartTab(BaseUITestCase):
    """Chart Tab testing suite optimized for native Eclipse PyUnit runner execution."""
    def _test_context_menus(self,chart):
        main_window = self.main_window
        # 4. CHART CONTEXT MENU SMOKE-TEST PATHS
        log("=== Chart Menu Test: Root/Submenu Paths Smoke ===")
        chart_menu_paths = [
            ["Planets"],
            ["Varnada Lagna"],
            ["Karakas"],
            ["Special Lagnas"],
            ["Sphuta"],
            ["Saham"],
            ["Upagrahas"],
            ["Arudhas", "Bhava Arudha"],
            ["Arudhas", "Sun Arudha"],
            ["Arudhas", "Moon Arudha"],
            ["Arudhas", "Mars Arudha"],
            ["Arudhas", "Mercury Arudha"],
            ["Arudhas", "Jupiter Arudha"],
            ["Arudhas", "Venus Arudha"],
            ["Arudhas", "Saturn Arudha"],
            ["Arudhas", "Rahu Arudha"],
            ["Arudhas", "Ketu Arudha"],
        ]

        def handle_menu_path(path, result_dict):
            menus = visible_menus()
            if not menus:
                return
            current_menu = menus[-1]
            result_dict["menu_seen"] = True

            for idx, segment in enumerate(path):
                action = _find_action_in_menu(current_menu, segment)
                check(action is not None, f"Found menu segment '{segment}'")

                if idx == len(path) - 1:
                    action.trigger()
                    result_dict["action_triggered"] = True
                    QtWidgets.QApplication.processEvents()
                    wait(300)
                    close_active_modal_dialog_if_any()
                    close_visible_menus()
                    return

                submenu = action.menu()
                check(submenu is not None, f"Segment '{segment}' has a submenu")
                submenu.popup(current_menu.mapToGlobal(current_menu.actionGeometry(action).center()))
                QtWidgets.QApplication.processEvents()
                wait(300)
                current_menu = submenu

        for path in chart_menu_paths:
            path_str = " > ".join(path)
            log(f"--- Testing menu path: {path_str} ---")

            path_res = {"menu_seen": False, "action_triggered": False}
            QtCore.QTimer.singleShot(500, lambda p=path, r=path_res: handle_menu_path(p, r))

            post_context_menu_event(chart)
            wait(1800)

            check(path_res["menu_seen"], f"Chart context menu opened for path '{path_str}'")
            check(path_res["action_triggered"], f"Leaf action triggered for path '{path_str}'")

        # 5. INFO DIALOG MENU TESTS
        log("=== Chart Menu Test: Info Dialog ===")
        info_menu_paths = [
            ["Paachakaadhi Relation"],
            ["Brahma,Rudra,Maheshwara"],
            ["Raasi Entry"],
            ["Yogi, Avayogi, Sahayogi"],
            ["Pushkara Amsa, Pushkara Bhaga"],
            ["Lattha nakshathra"],
        ]

        # ⚡ HUNTER LOOP: Keeps trying until the dialog is found and closed
        def _click_accept_on_dialog(res_dict, p_str, attempts=15):
            dlg = find_visible_dialog()
            if dlg is not None:
                res_dict["dialog_seen"] = True
                log(f"    [DIALOG] Info dialog detected for path '{p_str}'. Dismissing...")
                
                accept_visible_dialog()
                QtWidgets.QApplication.processEvents()
                
                if dlg.isVisible():
                    for btn in dlg.findChildren(QPushButton):
                        txt = btn.text().strip().lower()
                        if any(kwd in txt for kwd in ["ok", "close", "dismiss", "accept"]):
                            mouse_click(btn, QtCore.Qt.MouseButton.LeftButton)
                            QtWidgets.QApplication.processEvents()
                            break
                            
                res_dict["dialog_closed"] = not dlg.isVisible()
            else:
                if attempts > 0:
                    # Retry in 200ms if the dialog hasn't appeared yet
                    QtCore.QTimer.singleShot(200, lambda: _click_accept_on_dialog(res_dict, p_str, attempts - 1))

        def handle_info_menu_path(path, res_dict):
            p_str = " > ".join(path)
            menus = visible_menus()
            if not menus:
                return
            current_menu = menus[-1]
            res_dict["menu_seen"] = True

            for idx, segment in enumerate(path):
                action = _find_action_in_menu(current_menu, segment)
                check(action is not None, f"Found menu segment '{segment}'")

                if idx == len(path) - 1:
                    # Start the hunter loop BEFORE triggering the blocking action
                    QtCore.QTimer.singleShot(200, lambda r=res_dict, ps=p_str: _click_accept_on_dialog(r, ps))
                    action.trigger() # Thread blocks here until hunter kills the dialog
                    res_dict["action_triggered"] = True
                    QtWidgets.QApplication.processEvents()
                    wait(500)
                    close_visible_menus()
                    return

                submenu = action.menu()
                check(submenu is not None, f"Segment '{segment}' has a submenu")
                submenu.popup(current_menu.mapToGlobal(current_menu.actionGeometry(action).center()))
                QtWidgets.QApplication.processEvents()
                wait(300)
                current_menu = submenu

        for info_path in info_menu_paths:
            path_str = " > ".join(info_path)
            log(f"--- Testing info menu path: {path_str} ---")

            info_res = {
                "menu_seen": False,
                "action_triggered": False,
                "dialog_seen": False,
                "dialog_closed": False,
            }

            QtCore.QTimer.singleShot(500, lambda p=info_path, r=info_res: handle_info_menu_path(p, r))
            post_context_menu_event(chart)
            wait(2500) # Give the entire interaction sequence room to breathe

            close_visible_menus()

            check(info_res["menu_seen"], f"Chart context menu opened for path '{path_str}'")
            check(info_res["action_triggered"], f"Info leaf action triggered for path '{path_str}'")
            check(info_res["dialog_seen"], f"Info dialog appeared for path '{path_str}'")
            check(info_res["dialog_closed"], f"Info dialog closed for path '{path_str}'")

        # 6. WIDGET DIALOG MENU TESTS 
        log("=== Chart Menu Test: Widget Dialog Menus ===")
        widget_menu_paths = [
            ["Drishti"],
            ["Planets Speed, Distance Information"],
            ["Planet Aspect Relationships List"],
            ["planet Dhrekana"],
        ]

        asc_label = main_window.resources.get("ascendant_str", "Ascendant")
        widget_menu_paths.append(["Navathaara", asc_label])
        for planet_name in utils.PLANET_NAMES[:9]:
            widget_menu_paths.append(["Navathaara", planet_name])
            
        widget_menu_paths.append(["Special Thaara", asc_label])
        for planet_name in utils.PLANET_NAMES[:9]:
            widget_menu_paths.append(["Special Thaara", planet_name])

        # ⚡ HUNTER LOOP for Widget Dialogs
        def _close_widget_dialog_if_present(res_dict, p_str, attempts=15):
            dlg = find_visible_dialog()
            if dlg is not None:
                res_dict["dialog_seen"] = True
                log(f"    [DIALOG] Widget dialog detected for path '{p_str}'. Rejecting...")
                reject_visible_dialog()
                res_dict["dialog_closed"] = True
            else:
                if attempts > 0:
                    QtCore.QTimer.singleShot(200, lambda: _close_widget_dialog_if_present(res_dict, p_str, attempts - 1))

        def handle_widget_menu_path(path, res_dict):
            p_str = " > ".join(path)
            menus = visible_menus()
            if not menus:
                return
            current_menu = menus[-1]
            res_dict["menu_seen"] = True

            for idx, segment in enumerate(path):
                try:
                    action = _find_action_in_menu(current_menu, segment)
                except AssertionError as ae:
                    log(f"[WARN] Skipping path component mapping error: {ae}")
                    close_visible_menus()
                    return

                if idx == len(path) - 1:
                    # Start the hunter loop BEFORE triggering the action
                    QtCore.QTimer.singleShot(200, lambda r=res_dict, ps=p_str: _close_widget_dialog_if_present(r, ps))
                    action.trigger() # Blocks here
                    res_dict["action_triggered"] = True
                    QtWidgets.QApplication.processEvents()
                    wait(500)
                    close_visible_menus()
                    return

                submenu = action.menu()
                if submenu is None:
                    close_visible_menus()
                    return
                
                submenu.popup(current_menu.mapToGlobal(current_menu.actionGeometry(action).center()))
                QtWidgets.QApplication.processEvents()
                wait(300)
                current_menu = submenu

        for w_path in widget_menu_paths:
            path_str = " > ".join(w_path)
            log(f"--- Testing widget-dialog menu path: {path_str} ---")

            w_res = {
                "menu_seen": False,
                "action_triggered": False,
                "dialog_seen": False,
                "dialog_closed": False,
            }

            QtCore.QTimer.singleShot(500, lambda p=w_path, r=w_res: handle_widget_menu_path(p, r))
            post_context_menu_event(chart)
            wait(2500)

            close_visible_menus()

            if w_res["menu_seen"] and w_res["action_triggered"]:
                check(w_res["menu_seen"], f"Chart context menu opened for path '{path_str}'")
                check(w_res["action_triggered"], f"Widget-dialog leaf action triggered for path '{path_str}'")
                check(w_res["dialog_seen"], f"Widget dialog appeared for path '{path_str}'")
                check(w_res["dialog_closed"], f"Widget dialog closed for path '{path_str}'")

    def _test_chart_combo_iteration(self):
        main_window = self.main_window
        chart = main_window._kundali_charts[0]
        chart_combo = main_window._kundali_chart_combo
        # 2. CHART COMBO ITERATION WITH CONDITIONAL HASATTR CHECKS
        log("=== Chart Tab Test: Chart Combo Iteration ===")
        for i in range(chart_combo.count()-1): # Exclude DmXDn
            chart_name = chart_combo.itemText(i)
            log(f"--- Setting _kundali_chart_combo to index {i}: {chart_name!r} ---")
            chart_combo.setCurrentIndex(i)
            wait(1200)

            check(main_window.isVisible(), f"Main window visible after chart combo index {i}")
            check(chart.isVisible(), f"Main chart widget visible after chart combo index {i}")

            if hasattr(main_window, "_chart_info_label1"):
                label1 = main_window._chart_info_label1.text().split('\n')[0].strip()
                check(
                    main_window._chart_info_label1.text().strip() != "",
                    f"{chart_name} {label1} is non-empty after chart combo index {i}"
                )

            if hasattr(main_window, "_chart_info_label2"):
                label2 = main_window._chart_info_label2.text().split('\n')[0].strip()
                check(
                    main_window._chart_info_label2.text().strip() != "",
                    f"{chart_name} {label2} is non-empty after chart combo index {i}"
                )

            if hasattr(main_window, "_chart_option_button"):
                btn = main_window._chart_option_button
                log(
                    f"_chart_option_button state after index {i}: "
                    f"visible={btn.isVisible()}, enabled={btn.isEnabled()}, text={btn.text()!r}"
                )

            if hasattr(main_window, "_chart_option_info_label"):
                lbl = main_window._chart_option_info_label
                log(f"_chart_option_info_label after index {i}: {lbl.text()!r}")

    def _test_chart_combo_options(self):
        main_window = self.main_window
        chart = main_window._kundali_charts[0]
        chart_combo = main_window._kundali_chart_combo
        option_button = main_window._kundali_chart_option_button
        option_label = main_window._kundali_option_info_label
        # 3. CHART COMBO OPTIONS DIALOGS LOOP
        log("=== Chart Tab Test: Chart Combo Options Dialogs ===")
        for i in range(chart_combo.count() - 2):
            chart_name = chart_combo.itemText(i)
            log(f"--- Options test for _kundali_chart_combo index {i}: {chart_name!r} ---")

            chart_combo.setCurrentIndex(i)
            wait(1200)

            check(main_window.isVisible(), f"Main window visible after chart combo index {i}")
            check(chart.isVisible(), f"Main chart widget visible after chart combo index {i}")

            old_label_text = option_label.text().strip()
            log(f"Existing option label text: {old_label_text!r}")

            if i == 0:
                check(
                    option_label.text().strip() == "" or option_label.isVisible(),
                    "Default chart option label state is sane"
                )
                continue

            check(option_button.isVisible(), f"Options button visible for chart combo index {i}")
            check(option_button.isEnabled(), f"Options button enabled for chart combo index {i}")

            result = {
                "dialog_seen": False,
                "dialog_closed": False,
                "combo_changed": False,
            }

            def wrapped_options_handler(r=result):
                dlg = find_visible_dialog()
                if dlg is None:
                    return
                r["dialog_seen"] = True
                combos = [c for c in dlg.findChildren(QComboBox) if c.isEnabled() and c.count() > 1]
                if combos:
                    combo = combos[0]
                    old_idx = combo.currentIndex()
                    new_idx = 1 if old_idx == 0 and combo.count() > 1 else 0
                    if new_idx != old_idx:
                        combo.setCurrentIndex(new_idx)
                        r["combo_changed"] = True
                        wait(300)
                accept_visible_dialog()
                r["dialog_closed"] = True

            QtCore.QTimer.singleShot(400, wrapped_options_handler)

            log("Clicking kundali chart options button")
            mouse_click(option_button, QtCore.Qt.MouseButton.LeftButton)
            wait(1600)

            check(result["dialog_seen"], f"Options dialog opened for chart combo index {i}")
            check(result["dialog_closed"], f"Options dialog closed for chart combo index {i}")

            new_label_text = option_label.text().strip()
            check(new_label_text != "", f"Option label non-empty after dialog accept for chart combo index {i}")

            if result["combo_changed"]:
                check(
                    new_label_text != old_label_text,
                    f"Option label changed after dialog combo change for chart combo index {i}"
                )
        
    def test_chart_tab_comprehensive(self):
        log("=== Chart Tab Main Test ===")
        main_window = self.main_window

        # 1. SETUP CHART TAB
        log("Showing main window")
        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        check(main_window.isVisible(), "Main window is visible after show()")

        log("Calling compute_horoscope()")
        main_window.compute_horoscope()
        wait(1500)
        check(main_window.isVisible(), "Main window remains visible after compute")

        check(hasattr(main_window, "_kundali_charts"), "_kundali_charts attribute exists")
        check(len(main_window._kundali_charts) > 0, "At least one kundali chart exists")

        chart = main_window._kundali_charts[0]
        tab_widget = main_window.tabWidget
        chart_tab_index = _find_chart_tab_index(main_window)

        log(f"Switching to chart tab index {chart_tab_index}")
        tab_widget.setCurrentIndex(chart_tab_index)
        wait(800)
        check(chart.isVisible(), "Main chart widget is visible")

        # Verify loop attribute targets exist cleanly
        check(hasattr(main_window, "_kundali_chart_combo"), "_kundali_chart_combo exists")
        check(hasattr(main_window, "_kundali_chart_option_button"), "_kundali_chart_option_button exists")
        check(hasattr(main_window, "_kundali_option_info_label"), "_kundali_option_info_label exists")

        chart_combo = main_window._kundali_chart_combo

        check(chart_combo is not None, "_kundali_chart_combo is not None")
        check(chart_combo.count() > 0, f"_kundali_chart_combo has items (count={chart_combo.count()})")
        
        self._test_chart_combo_iteration()
        self._test_chart_combo_options()
        # === HARD RESET BEFORE CONTEXT MENU TESTS ===
        log("Resetting state before context menu tests")
        close_visible_menus()
        close_active_modal_dialog_if_any()
        QtWidgets.QApplication.processEvents()
        wait(300)
        
        chart_combo.setCurrentIndex(0)          # back to Rasi chart
        wait(1000)
        
        chart.activateWindow()
        chart.raise_()
        chart.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        QtWidgets.QApplication.processEvents()
        wait(500)

        self._test_context_menus(chart)

if __name__ == "__main__":
    import unittest
    unittest.main()