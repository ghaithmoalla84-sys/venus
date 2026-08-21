# -*- coding: utf-8 -*-
"""
وحدات الجرد الدوري لشاشة المواد والمخزون
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime

from venus.core.database import get_conn
from venus.ui.screens.inventory.delegates import NumericDelegate
from venus.utils.logger import setup_logger
logger = setup_logger()


class AuditDialog(QDialog):
    """حوار الجرد الدوري"""
    audit_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 الجرد الدوري")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumSize(900, 600)
        self.audit_data = []
        self.audit_prices = {}
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        info_label = QLabel("أدخل الكميات الفعلية في العمود المخصص ثم اضغط 'حفظ الجرد'")
        info_label.setStyleSheet("""
            font-size: 14px;
            color: #2c3e50;
            padding: 10px;
            background-color: #fef9e7;
            border: 1px solid #f9e79f;
            border-radius: 6px;
        """)
        info_label.setAlignment(Qt.AlignRight)
        layout.addWidget(info_label)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(6)
        self.audit_table.setHorizontalHeaderLabels(["المادة", "الوحدة", "الكمية النظرية", "الكمية الفعلية", "الفرق", "قيمة الفرق"])
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.audit_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.audit_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                background-color: #ffffff;
                gridline-color: #ecf0f1;
            }
            QHeaderView::section {
                background-color: #e67e22;
                color: white;
                padding: 8px;
                font-weight: bold;
                border: none;
            }
            QTableWidget::item { padding: 8px; }
        """)
        self.audit_table.setAlternatingRowColors(True)
        self._numeric_delegate = NumericDelegate(self.audit_table)
        self.audit_table.setItemDelegate(self._numeric_delegate)
        self.audit_table.cellChanged.connect(self.calculate_audit_diff)
        layout.addWidget(self.audit_table)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)

        save_btn = QPushButton("حفظ الجرد")
        save_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_btn.setFixedHeight(40)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        save_btn.clicked.connect(self.save_audit)

        close_btn = QPushButton("إغلاق")
        close_btn.setFixedHeight(40)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        close_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def load_data(self):
        """تحميل جدول الجرد بالكميات النظرية الحالية"""
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT م.معرف, م.الاسم, م.الوحدة, خ.الكمية_المتوفرة, م.سعر_الشراء_الأخير
                FROM المواد_الفرعية م
                LEFT JOIN المخزون خ ON م.معرف = خ.معرف_المادة_الفرعية
                ORDER BY م.الاسم
            """)
            data = cursor.fetchall()
            conn.close()

            try:
                self.audit_table.cellChanged.disconnect(self.calculate_audit_diff)
            except TypeError:
                pass

            self.audit_data = data
            self.audit_prices = {}
            self.audit_table.setRowCount(len(data))
            for row, (mid, name, unit, qty, last_price) in enumerate(data):
                self.audit_table.setItem(row, 0, QTableWidgetItem(name))
                self.audit_table.setItem(row, 1, QTableWidgetItem(unit))
                self.audit_table.setItem(row, 2, QTableWidgetItem(str(qty if qty is not None else 0)))

                actual_item = QTableWidgetItem("")
                actual_item.setFlags(actual_item.flags() | Qt.ItemIsEditable)
                self.audit_table.setItem(row, 3, actual_item)

                diff_item = QTableWidgetItem("")
                diff_item.setFlags(diff_item.flags() & ~Qt.ItemIsEditable)
                self.audit_table.setItem(row, 4, diff_item)

                value_item = QTableWidgetItem("")
                value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                self.audit_table.setItem(row, 5, value_item)

                self.audit_prices[mid] = last_price if last_price is not None else 0

            self.audit_table.cellChanged.connect(self.calculate_audit_diff)
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل جدول الجرد:\n{str(e)}")

    def calculate_audit_diff(self, row, column):
        """حساب فرق الجرد تلقائياً"""
        if column == 3:
            try:
                theoretical_item = self.audit_table.item(row, 2)
                actual_item = self.audit_table.item(row, 3)
                diff_item = self.audit_table.item(row, 4)
                value_item = self.audit_table.item(row, 5)

                if theoretical_item and actual_item and diff_item and value_item:
                    theoretical = float(theoretical_item.text()) if theoretical_item.text() else 0
                    actual = float(actual_item.text()) if actual_item.text() else 0
                    diff = actual - theoretical
                    diff_item.setText(str(diff))

                    material_info = self.audit_data[row]
                    last_price = self.audit_prices.get(material_info[0], 0)
                    value = diff * last_price if last_price is not None else 0
                    value_item.setText(str(value))
            except ValueError:
                pass

    def save_audit(self):
        """حفظ الجرد الدوري"""
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            audit_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for row in range(self.audit_table.rowCount()):
                material_info = self.audit_data[row]
                material_id = material_info[0]
                name = material_info[1]
                theoretical_item = self.audit_table.item(row, 2)
                actual_item = self.audit_table.item(row, 3)
                diff_item = self.audit_table.item(row, 4)
                value_item = self.audit_table.item(row, 5)

                if not actual_item or not actual_item.text().strip():
                    continue

                theoretical = float(theoretical_item.text()) if theoretical_item.text() else 0
                actual = float(actual_item.text()) if actual_item.text() else 0
                diff = actual - theoretical
                value = float(value_item.text()) if value_item and value_item.text() else 0

                cursor.execute("""
                    INSERT INTO الجرد (التاريخ, معرف_المادة_الفرعية, الكمية_النظري, الكمية_الفعلي, فرق_الجرد, قيمة_الفرق, ملاحظات)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (audit_date, material_id, theoretical, actual, diff, value, f"جرد دوري - {name}"))

                cursor.execute("""
                    INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (material_id, actual))

                cursor.execute("""
                    INSERT INTO تحركات_المخزون
                    (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات)
                    VALUES (?, 'جرد', ?, ?, ?)
                """, (material_id, diff, actual, f"جرد دوري - {name}"))

            conn.commit()
            QMessageBox.information(self, "نجاح", "تم حفظ الجرد بنجاح!")
            self.audit_saved.emit()
        except Exception as e:
            logger.error(str(e))
            if conn:
                conn.rollback()
            QMessageBox.critical(self, "خطأ", f"فشل حفظ الجرد:\n{str(e)}")
        finally:
            if conn:
                conn.close()

