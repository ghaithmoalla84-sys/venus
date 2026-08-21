# -*- coding: utf-8 -*-
"""
وحدات عرض المخزون لشاشة المواد والمخزون
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from venus.core.database import get_conn
from venus.core.repositories import MaterialsRepository
from venus.core.events import app_events
from venus.ui.widgets.searchable_table import SearchableTable
from venus.ui.widgets.entity_detail_dialog import EntityDetailDialog
from venus.ui.styles import Colors
from venus.utils.logger import setup_logger
logger = setup_logger()


class StockMixin:
    """ميكسين لعمليات عرض المخزون"""
    
    def load_materials_combo(self):
        """تحميل قائمة المواد في جدول بنود الفاتورة"""
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT معرف, الاسم FROM المواد_الفرعية ORDER BY الاسم
            """)
            materials = cursor.fetchall()

            self.materials_data = materials
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل المواد:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def load_inventory_display(self):
        """تحميل بيانات المخزون الحالي"""
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()

            group_filter = self.group_filter_combo.currentData()
            if group_filter is not None:
                cursor.execute("""
                    SELECT م.معرف, م.الاسم, م.الوحدة, ج.الاسم, خ.الكمية_المتوفرة, خ.آخر_تحديث, م.سعر_الشراء_الأخير, م.الحد_الأدنى
                    FROM المخزون خ
                    JOIN المواد_الفرعية م ON خ.معرف_المادة_الفرعية = م.معرف
                    JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                    WHERE م.معرف_المجموعة = ?
                    ORDER BY م.الاسم
                """, (group_filter,))
            else:
                cursor.execute("""
                    SELECT م.معرف, م.الاسم, م.الوحدة, ج.الاسم, خ.الكمية_المتوفرة, خ.آخر_تحديث, م.سعر_الشراء_الأخير, م.الحد_الأدنى
                    FROM المخزون خ
                    JOIN المواد_الفرعية م ON خ.معرف_المادة_الفرعية = م.معرف
                    JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                    ORDER BY م.الاسم
                """)

            data = cursor.fetchall()

            headers = ["المادة", "الوحدة", "المجموعة", "الكمية المتوفرة", "آخر تحديث", "سعر الشراء الأخير", "الحد الأدنى"]
            rows = [list(row) for row in data]

            self.inventory_table.set_data(headers, rows, id_column_index=0)

            self._apply_low_stock_warning()
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل المخزون:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _apply_low_stock_warning(self):
        """تطبيق تمييز بصري تحذيري على المواد التي تقل عن الحد الأدنى المحدد.

        يُظهر التمييز فقط للمواد **التي حدد صاحب المتجر حدّاً أدنى لها** (أكبر من صفر)
        وكميتها المتوفرة أقل من أو يساويه. لا يُخلط هذا التحذير بتنبيه "5 وحدات أو
        أقل" الثابت الموجود في لوحة المعلومات — فهذا تحذير مجموعي سريع في الـDashboard
        مقابل حد مخصّص لكل مادة هنا.
        """
        try:
            for row_data, row_idx in zip(self.inventory_table._rows_data, range(self.inventory_table.rowCount())):
                qty = float(row_data[4]) if row_data[4] is not None else 0
                min_qty = float(row_data[7]) if row_data[7] is not None else 0
                qty_item = self.inventory_table.table.item(row_idx, 3)
                min_item = self.inventory_table.table.item(row_idx, 6)
                if qty <= min_qty and min_qty > 0:
                    if qty_item:
                        qty_item.setForeground(QColor(Colors.WARNING))
                        f = qty_item.font()
                        f.setBold(True)
                        qty_item.setFont(f)
                    if min_item:
                        min_item.setForeground(QColor(Colors.WARNING))
                        f = min_item.font()
                        f.setBold(True)
                        min_item.setFont(f)
        except Exception:
            pass

    def _on_inventory_edit(self, material_id):
        """تعديل مادة من جدول المخزون"""
        repo = MaterialsRepository()
        material = repo.get_by_id(material_id)
        if not material:
            QMessageBox.warning(self, "تنبيه", "المادة غير موجودة")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("تعديل مادة")
        dialog.setLayoutDirection(Qt.RightToLeft)
        layout = QFormLayout(dialog)

        name_edit = QLineEdit(material["الاسم"])
        unit_combo = QComboBox()
        unit_combo.addItems(["كيلوغرام", "قطعة", "لتر"])
        unit_combo.setCurrentText(material["الوحدة"])
        price_edit = QLineEdit(str(material["سعر_الشراء_الأخير"] or 0))
        price_edit.setValidator(QDoubleValidator(0, 10000000, 2))
        min_stock_edit = QLineEdit(str(material.get("الحد_الأدنى", 0) or 0))
        min_stock_edit.setValidator(QDoubleValidator(0, 10000000, 2))

        groups_combo = QComboBox()
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT معرف, الاسم FROM المجموعات ORDER BY الترتيب, الاسم")
        groups = cursor.fetchall()
        conn.close()
        for gid, gname in groups:
            groups_combo.addItem(gname, gid)
        idx = groups_combo.findData(material["معرف_المجموعة"])
        if idx >= 0:
            groups_combo.setCurrentIndex(idx)

        layout.addRow("الاسم:", name_edit)
        layout.addRow("الوحدة:", unit_combo)
        layout.addRow("سعر الشراء الأخير:", price_edit)
        layout.addRow("الحد الأدنى للكمية:", min_stock_edit)
        layout.addRow("المجموعة:", groups_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            try:
                repo.update(
                    material_id,
                    الاسم=name_edit.text().strip(),
                    الوحدة=unit_combo.currentText(),
                    سعر_الشراء_الأخير=float(price_edit.text()),
                    الحد_الأدنى=float(min_stock_edit.text()),
                    معرف_المجموعة=groups_combo.currentData()
                )
                app_events.emit_data_changed("materials")
                self.load_inventory_display()
                QMessageBox.information(self, "نجاح", "تم تعديل المادة بنجاح")
            except Exception as e:
                logger.error(str(e))
                QMessageBox.critical(self, "خطأ", f"فشل تعديل المادة:\n{str(e)}")

    def _on_inventory_delete(self, material_id):
        """حذف مادة من جدول المخزون"""
        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            "هل أنت متأكد من حذف هذه المادة؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        repo = MaterialsRepository()
        try:
            affected = repo.delete(material_id)
            if affected > 0:
                app_events.emit_data_changed("materials")
                self.load_inventory_display()
                QMessageBox.information(self, "نجاح", "تم حذف المادة بنجاح")
        except Exception as e:
            logger.error(str(e))
            if "مرتبط" in str(e) or "تحرك" in str(e) or "تفاصيل" in str(e):
                QMessageBox.warning(
                    self, "لا يمكن الحذف",
                    "المادة مرتبطة بحركات مخزون أو فواتير شراء ولا يمكن حذفها.\n"
                    "يمكنك تعطيل المادة بدلاً من حذفها (يتطلب تعديل مخطط الجدول)."
                )
            else:
                QMessageBox.critical(self, "خطأ", f"فشل حذف المادة:\n{str(e)}")

    def _on_inventory_double_click(self, material_id):
        """فتح تفاصيل المادة عند النقر المزدوج"""
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT م.الاسم, م.الوحدة, ج.الاسم, خ.الكمية_المتوفرة, م.سعر_الشراء_الأخير, م.الحد_الأدنى
                FROM المواد_الفرعية م
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                LEFT JOIN المخزون خ ON م.معرف = خ.معرف_المادة_الفرعية
                WHERE م.معرف = ?
            """, (material_id,))
            row = cursor.fetchone()
            if not row:
                return

            name, unit, group, qty, last_price, min_qty = row

            detail_data = {
                "الاسم": name,
                "الوحدة": unit,
                "المجموعة": group,
                "الكمية الحالية": qty if qty is not None else 0,
                "سعر الشراء الأخير": last_price if last_price is not None else 0,
                "الحد الأدنى للكمية": min_qty if min_qty is not None else 0,
            }

            cursor.execute("""
                SELECT التاريخ, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات
                FROM تحركات_المخزون
                WHERE معرف_المادة_الفرعية = ?
                ORDER BY التاريخ DESC
                LIMIT 10
            """, (material_id,))
            movements = cursor.fetchall()

            related_headers = ["التاريخ", "نوع الحركة", "الكمية", "الرصيد بعد", "ملاحظات"]
            related_rows = [list(m) for m in movements]

            dialog = EntityDetailDialog(
                f"تفاصيل المادة: {name}",
                detail_data=detail_data,
                related_rows=related_rows,
                related_headers=related_headers
            )
            dialog.exec_()
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل التفاصيل:\n{str(e)}")
        finally:
            if conn:
                conn.close()
