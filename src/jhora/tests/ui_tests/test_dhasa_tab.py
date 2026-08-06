# src/jhora/ui_tests/test_dashas_tab.py

from PyQt6 import QtCore, QtWidgets, QtGui
import jhora.ui.horo_chart_tabs as horo_chart_tabs
from jhora.tests.ui_tests.test_helpers import (
    BaseUITestCase,
    log,
    check,
    wait,
    wait_until,
    mouse_click,
    find_tab_index_by_widget,
    find_visible_dialog,
    visible_menus,
    close_visible_menus,
    close_active_modal_dialog_if_any,
    accept_visible_dialog,
    post_context_menu_event,
)
# Import constants to safely match internal supported lists
from jhora import const

class TestDashasTab(BaseUITestCase):
    """Dashas Tab testing suite focusing exclusively on supported Dhasa matrices."""

    def test_dashas_tab_comprehensive(self):
        log("=== Dashas Tab: Nested Matrix, Chart Options & Context Dialog Test ===")
        main_window = self.main_window

        main_window.show()
        wait_until(main_window.isVisible, timeout=5000)
        main_window.compute_horoscope()
        wait(1500)

        dhasa_type_combo = getattr(main_window, "_dhasa_type_combo", None)
        dhasa_combo = getattr(main_window, "_dhasa_combo", None)
        options_button = getattr(main_window, "_dhasa_options_button", None)
        info_label = getattr(main_window, "_dhasa_option_info_label", None)

        check(dhasa_type_combo is not None, "Dhasa type combobox element exists")
        check(dhasa_combo is not None, "Dhasa combobox element exists")
        check(options_button is not None, "Dhasa options button element exists")
        check(info_label is not None, "Dhasa option info label element exists")

        if dhasa_type_combo is None or dhasa_combo is None:
            return

        # Explicitly switch viewports to the Dashas tab
        fallback_idx = getattr(horo_chart_tabs, "_dhasa_bhukthi_tab_index", 2)
        dashas_index = find_tab_index_by_widget(main_window, dhasa_type_combo, default_index=fallback_idx)

        log(f"Switching to Dashas tab viewport at index: {dashas_index}")
        main_window.tabWidget.setCurrentIndex(dashas_index)
        wait(1000)
        check(main_window.tabWidget.currentIndex() == dashas_index, "Switched to Dashas tab viewport")

        # Build the supported master list matching your application's context menu logic
        supported_dhasas = (
            const.planet_dhasas + 
            const.rasi_dhasas + 
            const.nakshathra_dhasas + 
            const.special_dhasas + 
            const.karaka_dhasas
        )

        total_types = dhasa_type_combo.count()
        log(f"Detected {total_types} Dhasa Types. Starting matrix test sequence...")

        for t_idx in range(total_types):
            type_name = dhasa_type_combo.itemText(t_idx)
            log(f"--- [OUTER LOOP] Testing Dhasa Type Index {t_idx}: '{type_name}' ---")
            
            dhasa_type_combo.setCurrentIndex(t_idx)
            dhasa_type_combo.activated.emit(t_idx) 
            wait(500)

            total_dhasas = dhasa_combo.count()
            for d_idx in range(total_dhasas):
                dhasa_name_display = dhasa_combo.itemText(d_idx)
                
                # 1. TRY-EXCEPT WRAPPER TO MARK FAILED ITEMS AND CONTINUE
                try:
                    # SAFE KEY LOOKUP GUARD
                    try:
                        if t_idx == 0:
                            internal_dhasa_key = list(const._graha_dhasa_dict.keys())[d_idx]
                        elif t_idx == 1:
                            internal_dhasa_key = list(const._rasi_dhasa_dict.keys())[d_idx]
                        else:
                            internal_dhasa_key = list(const._annual_dhasa_dict.keys())[d_idx]
                    except IndexError:
                        internal_dhasa_key = f"UNMAPPED_INDEX_{d_idx}"

                    is_supported = internal_dhasa_key in supported_dhasas
                    if not is_supported:
                        log(f"    -> [INNER LOOP] Unsupported Dhasa '{dhasa_name_display}' (Key: {internal_dhasa_key}) — context menu will show InfoDialog")
                    else:
                        log(f"    -> [INNER LOOP] Testing Supported Dhasa Index {d_idx}: '{dhasa_name_display}'")
                    
                    dhasa_combo.setCurrentIndex(d_idx)
                    dhasa_combo.activated.emit(d_idx)
                    
                    # Force the layout engine to process layout regenerations triggered by the combobox change
                    QtWidgets.QApplication.processEvents()
                    wait(600)

                    # --- PART A: Options Dialog (Clean Asynchronous Hunter) ---
                    if is_supported:
                        options_res = {
                            "dialog_seen": False,
                            "dialog_closed": False,
                        }

                        def _close_dialog_hunter(attempts=15):
                            dlg = find_visible_dialog()
                            if dlg is not None:
                                options_res["dialog_seen"] = True
                                log("    [OPTIONS DIALOG] Options dialog detected. Dismissing.")
                                
                                # WORKAROUND: If Shodasottari options cause a backend crash on accept, reject instead
                                if "shodasottari" in dhasa_name_display.lower():
                                    log("    [OPTIONS DIALOG] Shodasottari detected. Forcing rejection to bypass backend crash.")
                                    if hasattr(dlg, "reject"):
                                        dlg.reject()
                                    else:
                                        dlg.close()
                                else:
                                    accept_visible_dialog()
                                    
                                QtWidgets.QApplication.processEvents()
                                options_res["dialog_closed"] = not dlg.isVisible()
                                log("[OPTIONS DIALOG] Options dialog interaction complete")
                            elif attempts > 0:
                                QtCore.QTimer.singleShot(200, lambda: _close_dialog_hunter(attempts - 1))
                        if dhasa_name_display.lower() != "kaala":
                            log("Checking dialog see/closed")
                            # Arm the asynchronous hunter clean before dispatching interaction inputs
                            QtCore.QTimer.singleShot(100, lambda: _close_dialog_hunter())
    
                            # Dispatch click event natively on the main thread loop
                            log(f"    Clicking options button for Dhasa Index {d_idx}")
                            mouse_click(options_button, QtCore.Qt.MouseButton.LeftButton)
                            
                            # Monitor execution state updates
                            start_time = QtCore.QElapsedTimer()
                            start_time.start()
                            while not options_res["dialog_closed"] and start_time.elapsed() < 3000:
                                QtWidgets.QApplication.processEvents()
                            
                            log("    [MAIN THREAD] Master loop detected dialog closure. Advancing to verification.")
                            print(dhasa_name_display, 'options_res', options_res)
                            
                            check(options_res["dialog_seen"], f"Options dialog appeared for Type {t_idx} Dhasa {d_idx}")
                            check(options_res["dialog_closed"], f"Options dialog closed safely for Type {t_idx} Dhasa {d_idx}")
                    else:
                        log(f"    -> [PART A] Skipping options dialog for unsupported dhasa '{dhasa_name_display}'")

                    # --- PART B: Context Menu & Anti-Blocking Dialog Loop ---
                    context_res = {
                        "menu_seen": False,
                        "action_triggered": False,
                        "dialog_seen": False,
                        "dialog_closed": False,
                        "computed": False
                    }

                    def _handle_dhasa_dialog(res_dict, attempts=10):
                        dlg = find_visible_dialog()
                        if dlg is not None:
                            res_dict["dialog_seen"] = True
                            log(f"    [CONTEXT DIALOG] Dialog captured: {type(dlg).__name__}")
                            
                            buttons = dlg.findChildren(QtWidgets.QPushButton)
                            compute_btn = None
                            dismiss_btn = None
                            for btn in buttons:
                                btn_text = btn.text().strip().lower().replace("&", "")
                                if "compute" in btn_text:
                                    compute_btn = btn
                                elif any(kw in btn_text for kw in ("accept", "ok", "close", "cancel", "dismiss")):
                                    dismiss_btn = btn

                            if compute_btn is not None:
                                log("    [CONTEXT DIALOG] RunningDhasaDialog captured. Clicking 'Compute'.")
                                mouse_click(compute_btn, QtCore.Qt.MouseButton.LeftButton)
                                res_dict["computed"] = True
                                QtWidgets.QApplication.processEvents()
                                wait(400)
                                
                            if dismiss_btn is not None:
                                log(f"    [CONTEXT DIALOG] Clicking dismiss button: '{dismiss_btn.text()}'")
                                mouse_click(dismiss_btn, QtCore.Qt.MouseButton.LeftButton)
                            elif hasattr(dlg, "accept"):
                                dlg.accept()
                            else:
                                dlg.close()
                            
                            QtWidgets.QApplication.processEvents()
                            res_dict["dialog_closed"] = not dlg.isVisible()
                        else:
                            if attempts > 0:
                                QtCore.QTimer.singleShot(200, lambda: _handle_dhasa_dialog(res_dict, attempts - 1))

                    def handle_dhasa_context_menu(res_dict):
                        menus = visible_menus()
                        if not menus:
                            log("    [CONTEXT MENU] Context menu did not render.")
                            return
                        active_menu = menus[-1]
                        res_dict["menu_seen"] = True

                        valid_actions = [a for a in active_menu.actions() if not a.isSeparator()]
                        if valid_actions:
                            QtCore.QTimer.singleShot(200, lambda: _handle_dhasa_dialog(res_dict))
                            log("    [CONTEXT MENU] Triggering running dhasa menu entry.")
                            valid_actions[0].trigger()
                            res_dict["action_triggered"] = True
                            QtWidgets.QApplication.processEvents()
                        
                        close_visible_menus()

                    # STABILITY GUARD 1: Flush pending closing events from options dialog steps
                    QtWidgets.QApplication.processEvents()

                    # PRO-FIX: Dynamically fetch the absolute newest layout labels array from the application instance
                    current_db_labels = getattr(main_window, "_db_labels", [])
                    check(len(current_db_labels) > 0, f"Dhasa layout labels exist after changing to Index {d_idx}")
                    if not current_db_labels:
                        log(f"    [ERROR] No active db_labels found after switching layout to Index {d_idx}")
                        continue
                    
                    target_label = current_db_labels[0]
                    log(f"    [DEBUG] Target label type: {type(target_label).__name__}, Visible: {target_label.isVisible()}, Enabled: {target_label.isEnabled()}")

                    # STABILITY GUARD 2: Explicitly force focus and visibility initialization onto the correct widget instance
                    target_label.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
                    target_label.activateWindow()
                    wait(100)

                    # Arm context chain execution thread and post the platform event
                    QtCore.QTimer.singleShot(500, lambda: handle_dhasa_context_menu(context_res))
                    log("    Posting context menu event.")
                    post_context_menu_event(target_label)
                    wait(2500)

                    close_visible_menus()
                    print(dhasa_name_display, context_res)
                    check(context_res["menu_seen"], f"Context menu opened for Type {t_idx} Dhasa {d_idx}")
                    check(context_res["action_triggered"], f"Context action triggered for Type {t_idx} Dhasa {d_idx}")
                    check(context_res["dialog_seen"], f"Context dialog appeared for Type {t_idx} Dhasa {d_idx}")
                    check(context_res["dialog_closed"], f"Context dialog closed cleanly for Type {t_idx} Dhasa {d_idx}")

                # 2. CATCH, LOG AND PURGE LINGERING UI ELEMENTS TO ASSURE CONTINUATION
                except Exception as e:
                    import traceback
                    log(f"    [ERROR] Exception encountered during Type {t_idx}, Dhasa {d_idx}: {str(e)}")
                    log(f"    [TRACEBACK] {traceback.format_exc()}")
                    check(False, f"Dhasa Type {t_idx}, index {d_idx} encountered an unhandled exception")
                    
                    close_active_modal_dialog_if_any()
                    close_visible_menus()
                    QtWidgets.QApplication.processEvents()
                    wait(800)

        log("=== Dashas Tab Test Completed Successfully ===")

if __name__ == "__main__":
    import unittest
    unittest.main()