#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) Open Astro Technologies, USA.
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora

# This file is part of the "PyJHora" Python library
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import re
import sys
import os
from PyQt6 import QtCore, QtGui
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt
from _datetime import datetime, timedelta,time,date
import img2pdf
from jhora.horoscope.match import compatibility
from jhora import const, utils

_DATA_PATH = '../data/'
_IMAGES_PATH = '../images/'
_IMAGE_ICON_PATH=_IMAGES_PATH +"lord_ganesha2.jpg"


available_languages = {"English":'en','Tamil':'ta','Telugu':'te'}
_main_window_width = 600
_main_window_height = 510 #630

class MatchWindow(QWidget):
    def __init__(self, chart_type='south indian'):
        super().__init__()
        # --- Original Initialization ---
        self.setMinimumSize(_main_window_width, _main_window_height)
        self.setWindowIcon(QtGui.QIcon(_IMAGE_ICON_PATH))
        self._language = list(available_languages.keys())[0]
        self._matching_stars_tuple = []
        self.setWindowTitle(utils.resource_strings['window_title'] + '-' + const._APP_VERSION)
        
        v_layout = QVBoxLayout()
        
        # --- NEW: Method Selector & Extended Options Layout ---
        h_layout_method = QHBoxLayout()
        self._method_label = QLabel('Matching Method:')
        h_layout_method.addWidget(self._method_label)
        
        self._method_combo = QComboBox()
        self._method_combo.addItems(['North', 'South'])
        self._method_combo.setCurrentText('South' if 'south' in chart_type.lower() else 'North')
        # Connect method change to update visibility of the checkbox
        self._method_combo.currentIndexChanged.connect(self._update_visibility)
        h_layout_method.addWidget(self._method_combo)
        
        self._include_extended_porutham_check = QCheckBox('Include Varna and Nadi')
        self._include_extended_porutham_check.setChecked(False) 
        self._include_extended_porutham_check.toggled.connect(lambda: self._update_compatibility_table())
        h_layout_method.addWidget(self._include_extended_porutham_check)
        v_layout.addLayout(h_layout_method)
        # -----------------------------------------------------

        # Boy's Star Selection
        h_layout = QHBoxLayout()
        self._boy_star_label = QLabel("Boy's Birth Star:")
        h_layout.addWidget(self._boy_star_label)
        self._boy_star_combo = QComboBox()
        self._boy_star_combo.addItems(compatibility.nakshatra_list)
        h_layout.addWidget(self._boy_star_combo)
        self._boy_paadham_label = QLabel("Boy's Star Paadham:")
        h_layout.addWidget(self._boy_paadham_label)
        self._boy_paadham_combo = QSpinBox()
        self._boy_paadham_combo.setRange(1, 4)
        h_layout.addWidget(self._boy_paadham_combo)
        self._boy_show_all_matches_label = QLabel('Show All Matching Girl stars:')
        h_layout.addWidget(self._boy_show_all_matches_label)
        self._boy_show_all_matches_check = QCheckBox()
        self._boy_show_all_matches_check.setChecked(False)
        h_layout.addWidget(self._boy_show_all_matches_check)
        self._boy_show_all_matches_combo = QDoubleSpinBox()
        self._boy_show_all_matches_combo.setRange(0.0, 36.0)
        self._boy_show_all_matches_combo.setSingleStep(0.5)
        self._boy_show_all_matches_combo.setValue(18.0)
        h_layout.addWidget(self._boy_show_all_matches_combo)
        v_layout.addLayout(h_layout)

        # Girl's Star Selection
        h_layout = QHBoxLayout()
        self._girl_star_label = QLabel("Girl's Birth Star:")
        h_layout.addWidget(self._girl_star_label)
        self._girl_star_combo = QComboBox()
        self._girl_star_combo.addItems(compatibility.nakshatra_list)
        self._girl_star_combo.setCurrentText('Swati')
        h_layout.addWidget(self._girl_star_combo)
        self._girl_paadham_label = QLabel("Girl's Star Paadham:")
        h_layout.addWidget(self._girl_paadham_label)
        self._girl_paadham_combo = QSpinBox()
        self._girl_paadham_combo.setRange(1, 4)
        h_layout.addWidget(self._girl_paadham_combo)
        self._girl_show_all_matches_label = QLabel('Show All Matching Boy stars:')
        h_layout.addWidget(self._girl_show_all_matches_label)
        self._girl_show_all_matches_check = QCheckBox()
        self._girl_show_all_matches_check.setChecked(False)
        h_layout.addWidget(self._girl_show_all_matches_check)
        self._girl_show_all_matches_combo = QDoubleSpinBox()
        self._girl_show_all_matches_combo.setRange(0.0, 36.0)
        self._girl_show_all_matches_combo.setSingleStep(0.5)
        self._girl_show_all_matches_combo.setValue(18.0)
        h_layout.addWidget(self._girl_show_all_matches_combo)
        v_layout.addLayout(h_layout)

        # Optional Checks
        h_layout = QHBoxLayout()
        self._mahendra_label = QLabel('Mahendra Porutham Mandatory:')
        h_layout.addWidget(self._mahendra_label)
        self._mahendra_porutham_check = QCheckBox()
        self._mahendra_porutham_check.setChecked(False)
        h_layout.addWidget(self._mahendra_porutham_check)
        self._vedha_label = QLabel('Vedha Porutham Mandatory:')
        h_layout.addWidget(self._vedha_label)
        self._vedha_porutham_check = QCheckBox()
        self._vedha_porutham_check.setChecked(False)
        h_layout.addWidget(self._vedha_porutham_check)
        v_layout.addLayout(h_layout)

        h_layout = QHBoxLayout()
        self._rajju_label = QLabel('Rajju Porutham Mandatory:')
        h_layout.addWidget(self._rajju_label)
        self._rajju_porutham_check = QCheckBox()
        self._rajju_porutham_check.setChecked(False)
        h_layout.addWidget(self._rajju_porutham_check)
        self._shree_dheerga_label = QLabel('Shree Dheerga Porutham Mandatory:')
        h_layout.addWidget(self._shree_dheerga_label)
        self._shree_dheerga_porutham_check = QCheckBox()
        self._shree_dheerga_porutham_check.setChecked(False)
        h_layout.addWidget(self._shree_dheerga_porutham_check)
        v_layout.addLayout(h_layout)
        
        self._compute_button = QPushButton('Show Match')
        v_layout.addWidget(self._compute_button)
        
        # Results Section
        h_layout = QHBoxLayout()
        self._matching_star_list = QListWidget()
        self._matching_star_list.currentRowChanged.connect(self._update_compatibility_table)
        self._matching_star_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._matching_star_list.setVerticalScrollBar(QScrollBar(self))
        h_layout.addWidget(self._matching_star_list)
        
        self._results_table = QTableWidget(13, 4)
        self._results_table.verticalHeader().hide()
        self._results_table.setHorizontalHeaderItem(0, QTableWidgetItem('Porutham/Koota'))
        self._results_table.setHorizontalHeaderItem(1, QTableWidgetItem('Score'))
        self._results_table.setHorizontalHeaderItem(2, QTableWidgetItem('Max Score'))
        self._results_table.setHorizontalHeaderItem(3, QTableWidgetItem('%'))
        self._results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._results_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        h_layout.addWidget(self._results_table)
        
        self._matching_star_list.setMinimumHeight(self._results_table.height())
        v_layout.addLayout(h_layout)

        # Signal Connections
        self._boy_show_all_matches_check.toggled.connect(self._check_only_boy_or_girl)
        self._girl_show_all_matches_check.toggled.connect(self._check_only_boy_or_girl)
        self._compute_button.clicked.connect(self._get_compatibility)
        self.setLayout(v_layout)
        
        # Initialize Visibility
        self._update_visibility()
        self._get_compatibility()
    def _update_visibility(self):
        is_south = 'south' in self._method_combo.currentText().lower()
        self._include_extended_porutham_check.setVisible(is_south)
        self._update_compatibility_table()
        
    def _clear_results_table(self):
        self._results_table.clear()
        self._results_table.setRowCount(0)
        self._results_table.setColumnCount(0)
    
    def _prepare_results_table(self):
        self._results_table.clear()
        self._results_table.setRowCount(13)
        self._results_table.setColumnCount(4)
    
        self._results_table.verticalHeader().hide()
        self._results_table.setHorizontalHeaderItem(0, QTableWidgetItem('Porutham/Koota'))
        self._results_table.setHorizontalHeaderItem(1, QTableWidgetItem('Score'))
        self._results_table.setHorizontalHeaderItem(2, QTableWidgetItem('Max Score'))
        self._results_table.setHorizontalHeaderItem(3, QTableWidgetItem('%'))
    
        self._results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._results_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        
    def _get_compatibility(self):
        if self._girl_show_all_matches_check.isChecked():
            bn = None
            bp = None
        else:
            bn = self._boy_star_combo.currentIndex() + 1
            bp = self._boy_paadham_combo.value()
    
        if self._boy_show_all_matches_check.isChecked():
            gn = None
            gp = None
        else:
            gn = self._girl_star_combo.currentIndex() + 1
            gp = self._girl_paadham_combo.value()
    
        m_check = True if self._mahendra_porutham_check.isChecked() else None
        v_check = True if self._vedha_porutham_check.isChecked() else None
        r_check = True if self._rajju_porutham_check.isChecked() else None
        s_check = True if self._shree_dheerga_porutham_check.isChecked() else None
        selected_method = self._method_combo.currentText()
        comp = compatibility.Match(
            boy_nakshatra_number=bn,
            boy_paadham_number=bp,
            girl_nakshatra_number=gn,
            girl_paadham_number=gp,
            check_for_mahendra_porutham=m_check,
            check_for_vedha_porutham=v_check,
            check_for_rajju_porutham=r_check,
            check_for_shreedheerga_porutham=s_check,
            method = selected_method
        )
    
        self._matching_stars_tuple = utils.sort_tuple(
            comp.get_matching_partners(),
            3,
            reverse=True
        )
    
        self._matching_star_list.clear()
    
        if not self._matching_stars_tuple:
            self._matching_star_list.addItems(['No matching found'])
    
            self._results_table.clear()
            self._results_table.setRowCount(0)
            self._results_table.setColumnCount(0)
            return
    
        matching_stars = []
    
        for m_s_tup in self._matching_stars_tuple:
            nakshatra = compatibility.nakshatra_list[m_s_tup[0] - 1]
            paadham = 'Paadham-' + str(m_s_tup[1])
            matching_stars.append(nakshatra + '-' + paadham)
    
        self._matching_star_list.addItems(matching_stars)
    
        # This will trigger currentRowChanged and update the table.
        self._matching_star_list.setCurrentRow(0)
    
        # Extra safety in case currentRowChanged does not fire.
        self._update_compatibility_table(0)
        

    def _check_only_boy_or_girl(self):
        if self._boy_show_all_matches_check.isChecked():
            ' disable all girl ui elements'
            self._girl_star_label.setEnabled(False)
            self._girl_star_combo.setEnabled(False)
            self._girl_paadham_label.setEnabled(False)
            self._girl_paadham_combo.setEnabled(False)
        else: #if not self._boy_show_all_matches_check.isChecked():
            ' enable all girl ui elements'
            self._girl_star_label.setEnabled(True)
            self._girl_star_combo.setEnabled(True)
            self._girl_paadham_label.setEnabled(True)
            self._girl_paadham_combo.setEnabled(True)
        if self._girl_show_all_matches_check.isChecked():
            ' disable all boy ui elements'
            self._boy_star_label.setEnabled(False)
            self._boy_star_combo.setEnabled(False)
            self._boy_paadham_label.setEnabled(False)
            self._boy_paadham_combo.setEnabled(False)
        else: #if not self._girl_show_all_matches_check.isChecked():
            ' enable all boy ui elements'
            self._boy_star_label.setEnabled(True)
            self._boy_star_combo.setEnabled(True)
            self._boy_paadham_label.setEnabled(True)
            self._boy_paadham_combo.setEnabled(True)
    
    def _update_compatibility_table(self, current_row=None):
        """
        Updates the compatibility table and dynamically calculates 
        totals for the 'Overall Matching Score' row.
        """
        results_table = self._results_table
        
        # 1. Determine index from list or argument
        if current_row is None:
            selected_list_index = self._matching_star_list.currentRow()
        else:
            selected_list_index = current_row

        if not hasattr(self, '_matching_stars_tuple') or not self._matching_stars_tuple or selected_list_index < 0:
            results_table.clear()
            results_table.setRowCount(0)
            return

        selected_matching_star_tuple = self._matching_stars_tuple[selected_list_index]
        ettu_porutham_results = selected_matching_star_tuple[2]
        naalu_porutham_results = selected_matching_star_tuple[4]

        # 2. Configuration
        is_south = 'south' in self._method_combo.currentText().lower()
        include_all = self._include_extended_porutham_check.isChecked()

        # 3. Define all items (using variables for max scores)
        all_ettu_items = [
            ('varna porutham', ettu_porutham_results[0], compatibility.varna_max_score),
            ('vasiya porutham', ettu_porutham_results[1], compatibility.vasiya_max_score),
            ('gana porutham', ettu_porutham_results[2], compatibility.gana_max_score),
            ('nakshathra porutham', ettu_porutham_results[3], compatibility.nakshathra_max_score),
            ('yoni porutham', ettu_porutham_results[4], compatibility.yoni_max_score),
            ('adhipathi porutham', ettu_porutham_results[5], compatibility.raasi_adhipathi_max_score),
            ('raasi porutham', ettu_porutham_results[6], compatibility.raasi_max_score),
            ('naadi porutham', ettu_porutham_results[7], compatibility.naadi_max_score)
        ]
        
        naalu_items = [
            ('mahendra porutham', naalu_porutham_results[0]),
            ('vedha porutham', naalu_porutham_results[1]),
            ('rajju porutham', naalu_porutham_results[2]),
            ('sthree dheerga porutham', naalu_porutham_results[3])
        ]

        # 4. Filter and Calculate
        display_rows = []
        total_achieved = 0.0
        total_possible = 0.0

        # Helper to convert "True"/"False" or numbers to float
        def get_numeric(val):
            if isinstance(val, bool): return 1.0 if val else 0.0
            if str(val).lower() == 'true': return 1.0
            if str(val).lower() == 'false': return 0.0
            try: return float(val)
            except: return 0.0

        # Process Ettu Porutham
        for i, item in enumerate(all_ettu_items):
            if is_south and not include_all and (i == 0 or i == 7):
                continue
            
            score_val = get_numeric(item[1])
            max_val = 1.0 if is_south else float(item[2])
            
            display_rows.append({'name': item[0], 'score': score_val, 'max': max_val})
            total_achieved += score_val
            total_possible += max_val

        # Process Naalu Porutham (Always included for South)
        if is_south:
            for item in naalu_items:
                score_val = get_numeric(item[1])
                display_rows.append({'name': item[0], 'score': score_val, 'max': 1.0})
                total_achieved += score_val
                total_possible += 1.0

        # 5. Build Table
        results_table.clear()
        results_table.setRowCount(len(display_rows) + 1)
        results_table.setColumnCount(4)
        results_table.setHorizontalHeaderLabels(['Porutham/Koota', 'Score', 'Max Score', '%'])

        for row, data in enumerate(display_rows):
            results_table.setItem(row, 0, QTableWidgetItem(data['name'].title()))
            
            if is_south:
                # South Method: Display True/False and Check/Cross
                score_str = "True" if data['score'] > 0 else "False"
                max_str = "True"
                perc_str = "✅" if data['score'] > 0 else "❌"
            else:
                # North Method: Display standard numeric values
                score_str = str(data['score'])
                max_str = str(data['max'])
                p = (data['score'] / data['max'] * 100) if data['max'] > 0 else 0
                perc_str = f"{int(p)}%"

            results_table.setItem(row, 1, QTableWidgetItem(score_str))
            results_table.setItem(row, 2, QTableWidgetItem(max_str))
            
            perc_item = QTableWidgetItem(perc_str)
            if is_south:
                # Center align the visual checkmarks for a cleaner UI
                perc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            results_table.setItem(row, 3, perc_item)

        # 6. Overall Row
        total_row = len(display_rows)
        results_table.setItem(total_row, 0, QTableWidgetItem('Overall Matching Score'))
        
        if is_south:
            # 1. Enforce the 4 user-controlled checkboxes strictly based on selection
            req_mahendra = self._mahendra_porutham_check.isChecked()
            req_vedha = self._vedha_porutham_check.isChecked()
            req_rajju = self._rajju_porutham_check.isChecked()
            req_shree = self._shree_dheerga_porutham_check.isChecked()
            
            has_mahendra = bool(naalu_porutham_results[0])
            has_vedha = bool(naalu_porutham_results[1])
            has_rajju = bool(naalu_porutham_results[2])
            has_shree = bool(naalu_porutham_results[3])
            
            checkboxes_pass = True
            if req_mahendra and not has_mahendra: checkboxes_pass = False
            if req_vedha and not has_vedha: checkboxes_pass = False
            if req_rajju and not has_rajju: checkboxes_pass = False
            if req_shree and not has_shree: checkboxes_pass = False
            
            # 2. Apply traditional minimum logic to the remaining core Ettu items
            has_dina = bool(ettu_porutham_results[3])   # Nakshathra Porutham
            has_gana = bool(ettu_porutham_results[2])
            has_yoni = bool(ettu_porutham_results[4])
            has_rasi = bool(ettu_porutham_results[6])
            
            if has_rajju and len(naalu_porutham_results) > 4:
                # If Rajju is naturally True, the backend column accurately reflects the other 6/8 items
                other_items_pass = bool(naalu_porutham_results[4])
            else:
                # If Rajju is False but user ignored it, check if the other core items meet the standard baseline (3 out of 4)
                other_items_score = sum([has_dina, has_gana, has_yoni, has_rasi])
                other_items_pass = other_items_score >= 3

            # Final Verdict: Both conditions must clear
            is_overall_match = checkboxes_pass and other_items_pass
            
            # Display numeric counts of Trues vs Total evaluated Poruthams (10 or 12)
            overall_score_str = str(int(total_achieved))
            overall_max_str = str(int(total_possible))
            overall_perc_str = "✅" if is_overall_match else "❌"
            
            results_table.setItem(total_row, 1, QTableWidgetItem(overall_score_str))
            results_table.setItem(total_row, 2, QTableWidgetItem(overall_max_str))
            
            overall_perc_item = QTableWidgetItem(overall_perc_str)
            overall_perc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            results_table.setItem(total_row, 3, overall_perc_item)
        else:
            # North Method summary logic
            results_table.setItem(total_row, 1, QTableWidgetItem(str(total_achieved)))
            results_table.setItem(total_row, 2, QTableWidgetItem(str(total_possible)))
            
            overall_perc = (total_achieved / total_possible * 100) if total_possible > 0 else 0
            results_table.setItem(total_row, 3, QTableWidgetItem(f"{int(overall_perc)}%"))

        for c in range(results_table.columnCount()):
            results_table.resizeColumnToContents(c)

if __name__ == "__main__":
    def except_hook(cls, exception, traceback):
        print('exception called')
        sys.__excepthook__(cls, exception, traceback)
    sys.excepthook = except_hook
    App = QApplication(sys.argv)
    chart = MatchWindow(chart_type='south')
    chart.show()
    sys.exit(App.exec())