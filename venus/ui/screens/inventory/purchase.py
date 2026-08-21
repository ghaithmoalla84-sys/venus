# Path: D:\acc\venus\ui\screens\inventory\purchase.py
# -*- coding: utf-8 -*-
"""
وحدات فواتير الشراء لشاشة المواد والمخزون
"""

from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime, timedelta

from venus.core.database import get_conn, now_str
from venus.core.repositories import MaterialsRepository, CreditorsRepository
from venus.core.events import app_events
from venus.ui.widgets.combo_quick_add import ComboWithQuickAdd
from venus.ui.widgets.searchable_material_combo import SearchableMaterialCombo
from venus.ui.widgets.entity_detail_dialog import EntityDetailDialog
from venus.utils.currency import fmt
from venus.utils.logger import setup_logger
logger = setup_logger()


class BillItemsTable(QTableWidget):
    """جدول بنود الفاتورة مع دعم مفتاح Enter للتنقل بين الصفوف"""

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            current_row = self.currentRow()
            current_column = self.currentColumn()

            if current_column in (1, 2, 3) and self.state() == QTableWidget.EditingState:
                if current_row < self.rowCount() - 1:
                    self.setCurrentCell(current_row + 1, current_column)
                    self.editItem(self.item(current_row + 1, current_column))
                else:
                    # البحث عن الأب الذي يملك add_bill_row (حالياً InventoryScreen عبر PurchaseBillMixin).
                    # إذا أُعيد هيكلة شجرة الواجهة مستقبلاً بإضافة حاويات وسيطة جديدة،
                    # يجب التأكد أن هذا المسار ما زال يصل للكلاس الصحيح،
                    # أو استبداله بمرجع مباشر (تمرير reference للشاشة الأم عند إنشاء BillItemsTable).
                    parent = self.parent()
                    while parent is not None and not hasattr(parent, 'add_bill_row'):
                        parent = parent.parent()
                    if parent is not None:
                        parent.add_bill_row()
                        new_row = self.rowCount() - 1
                        self.setCurrentCell(new_row, 1)
                        self.editItem(self.item(new_row, 1))
                event.accept()
                return
        super().keyPressEvent(event)


class PurchaseBillMixin:
    """ميكسين لعمليات فواتير الشراء"""
    
    def _load_materials_for_combo(self):
        logger.debug("_load_materials_for_combo: بدأت")
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT م.معرف, م.الاسم, ج.الاسم, م.سعر_الشراء_الأخير,
                       COALESCE(خ.الكمية_المتوفرة, 0), م.الوحدة
                FROM المواد_الفرعية م
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                LEFT JOIN المخزون خ ON خ.معرف_المادة_الفرعية = م.معرف
                ORDER BY ج.الاسم, م.الاسم
            """)
            result = []
            for row in cursor.fetchall():
                result.append({
                    'id': row[0],
                    'name': row[1],
                    'group': row[2],
                    'last_price': row[3] or 0,
                    'qty': row[4] or 0,
                    'unit': row[5]
                })
            logger.debug(f"_load_materials_for_combo: أرجعت {len(result)} عنصر")
            return result
        except Exception as e:
            logger.error(f"_load_materials_for_combo خطأ: {e}", exc_info=True)
            return []
        finally:
            conn.close()
            logger.debug("_load_materials_for_combo: أغلقت الاتصال")

    def _add_material_dialog(self):
        """حوار إضافة مادة سريعة"""
        dialog = QDialog(self)
        dialog.setWindowTitle("إضافة مادة جديدة")
        dialog.setLayoutDirection(Qt.RightToLeft)
        layout = QFormLayout(dialog)

        name_edit = QLineEdit()
        unit_combo = QComboBox()
        unit_combo.addItems(["كيلوغرام", "قطعة", "لتر"])
        price_edit = QLineEdit("0")
        price_edit.setValidator(QDoubleValidator(0, 10000000, 2))
        min_stock_edit = QLineEdit("0")
        min_stock_edit.setValidator(QDoubleValidator(0, 10000000, 2))

        groups_combo = QComboBox()
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT معرف, الاسم FROM المجموعات ORDER BY الترتيب, الاسم")
            groups = cursor.fetchall()
        except Exception as e:
            logger.error(f"فشل تحميل المجموعات في نافذة إضافة المادة: {type(e).__name__}")
            groups = []
        finally:
            conn.close()
        for gid, gname in groups:
            groups_combo.addItem(gname, gid)

        layout.addRow("الاسم:", name_edit)
        layout.addRow("الوحدة:", unit_combo)
        layout.addRow("سعر الشراء الابتدائي:", price_edit)
        layout.addRow("الحد الأدنى للكمية:", min_stock_edit)
        layout.addRow("المجموعة:", groups_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            name = name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم المادة")
                return None
            try:
                repo = MaterialsRepository()
                mid = repo.create(
                    الاسم=name,
                    الوحدة=unit_combo.currentText(),
                    معرف_المجموعة=groups_combo.currentData(),
                    سعر_الشراء_الأخير=float(price_edit.text()),
                    الحد_الأدنى=float(min_stock_edit.text())
                )
                app_events.emit_data_changed("materials")
                return mid
            except Exception as e:
                logger.error(str(e))
                QMessageBox.critical(self, "خطأ", f"فشل إضافة المادة:\n{str(e)}")
        return None

    def _load_suppliers_for_combo(self):
        """تحميل قائمة الموردين لـ ComboWithQuickAdd — يرجع أزواج (اسم، معرّف)"""
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT معرف, اسم_الطرف FROM الديون
                WHERE نوع_الطرف = 'مورد'
                ORDER BY اسم_الطرف
            """)
            return [(row[1], row[0]) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _add_supplier_dialog(self):
        """حوار إضافة مورد سريع"""
        dialog = QDialog(self)
        dialog.setWindowTitle("إضافة مورد جديد")
        dialog.setLayoutDirection(Qt.RightToLeft)
        layout = QFormLayout(dialog)

        name_edit = QLineEdit()
        layout.addRow("اسم المورد:", name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            name = name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم المورد")
                return None
            try:
                repo = CreditorsRepository()
                supplier_id = repo.create(
                    اسم_الطرف=name,
                    نوع_الطرف="مورد",
                    العملة="ليرة_سورية",
                    المبلغ_الإجمالي=0,
                    الرصيد=0,
                    حالة_الدين="نشط"
                )
                app_events.emit_data_changed("creditors")
                return name
            except Exception as e:
                logger.error(str(e))
                QMessageBox.critical(self, "خطأ", f"فشل إضافة المورد:\n{str(e)}")
        return None

    def _check_material_duplicate(self, material_id, current_combo):
        """التحقق من عدم تكرار نفس المادة في صفوف أخرى"""
        for row in range(self.items_table.rowCount()):
            widget = self.items_table.cellWidget(row, 0)
            if widget is None or widget is current_combo:
                continue
            val = widget.currentData() if hasattr(widget, 'currentData') else getattr(widget, 'current_value', None)
            if val == material_id:
                QMessageBox.warning(
                    self, "تنبيه",
                    f"هذه المادة موجودة بالفعل في الصف رقم {row + 1}.\n"
                    "يرجى تعديل الصف الموجود بدلاً من إنشاء صف مكرر."
                )
                return False
        return True

    def _on_material_selected(self, row, material_id):
        """عند اختيار مادة: تعبئة سعر الوحدة تلقائياً بآخر سعر شراء"""
        if material_id is None:
            return
        widget = self.items_table.cellWidget(row, 0)
        if widget is None:
            return
        data = None
        for item in getattr(widget, '_all_items', []):
            if item.get('id') == material_id:
                data = item
                break
        if not data:
            return
        price = data.get('last_price', 0) or 0
        price_item = self.items_table.item(row, 2)
        if price_item:
            price_item.setText(str(price))
        self.calculate_row_total(row, 2)

    def add_bill_row(self):
        """إضافة صف جديد لجدول بنود الفاتورة"""
        logger.debug("add_bill_row: بدأت")
        try:
            row = self.items_table.rowCount()
            logger.debug(f"add_bill_row: عدد الصفوف الحالي = {row}")
            self.items_table.insertRow(row)
            logger.debug("add_bill_row: تم إدراج الصف")

            material_combo = SearchableMaterialCombo(
                load_func=self._load_materials_for_combo,
                add_dialog_func=self._add_material_dialog,
                table_widget=self.items_table,
                current_row=row,
                on_duplicate_check=self._check_material_duplicate
            )
            material_combo.value_changed.connect(lambda mid, r=row: self._on_material_selected(r, mid))
            logger.debug("add_bill_row: تم إنشاء material_combo")

            qty_item = QTableWidgetItem("0")
            qty_item.setFlags(qty_item.flags() | Qt.ItemIsEditable)
            logger.debug("add_bill_row: تم إنشاء qty_item")

            price_item = QTableWidgetItem("0")
            price_item.setFlags(price_item.flags() | Qt.ItemIsEditable)
            logger.debug("add_bill_row: تم إنشاء price_item")

            total_item = QTableWidgetItem("0")
            total_item.setFlags(total_item.flags() | Qt.ItemIsEditable)
            logger.debug("add_bill_row: تم إنشاء total_item")

            delete_btn = QPushButton()
            delete_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon))
            delete_btn.setFixedWidth(40)
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #c0392b; }
            """)
            delete_btn.clicked.connect(lambda _, btn=delete_btn: self._remove_bill_row(btn))
            logger.debug("add_bill_row: تم إنشاء delete_btn")

            self.items_table.blockSignals(True)
            try:
                self.items_table.setCellWidget(row, 0, material_combo)
                logger.debug("add_bill_row: تم وضع material_combo في العمود 0")
                self.items_table.setItem(row, 1, qty_item)
                self.items_table.setItem(row, 2, price_item)
                self.items_table.setItem(row, 3, total_item)
                self.items_table.setCellWidget(row, 4, delete_btn)
                logger.debug("add_bill_row: تم تعبئة جميع الخلايا")
            finally:
                self.items_table.blockSignals(False)

            logger.debug("add_bill_row: الانتهاء بنجاح")
        except Exception as e:
            logger.error(f"add_bill_row خطأ: {e}", exc_info=True)
            raise

    def _remove_bill_row(self, btn):
        """حذف صف من جدول بنود الفاتورة بناءً على زر الحذف"""
        for row in range(self.items_table.rowCount()):
            if self.items_table.cellWidget(row, 4) == btn:
                material_widget = self.items_table.cellWidget(row, 0)
                current_value = getattr(material_widget, 'current_value', None)
                qty_item = self.items_table.item(row, 1)
                price_item = self.items_table.item(row, 2)

                qty_text = qty_item.text().strip() if qty_item else "0"
                price_text = price_item.text().strip() if price_item else "0"

                try:
                    qty = float(qty_text) if qty_text else 0
                except ValueError:
                    qty = 0
                try:
                    price = float(price_text) if price_text else 0
                except ValueError:
                    price = 0

                has_data = current_value is not None or qty > 0 or price > 0

                if has_data:
                    material_name = ""
                    if current_value is not None and hasattr(material_widget, '_all_items'):
                        for item in getattr(material_widget, '_all_items', []):
                            if item.get('id') == current_value:
                                material_name = item.get('name', '')
                                break
                    if material_name:
                        msg = f"هل أنت متأكد من حذف صف [{material_name}]؟"
                    else:
                        msg = "هل أنت متأكد من حذف هذا الصف؟"
                    reply = QMessageBox.question(
                        self, "تأكيد الحذف",
                        msg,
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if reply != QMessageBox.Yes:
                        return

                self.items_table.removeRow(row)
                self.update_bill_total()
                return

    def calculate_row_total(self, row, column):
        """حساب المبلغ الإجمالي للبند تلقائياً بالاتجاهين"""
        logger.debug(f"calculate_row_total: row={row}, column={column}")
        if row >= self.items_table.rowCount():
            return
        if column not in (1, 2, 3):
            return
        try:
            qty_item = self.items_table.item(row, 1)
            price_item = self.items_table.item(row, 2)
            total_item = self.items_table.item(row, 3)
            if not (qty_item and price_item and total_item):
                return

            qty_text = qty_item.text().strip()
            qty = float(qty_text) if qty_text else 0

            if column in (1, 2):
                price_text = price_item.text().strip()
                price = float(price_text) if price_text else 0
                total = qty * price
                self.items_table.blockSignals(True)
                try:
                    total_item.setText(str(total))
                finally:
                    self.items_table.blockSignals(False)
                logger.debug(f"calculate_row_total: المجموع = {total}")
            elif column == 3:
                if qty <= 0 or not qty_text:
                    logger.debug("calculate_row_total: كمية فارغة أو صفر، لا يمكن حساب السعر")
                    return
                total_text = total_item.text().strip()
                if not total_text:
                    return
                total = float(total_text)
                price = total / qty
                price_rounded = round(price, 2)
                self.items_table.blockSignals(True)
                try:
                    price_item.setText(str(price_rounded))
                finally:
                    self.items_table.blockSignals(False)
                logger.debug(f"calculate_row_total: السعر المحسوب = {price_rounded}")

            self.update_bill_total()
        except ValueError:
            logger.debug("calculate_row_total: ValueError")
            pass

    def update_bill_total(self):
        """تحديث المبلغ الإجمالي للفاتورة"""
        logger.debug("update_bill_total: بدأت")
        total = 0
        for row in range(self.items_table.rowCount()):
            item = self.items_table.item(row, 3)
            if item:
                try:
                    total += float(item.text()) if item.text() else 0
                except ValueError:
                    pass
        self.total_amount_label.setText(str(total))
        logger.debug(f"update_bill_total: المجموع النهائي = {total}")

    def save_purchase_bill(self):
        """حفظ فاتورة الشراء"""
        supplier_id = self.supplier_combo.current_value
        if not supplier_id:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار المورد")
            return

        if self.items_table.rowCount() == 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء إضافة بند واحد على الأقل")
            return

        bill_date = self.date_input.date().toString("yyyy-MM-dd")
        bill_date = bill_date.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        payment_mode = self.payment_combo.currentText()

        normalized_date = str(bill_date).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        normalized_date = normalized_date.split(" ")[0] if " " in normalized_date else normalized_date

        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            next_date = (datetime.strptime(normalized_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            cursor.execute("SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (normalized_date, next_date))
            day_row = cursor.fetchone()
            if day_row and day_row[0]:
                QMessageBox.warning(self, "خطأ", "لا يمكن تسجيل فاتورة شراء في يومية مُغلقة. يرجى إعادة فتح اليومية أولًا من شاشة النقدية.")
                return
        except Exception:
            pass
        finally:
            if conn:
                conn.close()

        items = []
        total_amount = 0
        for row in range(self.items_table.rowCount()):
            widget = self.items_table.cellWidget(row, 0)
            if isinstance(widget, QComboBox):
                material_id = widget.currentData()
            else:
                material_id = widget.current_value
            qty_item = self.items_table.item(row, 1)
            price_item = self.items_table.item(row, 2)
            total_item = self.items_table.item(row, 3)

            if not material_id:
                QMessageBox.warning(self, "تنبيه", f"الرجاء اختيار المادة في الصف {row + 1}")
                return

            try:
                qty = float(qty_item.text()) if qty_item and qty_item.text() else 0
                price = float(price_item.text()) if price_item and price_item.text() else 0
                line_total = float(total_item.text()) if total_item and total_item.text() else 0
            except ValueError:
                QMessageBox.warning(self, "تنبيه", f"قيمة غير صالحة في الصف {row + 1}")
                return

            if qty <= 0 or price <= 0:
                QMessageBox.warning(self, "تنبيه", f"الكمية والسعر يجب أن يكونا أكبر من صفر في الصف {row + 1}")
                return

            items.append({
                "material_id": material_id,
                "qty": qty,
                "price": price,
                "total": line_total
            })
            total_amount += line_total

        if not items:
            QMessageBox.warning(self, "تنبيه", "الرجاء إدخال بنود صالحة")
            return

        if payment_mode == "جزئي (كاش + دين)":
            cash_txt = self.cash_amount_edit.text().strip()
            if not cash_txt:
                QMessageBox.warning(self, "تنبيه", "الرجاء إدخال المبلغ النقدي")
                return
            try:
                cash_amount = float(cash_txt)
            except ValueError:
                QMessageBox.warning(self, "تنبيه", "قيمة غير صالحة للمبلغ النقدي")
                return
            if cash_amount < 0:
                QMessageBox.warning(self, "تنبيه", "المبلغ النقدي يجب أن يكون أكبر من صفر")
                return
            if cash_amount > total_amount:
                QMessageBox.warning(self, "تنبيه", "المبلغ النقدي لا يمكن أن يتجاوز إجمالي الفاتورة")
                return
            is_debt = True
            cash_payment = cash_amount
        elif payment_mode == "دين (آجل)":
            is_debt = True
            cash_payment = 0.0
        else:
            is_debt = False
            cash_payment = 0.0

        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            cursor.execute("""
                SELECT العملة FROM الديون WHERE معرف = ?
            """, (supplier_id,))
            currency_row = cursor.fetchone()
            supplier_currency = currency_row[0] if currency_row else 'ليرة_سورية'

            cursor.execute("""
                SELECT اسم_الطرف FROM الديون WHERE معرف = ?
            """, (supplier_id,))
            supplier_name_row = cursor.fetchone()
            supplier_name = supplier_name_row[0] if supplier_name_row else ""

            cursor.execute("""
                INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة)
                VALUES (?, ?, ?, ?, ?)
            """, (bill_date, supplier_id, supplier_name, total_amount, supplier_currency))
            invoice_id = cursor.lastrowid

            material_ids = [item["material_id"] for item in items]
            placeholders = ",".join("?" * len(material_ids))
            cursor.execute(
                f"SELECT معرف_المادة_الفرعية, الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية IN ({placeholders})",
                material_ids
            )
            stock_map = {row[0]: row[1] for row in cursor.fetchall()}

            price_updates = []

            for item in items:
                cursor.execute("""
                    INSERT INTO تفاصيل_الشراء (معرف_الفاتورة, معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي)
                    VALUES (?, ?, ?, ?, ?)
                """, (invoice_id, item["material_id"], item["qty"], item["price"], item["total"]))

                current_qty = stock_map.get(item["material_id"], 0)
                new_qty = current_qty + item["qty"]

                cursor.execute("""
                    INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (item["material_id"], new_qty))

                cursor.execute("""
                    INSERT INTO تحركات_المخزون
                    (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, معرف_الفاتورة, ملاحظات)
                    VALUES (?, 'شراء', ?, ?, ?, ?)
                """, (item["material_id"], item["qty"], new_qty, invoice_id, f"فاتورة شراء #{invoice_id}"))

                price_updates.append((item["price"], item["material_id"]))

            cursor.executemany(
                "UPDATE المواد_الفرعية SET سعر_الشراء_الأخير = ? WHERE معرف = ?",
                price_updates
            )

            debt_id = None

            if payment_mode == "نقدي من الدرج":
                cursor.execute("""
                    INSERT INTO السحوبات (التاريخ, المبلغ, الوصف, العملة, ملاحظات)
                    VALUES (?, ?, ?, ?, ?)
                """, (now_str(), total_amount, f"شراء - {supplier_name}", supplier_currency, f"فاتورة #{invoice_id} - نقدي من الدرج"))
            elif payment_mode == "نقدي من الخزنة":
                cursor.execute("SELECT الرصيد_بعد_الحركة FROM الخزنة ORDER BY معرف DESC LIMIT 1")
                vault_row = cursor.fetchone()
                vault_balance = vault_row[0] if vault_row else 0
                if vault_balance < total_amount:
                    conn.rollback()
                    QMessageBox.warning(self, "خطأ", f"رصيد الخزنة ({fmt(vault_balance)}) لا يكفي للشراء ({fmt(total_amount)})")
                    return
                cursor.execute("""
                    INSERT INTO الخزنة (التاريخ, البيان, سحب, الرصيد_بعد_الحركة, ملاحظات)
                    VALUES (?, ?, ?, ?, ?)
                """, (now_str(), f"شراء - {supplier_name}", total_amount, vault_balance - total_amount, f"فاتورة #{invoice_id}"))
                cursor.execute("""
                    INSERT INTO تحويلات_الصندوق (التاريخ, من_حساب, إلى_حساب, المبلغ, ملاحظات)
                    VALUES (?, 'الخزنة', 'الخارجي', ?, ?)
                """, (now_str(), total_amount, f"شراء من مورد - {supplier_name}"))
            elif payment_mode == "جزئي (كاش + دين)":
                debt_amount = total_amount - cash_payment
                cash_source = getattr(self, 'partial_payment_source_combo', None)
                cash_source_text = cash_source.currentText() if cash_source else "من الدرج"
                if cash_payment > 0:
                    if cash_source_text == "من الخزنة":
                        cursor.execute("SELECT الرصيد_بعد_الحركة FROM الخزنة ORDER BY معرف DESC LIMIT 1")
                        vault_row = cursor.fetchone()
                        vault_balance = vault_row[0] if vault_row else 0
                        if vault_balance < cash_payment:
                            conn.rollback()
                            QMessageBox.warning(self, "خطأ", f"رصيد الخزنة ({fmt(vault_balance)}) لا يكفي")
                            return
                        cursor.execute("""
                            INSERT INTO الخزنة (التاريخ, البيان, سحب, الرصيد_بعد_الحركة, ملاحظات)
                    VALUES (?, ?, ?, ?, ?)
                """, (now_str(), f"شراء جزئي - {supplier_name}", cash_payment, vault_balance - cash_payment, f"فاتورة #{invoice_id}"))
                        cursor.execute("""
                            INSERT INTO تحويلات_الصندوق (التاريخ, من_حساب, إلى_حساب, المبلغ, ملاحظات)
                            VALUES (?, 'الخزنة', 'الخارجي', ?, ?)
                        """, (now_str(), cash_payment, f"شراء جزئي من مورد - {supplier_name}"))
                    else:
                        cursor.execute("""
                            INSERT INTO السحوبات (التاريخ, المبلغ, الوصف, العملة, ملاحظات)
                    VALUES (?, ?, ?, ?, ?)
                """, (now_str(), cash_payment, f"شراء جزئي - {supplier_name}", supplier_currency, f"فاتورة #{invoice_id} - نقدي من الدرج"))
                if debt_amount > 0:
                    cursor.execute("""
                        SELECT معرف, العملة FROM الديون WHERE معرف = ?
                    """, (supplier_id,))
                    debt_row = cursor.fetchone()
                    if debt_row:
                        debt_id = debt_row[0]
                        cursor.execute("""
                            UPDATE الديون
                            SET المبلغ_الإجمالي = المبلغ_الإجمالي + ?,
                                الرصيد = الرصيد + ?,
                                تاريخ_التحديث = CURRENT_TIMESTAMP
                            WHERE معرف = ?
                        """, (debt_amount, debt_amount, debt_id))
                    else:
                        cursor.execute("""
                            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
                            VALUES (?, 'مورد', ?, ?, 0, ?, 'نشط')
                        """, (supplier_name, supplier_currency, debt_amount, debt_amount))
                        debt_id = cursor.lastrowid
                    cursor.execute("""
                        INSERT INTO تحركات_الديون (معرف_الدين, المبلغ, نوع_الحركة, ملاحظات)
                        VALUES (?, ?, 'إضافة', ?)
                    """, (debt_id, debt_amount, f"فاتورة شراء #{invoice_id} - جزئي"))
            elif is_debt:
                cursor.execute("""
                    SELECT معرف, العملة FROM الديون WHERE معرف = ?
                """, (supplier_id,))
                debt_row = cursor.fetchone()

                if debt_row:
                    debt_id = debt_row[0]
                    cursor.execute("""
                        UPDATE الديون
                        SET المبلغ_الإجمالي = المبلغ_الإجمالي + ?,
                            الرصيد = الرصيد + ?,
                            تاريخ_التحديث = CURRENT_TIMESTAMP
                        WHERE معرف = ?
                    """, (total_amount, total_amount, debt_id))
                else:
                    cursor.execute("""
                        INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
                        VALUES (?, 'مورد', ?, ?, 0, ?, 'نشط')
                    """, (supplier_name, supplier_currency, total_amount, total_amount))
                    debt_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO تحركات_الديون (معرف_الدين, المبلغ, نوع_الحركة, ملاحظات)
                    VALUES (?, ?, 'إضافة', ?)
                """, (debt_id, total_amount, f"فاتورة شراء #{invoice_id}"))

            conn.commit()
            QMessageBox.information(self, "نجاح", f"تم حفظ الفاتورة #{invoice_id} بنجاح!")

            try:
                main_window = self.window()
                if isinstance(main_window, QMainWindow):
                    main_window.show_status(f"تم حفظ فاتورة الشراء رقم {invoice_id} بنجاح", "success")
            except Exception:
                pass

            self.items_table.setRowCount(0)
            self.total_amount_label.setText("0")
            self.payment_combo.setCurrentIndex(0)
            self.cash_amount_edit.clear()
            self.cash_amount_edit.setVisible(False)
            self.load_inventory_display()

            app_events.emit_data_changed("purchases")
            app_events.emit_data_changed("materials")
            if debt_id:
                app_events.emit_data_changed("creditors")

        except Exception as e:
            logger.error(str(e))
            if conn:
                conn.rollback()
            QMessageBox.critical(self, "خطأ", f"فشل حفظ الفاتورة:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _load_purchase_history(self):
        """تحميل قائمة فواتير الشراء السابقة"""
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT معرف, التاريخ, اسم_المورد, المبلغ_الإجمالي, العملة
                FROM فواتير_الشراء
                ORDER BY التاريخ DESC
                LIMIT 200
            """)  # TODO: add date filter UI if list grows
            data = cursor.fetchall()

            headers = ["معرف", "التاريخ", "المورد", "المبلغ الإجمالي", "العملة"]
            rows = [list(row) for row in data]

            self.purchase_history_table.set_data(headers, rows, id_column_index=0)
            self.purchase_history_table.table.setColumnHidden(0, True)
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل فواتير الشراء:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _on_purchase_history_double_click(self, invoice_id):
        """فتح تفاصيل الفاتورة عند النقر المزدوج"""
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT التاريخ, اسم_المورد, المبلغ_الإجمالي, العملة
                FROM فواتير_الشراء WHERE معرف = ?
            """, (invoice_id,))
            invoice = cursor.fetchone()
            if not invoice:
                return

            date, supplier, total, currency = invoice
            detail_data = {
                "رقم الفاتورة": invoice_id,
                "التاريخ": date,
                "المورد": supplier,
                "المبلغ الإجمالي": total,
                "العملة": currency,
            }

            cursor.execute("""
                SELECT م.الاسم, d.الكمية, d.سعر_الوحدة, d.المبلغ_الإجمالي
                FROM تفاصيل_الشراء d
                JOIN المواد_الفرعية م ON d.معرف_المادة_الفرعية = م.معرف
                WHERE d.معرف_الفاتورة = ?
            """, (invoice_id,))
            items = cursor.fetchall()

            related_headers = ["المادة", "الكمية", "سعر الوحدة", "المبلغ الإجمالي"]
            related_rows = [list(row) for row in items]

            dialog = EntityDetailDialog(
                f"تفاصيل فاتورة الشراء #{invoice_id}",
                detail_data=detail_data,
                related_rows=related_rows,
                related_headers=related_headers,
            )
            dialog.exec_()
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل التفاصيل:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _on_purchase_history_edit(self, invoice_id):
        """تعديل فاتورة شراء (حذف إجباري ثم فتح نموذج جديد معبأ بالبيانات القديمة)"""
        saved_data = None
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة, التاريخ
                FROM فواتير_الشراء WHERE معرف = ?
            """, (invoice_id,))
            invoice_row = cursor.fetchone()
            if invoice_row:
                cursor.execute("""
                    SELECT معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي
                    FROM تفاصيل_الشراء WHERE معرف_الفاتورة = ?
                """, (invoice_id,))
                items = cursor.fetchall()
                saved_data = {
                    'supplier_id': invoice_row[0],
                    'supplier_name': invoice_row[1],
                    'total': invoice_row[2],
                    'currency': invoice_row[3],
                    'date': invoice_row[4],
                    'items': items
                }
        except Exception as e:
            logger.error(f"خطأ في تحميل بيانات الفاتورة قبل التعديل: {e}")
        finally:
            if conn:
                conn.close()

        try:
            self._force_delete_purchase_invoice(invoice_id)
            app_events.emit_data_changed("purchases")
            app_events.emit_data_changed("materials")

            if saved_data:
                invoice_date = saved_data.get('date')
                if invoice_date:
                    normalized_date = str(invoice_date).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
                    normalized_date = normalized_date.split(" ")[0] if " " in normalized_date else normalized_date
                    conn2 = None
                    try:
                        conn2 = get_conn()
                        cursor2 = conn2.cursor()
                        next_date = (datetime.strptime(normalized_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                        cursor2.execute("SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (normalized_date, next_date))
                        day_row = cursor2.fetchone()
                        if day_row and day_row[0]:
                            QMessageBox.warning(self, "تنبيه", "تنبيه: اليومية لتاريخ هذه الفاتورة مغلقة. سيتم التعديل مع تحديث الحسابات، لكن يُنصح بمراجعة التقارير.")
                    except Exception:
                        pass
                    finally:
                        if conn2:
                            conn2.close()

            QMessageBox.information(self, "تم", "تم حذف الفاتورة القديمة بنجاح. يمكنك الآن إدخال الفاتورة المعدّلة.")

            if saved_data:
                self._prefill_purchase_form(saved_data=saved_data)
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تعديل الفاتورة:\n{str(e)}")

    def _on_purchase_history_delete(self, invoice_id):
        """حذف فاتورة شراء مع تأكيد"""
        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل أنت متأكد من حذف فاتورة الشراء #{invoice_id}؟\n"
            "لا يمكن التراجع عن هذا الإجراء.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._force_delete_purchase_invoice(invoice_id)
            QMessageBox.information(self, "نجاح", f"تم حذف الفاتورة #{invoice_id} بنجاح")

            try:
                main_window = self.window()
                if isinstance(main_window, QMainWindow):
                    main_window.show_status("تم حذف الفاتورة بنجاح", "success")
            except Exception:
                pass

            self._load_purchase_history()
            self.load_inventory_display()
            app_events.emit_data_changed("purchases")
            app_events.emit_data_changed("materials")
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل حذف الفاتورة:\n{str(e)}")

    def _force_delete_purchase_invoice(self, invoice_id):
        """حذف إجباري لفاتورة الشراء مع إعادة حساب كاملة بدون شروط منعية"""
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            cursor.execute("""
                SELECT التاريخ, المبلغ_الإجمالي, العملة, اسم_المورد, معرف_المورد
                FROM فواتير_الشراء WHERE معرف = ?
            """, (invoice_id,))
            invoice = cursor.fetchone()
            if not invoice:
                conn.rollback()
                raise Exception("الفاتورة غير موجودة")

            invoice_date, total_amount, currency, supplier_name, supplier_id = invoice

            cursor.execute("""
                SELECT معرف_المادة_الفرعية, الكمية, سعر_الوحدة
                FROM تفاصيل_الشراء WHERE معرف_الفاتورة = ?
            """, (invoice_id,))
            items = cursor.fetchall()
            if not items:
                conn.rollback()
                raise Exception("لا توجد بنود في الفاتورة")

            cursor.execute("""
                DELETE FROM تحركات_المخزون WHERE معرف_الفاتورة = ?
            """, (invoice_id,))

            for material_id, qty, price in items:
                cursor.execute("""
                    SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?
                """, (material_id,))
                row = cursor.fetchone()
                current_qty = row[0] if row else 0

                new_qty = current_qty - qty
                if new_qty < 0:
                    new_qty = 0
                    stock_note = f"إلغاء فاتورة شراء #{invoice_id} - كمية سالبة تم ضبطها على 0"
                else:
                    stock_note = f"إلغاء فاتورة شراء #{invoice_id}"

                cursor.execute("""
                    INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (material_id, new_qty))

                cursor.execute("""
                    INSERT INTO تحركات_المخزون
                    (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, معرف_الفاتورة, ملاحظات)
                    VALUES (?, 'تعديل_يدوي', ?, ?, NULL, ?)
                """, (material_id, qty, new_qty, stock_note))

                cursor.execute("""
                    UPDATE المواد_الفرعية SET سعر_الشراء_الأخير = ? WHERE معرف = ?
                """, (price, material_id))

            debt_id = None
            if supplier_id:
                cursor.execute("""
                    SELECT معرف FROM الديون WHERE معرف = ?
                """, (supplier_id,))
                debt_row = cursor.fetchone()
                debt_id = debt_row[0] if debt_row else None
                if debt_id is None and supplier_id:
                    debt_id = supplier_id

                if debt_id:
                    cursor.execute("""
                        SELECT المبلغ_الإجمالي, الرصيد FROM الديون WHERE معرف = ?
                    """, (debt_id,))
                    debt_info = cursor.fetchone()
                    if debt_info:
                        current_total, current_balance = debt_info
                        new_total = max(0, current_total - total_amount)
                        new_balance = max(0, current_balance - total_amount)
                        cursor.execute("""
                            UPDATE الديون
                            SET المبلغ_الإجمالي = ?,
                                الرصيد = ?,
                                تاريخ_التحديث = CURRENT_TIMESTAMP
                            WHERE معرف = ?
                        """, (new_total, new_balance, debt_id))

            cursor.execute("""
                DELETE FROM تحركات_الديون WHERE ملاحظات LIKE ? AND نوع_الحركة = 'إضافة'
            """, (f"فاتورة شراء #{invoice_id}%",))

            cursor.execute("""
                DELETE FROM السحوبات WHERE ملاحظات LIKE ?
            """, (f"فاتورة #{invoice_id}%",))

            cursor.execute("""
                SELECT معرف, إيداع, سحب FROM الخزنة WHERE ملاحظات LIKE ? ORDER BY معرف ASC
            """, (f"فاتورة #{invoice_id}%",))
            vault_records = cursor.fetchall()
            for v_id, v_deposit, v_withdraw in vault_records:
                v_delta = (v_deposit or 0) - (v_withdraw or 0)
                cursor.execute("DELETE FROM الخزنة WHERE معرف = ?", (v_id,))
                if v_delta != 0:
                    cursor.execute("""
                        UPDATE الخزنة SET الرصيد_بعد_الحركة = الرصيد_بعد_الحركة - ?
                        WHERE معرف > ?
                    """, (v_delta, v_id))

            cursor.execute("""
                DELETE FROM تحويلات_الصندوق WHERE ملاحظات LIKE ?
            """, (f"فاتورة #{invoice_id}%",))

            cursor.execute("""
                DELETE FROM تفاصيل_الشراء WHERE معرف_الفاتورة = ?
            """, (invoice_id,))
            cursor.execute("""
                DELETE FROM فواتير_الشراء WHERE معرف = ?
            """, (invoice_id,))

            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise

    def _prefill_purchase_form(self, invoice_id=None, saved_data=None):
        """تعبئة نموذج الفاتورة ببيانات الفاتورة القديمة للتعديل"""
        conn = None
        try:
            if saved_data is not None:
                supplier_id_val = saved_data.get('supplier_id')
                supplier_name_val = saved_data.get('supplier_name')
                total = saved_data.get('total')
                currency = saved_data.get('currency')
                items = saved_data.get('items', [])
            else:
                conn = get_conn()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة
                    FROM فواتير_الشراء WHERE معرف = ?
                """, (invoice_id,))
                invoice = cursor.fetchone()
                if not invoice:
                    return

                supplier_id_val, supplier_name_val, total, currency = invoice

                cursor.execute("""
                    SELECT معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي
                    FROM تفاصيل_الشراء WHERE معرف_الفاتورة = ?
                """, (invoice_id,))
                items = cursor.fetchall()

            self.supplier_combo.setCurrentValue(supplier_id_val)
            self.total_amount_label.setText(str(total))

            self.items_table.setRowCount(0)
            for material_id, qty, price, line_total in items:
                row = self.items_table.rowCount()
                self.items_table.insertRow(row)

                material_combo = SearchableMaterialCombo(
                    load_func=self._load_materials_for_combo,
                    add_dialog_func=self._add_material_dialog,
                    table_widget=self.items_table,
                    current_row=row,
                    on_duplicate_check=self._check_material_duplicate
                )
                material_combo.value_changed.connect(lambda mid, r=row: self._on_material_selected(r, mid))
                material_combo.setCurrentValue(material_id)

                qty_item = QTableWidgetItem(str(qty))
                qty_item.setFlags(qty_item.flags() | Qt.ItemIsEditable)

                price_item = QTableWidgetItem(str(price))
                price_item.setFlags(price_item.flags() | Qt.ItemIsEditable)

                total_item = QTableWidgetItem(str(line_total))
                total_item.setFlags(total_item.flags() | Qt.ItemIsEditable)

                delete_btn = QPushButton()
                delete_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon))
                delete_btn.setFixedWidth(40)
                delete_btn.setCursor(Qt.PointingHandCursor)
                delete_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-size: 12px;
                    }
                    QPushButton:hover { background-color: #c0392b; }
                """)
                delete_btn.clicked.connect(lambda _, btn=delete_btn: self._remove_bill_row(btn))

                self.items_table.setCellWidget(row, 0, material_combo)
                self.items_table.setItem(row, 1, qty_item)
                self.items_table.setItem(row, 2, price_item)
                self.items_table.setItem(row, 3, total_item)
                self.items_table.setCellWidget(row, 4, delete_btn)

            self.update_bill_total()
            QMessageBox.information(self, "تعديل", "تم تعبئة بيانات الفاتورة القديمة. قم بالتعديل ثم اضغط حفظ.")
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تعبئة الفاتورة:\n{str(e)}")
        finally:
            if conn:
                conn.close()
