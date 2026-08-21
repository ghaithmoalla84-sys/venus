# Path: D:\acc\venus\ui\screens\sales.py
# -*- coding: utf-8 -*-
"""
شاشة المبيعات اليومية - Venus Coffee
تسجيل وعرض مبيعات المتجر حسب المجموعات
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime, timedelta

from venus.core.database import get_conn
from venus.core.repositories import SalesRepository, GroupsRepository
from venus.core.events import app_events
from venus.ui.widgets.entity_detail_dialog import EntityDetailDialog
from venus.ui.widgets.searchable_table import SearchableTable
from venus.ui.widgets.combo_quick_add import ComboWithQuickAdd
from venus.ui.styles import (
    Colors, FontSizes, Spacing, BorderRadius,
    title_label_style, group_box_style, table_style,
    primary_button_style, success_button_style, input_style, combo_style, date_edit_style,
    status_bar_style
)
from venus.utils.currency import fmt, fmt_syp, round_currency
from venus.utils.logger import setup_logger
logger = setup_logger()


class NumericDelegate(QStyledItemDelegate):
    """ديلجيت لتقييد الإدخال بالأرقام فقط في الجداول"""
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setValidator(QDoubleValidator())
        return editor


class EditSaleDialog(QDialog):
    """حوار تعديل مبيعة مسجلة"""

    def __init__(self, amount, notes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تعديل المبيعة")
        self.setLayoutDirection(Qt.RightToLeft)
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.amount_edit = QLineEdit(str(amount))
        self.amount_edit.setValidator(QDoubleValidator(0, 10000000, 2))
        self.amount_edit.setStyleSheet(input_style(focus_color=Colors.FOCUS_GREEN))

        self.notes_edit = QLineEdit(notes or "")
        self.notes_edit.setStyleSheet(input_style(focus_color=Colors.FOCUS_GREEN))

        layout.addRow("المبلغ الإجمالي:", self.amount_edit)
        layout.addRow("ملاحظات:", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setLayoutDirection(Qt.RightToLeft)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        btn_ok = buttons.button(QDialogButtonBox.Ok)
        btn_ok.setAutoDefault(False)
        btn_ok.setDefault(False)
        self.notes_edit.returnPressed.connect(btn_ok.click)
        layout.addRow(buttons)

        self.amount_edit.setFocus()

    def get_data(self):
        try:
            amount = float(self.amount_edit.text())
        except ValueError:
            return None
        return {"amount": amount, "notes": self.notes_edit.text().strip()}


class SalesScreen(QWidget):
    """شاشة المبيعات اليومية"""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.sales_repo = SalesRepository()
        self.groups_repo = GroupsRepository()
        self._current_sales = []
        self._groups_data = []
        self.init_ui()
        self.load_data()
        app_events.data_changed.connect(self._on_app_data_changed)

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("🛒 المبيعات اليومية")
        title.setWordWrap(True)
        title.setStyleSheet(title_label_style(font_size=FontSizes.XL3, color=Colors.DARK))
        title.setAlignment(Qt.AlignRight)
        main_layout.addWidget(title)

        entry_group = QGroupBox("📝 تسجيل مبيعات اليوم")
        entry_group.setStyleSheet(group_box_style(Colors.SUCCESS))
        entry_layout = QVBoxLayout()
        entry_layout.setSpacing(Spacing.MD)
        entry_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        date_layout = QHBoxLayout()
        date_layout.setContentsMargins(0, 0, 0, 0)

        date_label = QLabel("التاريخ:")
        date_label.setWordWrap(True)
        date_label.setStyleSheet(f"font-size: {FontSizes.SM}; color: {Colors.DARK};")
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setStyleSheet(date_edit_style(focus_color=Colors.FOCUS_GREEN))

        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_input)
        date_layout.addStretch()
        entry_layout.addLayout(date_layout)

        self.entry_table = QTableWidget()
        self.entry_table.setColumnCount(4)
        self.entry_table.setHorizontalHeaderLabels([
            "المجموعة", "المبلغ الإجمالي", "ملاحظات", "حذف الصف"
        ])
        self.entry_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.entry_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.entry_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.entry_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.entry_table.setColumnWidth(3, 60)
        self.entry_table.horizontalHeader().setMinimumSectionSize(60)
        self.entry_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.entry_table.setStyleSheet(table_style(Colors.SUCCESS))
        self.entry_table.setAlternatingRowColors(True)
        self.entry_table.setItemDelegateForColumn(1, NumericDelegate())
        entry_layout.addWidget(self.entry_table)
        self.entry_table.setMinimumHeight(80)
        self.entry_table.verticalHeader().setVisible(False)
        self.entry_table.setSelectionBehavior(QTableWidget.SelectRows)

        entry_buttons_layout = QHBoxLayout()
        entry_buttons_layout.setContentsMargins(0, 0, 0, 0)

        add_row_btn = QPushButton("إضافة صف")
        add_row_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileIcon))
        add_row_btn.setIconSize(QSize(16, 16))
        add_row_btn.setMaximumHeight(32)
        add_row_btn.setCursor(Qt.PointingHandCursor)
        add_row_btn.setStyleSheet(success_button_style())
        add_row_btn.clicked.connect(self.add_entry_row)

        save_btn = QPushButton("حفظ المبيعات")
        save_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_btn.setIconSize(QSize(16, 16))
        save_btn.setMaximumHeight(32)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(success_button_style())
        save_btn.clicked.connect(self.save_sales)

        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        save_shortcut.activated.connect(self.save_sales)

        undo_btn = QPushButton("↩️ تراجع عن آخر عملية")
        undo_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_ArrowBack))
        undo_btn.setIconSize(QSize(16, 16))
        undo_btn.setMaximumHeight(32)
        undo_btn.setCursor(Qt.PointingHandCursor)
        undo_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        undo_btn.clicked.connect(self.undo_last_sale)

        entry_buttons_layout.addWidget(add_row_btn)
        entry_buttons_layout.addWidget(save_btn)
        entry_buttons_layout.addWidget(undo_btn)
        entry_buttons_layout.addStretch()
        entry_layout.addLayout(entry_buttons_layout)

        entry_group.setLayout(entry_layout)
        entry_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        display_group = QGroupBox("📋 المبيعات المسجلة سابقاً")
        display_group.setStyleSheet(group_box_style(Colors.PRIMARY))
        display_layout = QVBoxLayout()
        display_layout.setSpacing(Spacing.MD)
        display_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        display_header_layout = QHBoxLayout()
        display_header_layout.setContentsMargins(0, 0, 0, 0)

        view_date_label = QLabel("اختر التاريخ:")
        view_date_label.setWordWrap(True)
        view_date_label.setStyleSheet(f"font-size: {FontSizes.SM}; color: {Colors.DARK};")
        self.view_date_input = QDateEdit()
        self.view_date_input.setDate(QDate.currentDate())
        self.view_date_input.setCalendarPopup(True)
        self.view_date_input.setStyleSheet(date_edit_style(focus_color=Colors.FOCUS_BLUE))

        view_btn = QPushButton("عرض")
        view_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        view_btn.setIconSize(QSize(16, 16))
        view_btn.setMaximumHeight(32)
        view_btn.setCursor(Qt.PointingHandCursor)
        view_btn.setStyleSheet(primary_button_style(
            bg=Colors.PRIMARY, hover=Colors.PRIMARY_HOVER,
            font_size=FontSizes.MD, padding="6px 10px"
        ))
        view_btn.clicked.connect(self.view_previous_sales)

        display_header_layout.addWidget(view_date_label)
        display_header_layout.addWidget(self.view_date_input)
        display_header_layout.addWidget(view_btn)
        display_header_layout.addStretch()
        display_layout.addLayout(display_header_layout)

        self.display_table = SearchableTable()
        self.display_table.edit_requested.connect(self._on_edit_requested)
        self.display_table.delete_requested.connect(self._on_delete_requested)
        self.display_table.row_double_clicked.connect(self._on_sale_double_clicked)
        display_layout.addWidget(self.display_table)
        self.display_table.setMinimumHeight(150)

        self.total_label = QLabel("إجمالي مبيعات اليوم: 0")
        self.total_label.setWordWrap(True)
        self.total_label.setStyleSheet(f"""
            font-size: {FontSizes.LG};
            font-weight: bold;
            color: {Colors.DARK};
            padding: 6px;
            background-color: #eaf2f8;
            border-radius: {BorderRadius.MD};
        """)
        self.total_label.setAlignment(Qt.AlignRight)
        display_layout.addWidget(self.total_label)

        display_group.setLayout(display_layout)
        display_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        sections_layout = QHBoxLayout()
        sections_layout.setSpacing(12)
        sections_layout.addWidget(entry_group, stretch=1)
        sections_layout.addWidget(display_group, stretch=1)
        main_layout.addLayout(sections_layout, stretch=1)

    def load_data(self):
        """تحميل البيانات الأولية للشاشة"""
        self.load_groups()
        self._populate_entry_table()
        self.view_previous_sales()

    def load_groups(self):
        """تحميل قائمة المجموعات من جدول المجموعات"""
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT معرف, الاسم FROM المجموعات WHERE الاسم != 'مبيعات غير مسجلة' ORDER BY الترتيب, الاسم")
            groups = cursor.fetchall()
            self._groups_data = groups
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل المجموعات:\n{str(e)}")
            self._groups_data = []
        finally:
            conn.close()

    def _on_app_data_changed(self, entity_name):
        if entity_name in {"sales", "groups"}:
            self.load_data()

    def _load_groups_for_combo(self):
        """إرجاع المجموعات بتنسيق (الاسم، المعرف) لمكوّن ComboWithQuickAdd"""
        return [(name, gid) for gid, name in self._groups_data]

    def _quick_add_group(self):
        """حوار إضافة مجموعة سريعة (الاسم فقط)"""
        name, ok = QInputDialog.getText(
            self, "إضافة مجموعة سريعة", "اسم المجموعة:")
        if ok and name.strip():
            try:
                gid = self.groups_repo.create(الاسم=name.strip())
                self.load_groups()
                app_events.emit_data_changed("groups")
                return name.strip()
            except Exception as e:
                logger.error(str(e))
                QMessageBox.critical(self, "خطأ", f"فشل إضافة المجموعة:\n{str(e)}")
        return None

    def _create_entry_row(self, group_id=None):
        """إنشاء صف جديد في جدول إدخال المبيعات"""
        row = self.entry_table.rowCount()
        self.entry_table.insertRow(row)
        current_row_height = self.entry_table.rowHeight(row)
        self.entry_table.setRowHeight(row, int(current_row_height * 1.5))

        group_combo = ComboWithQuickAdd(
            load_func=self._load_groups_for_combo,
            add_dialog_func=self._quick_add_group,
            combo_style="""
                QComboBox {
                    padding: 6px;
                    font-size: 13px;
                    border: 1px solid #bdc3c7;
                    border-radius: 4px;
                    background-color: white;
                }
                QComboBox::drop-down { border: none; width: 25px; }
            """,
            button_style="""
                QPushButton {
                    border: none;
                    background-color: #27ae60;
                    color: white;
                    font-size: 14px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #229954; }
            """,
        )
        if group_id is not None:
            group_combo.setCurrentValue(group_id)

        amount_item = QTableWidgetItem("0")
        amount_item.setFlags(amount_item.flags() | Qt.ItemIsEditable)

        notes_item = QTableWidgetItem("")
        notes_item.setFlags(notes_item.flags() | Qt.ItemIsEditable)

        delete_btn = QPushButton()
        delete_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon))
        delete_btn.setIconSize(QSize(16, 16))
        delete_btn.setFixedWidth(32)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        def make_delete(btn):
            def do_delete():
                for i in range(self.entry_table.rowCount()):
                    if self.entry_table.cellWidget(i, 3) == btn:
                        self.entry_table.removeRow(i)
                        break
            return do_delete

        delete_btn.clicked.connect(make_delete(delete_btn))

        self.entry_table.setCellWidget(row, 0, group_combo)
        self.entry_table.setItem(row, 1, amount_item)
        self.entry_table.setItem(row, 2, notes_item)
        self.entry_table.setCellWidget(row, 3, delete_btn)

    def _populate_entry_table(self):
        """ملء جدول إدخال المبيعات تلقائياً بصف واحد لكل مجموعة موجودة فعلياً"""
        self.entry_table.setRowCount(0)
        for gid, name in self._groups_data:
            self._create_entry_row(group_id=gid)

    def add_entry_row(self):
        """إضافة صف جديد فارغ لجدول إدخال المبيعات"""
        self._create_entry_row()

    def save_sales(self):
        """حفظ جميع صفوف المبيعات كسجلات منفصلة في جدول المبيعات_اليومية"""
        sales_data = []

        for row in range(self.entry_table.rowCount()):
            group_combo = self.entry_table.cellWidget(row, 0)
            group_id = group_combo.current_value

            amount_item = self.entry_table.item(row, 1)
            amount_text = amount_item.text().strip() if amount_item else "0"

            notes_item = self.entry_table.item(row, 2)
            notes_text = notes_item.text().strip() if notes_item else ""

            if group_id is None:
                QMessageBox.warning(
                    self, "تنبيه",
                    f"الرجاء اختيار المجموعة في الصف {row + 1}"
                )
                return

            try:
                amount = float(amount_text) if amount_text else 0.0
            except ValueError:
                QMessageBox.warning(
                    self, "تنبيه",
                    f"قيمة غير صالحة للمبلغ في الصف {row + 1}"
                )
                return

            if amount < 0:
                QMessageBox.warning(
                    self, "تنبيه",
                    f"المبلغ يجب أن يكون أكبر من صفر في الصف {row + 1}"
                )
                return

            if amount == 0:
                continue

            sales_data.append({
                "group_id": group_id,
                "amount": amount,
                "notes": notes_text,
            })

        if not sales_data:
            QMessageBox.warning(self, "تنبيه", "لم يتم إدخال أي مبلغ مبيعات")
            return

        sales_date = self.date_input.date().toString("yyyy-MM-dd")
        sales_date = sales_date.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        next_date = (datetime.strptime(sales_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        currency = "ليرة_سورية"
        conn_curr = get_conn()
        try:
            cur = conn_curr.cursor()
            cur.execute(
                "SELECT العملة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?",
                (sales_date, next_date),
            )
            row = cur.fetchone()
            if row and row[0]:
                currency = row[0]
        except Exception as e:
            logger.error(f"فشل تحميل عملة اليومية: {type(e).__name__}")
            # currency stays as default "ليرة_سورية"
        finally:
            conn_curr.close()

        if self.sales_repo.is_day_closed(sales_date):
            QMessageBox.warning(
                self, "تنبيه",
                "لا يمكن تعديل مبيعات يومية مُغلقة. يجب إعادة فتح اليومية من شاشة النقدية أولًا."
            )
            return

        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            new_sale_ids = []
            for sale in sales_data:
                cursor.execute("""
                    SELECT معرف, المبلغ_الإجمالي FROM المبيعات_اليومية
                    WHERE التاريخ = ? AND معرف_المجموعة = ?
                """, (sales_date, sale["group_id"]))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute("""
                        UPDATE المبيعات_اليومية
                        SET المبلغ_الإجمالي = المبلغ_الإجمالي + ?, ملاحظات = ?
                        WHERE معرف = ?
                    """, (sale["amount"], sale["notes"], existing[0]))
                else:
                    cursor.execute("""
                        INSERT INTO المبيعات_اليومية
                        (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, نوع_المعاملة, ملاحظات)
                        VALUES (?, ?, ?, ?, 'نقدي', ?)
                    """, (sales_date, sale["group_id"], sale["amount"], currency, sale["notes"]))
                    new_sale_ids.append(cursor.lastrowid)

            for sale_id in new_sale_ids:
                cursor.execute("""
                    INSERT INTO سجل_العمليات_الأخيرة (نوع_العملية, معرف_السجل, التاريخ_المتأثر)
                    VALUES (?, ?, ?)
                """, ('بيع', sale_id, sales_date))

            conn.commit()
            saved_count = len(sales_data)

            self.entry_table.setRowCount(0)
            self._populate_entry_table()

            self.view_date_input.setDate(self.date_input.date())
            self.view_previous_sales()

            QMessageBox.information(
                self, "نجاح",
                f"تم حفظ {saved_count} مبيعة بنجاح!"
            )
            app_events.emit_data_changed("sales")

            try:
                main_window = self.window()
                if isinstance(main_window, QMainWindow):
                    main_window.show_status(f"تم حفظ {saved_count} مبيعة بنجاح", "success")
            except Exception:
                pass

        except Exception as e:
            logger.error(str(e))
            if conn:
                conn.rollback()
            QMessageBox.critical(self, "خطأ", f"فشل حفظ المبيعات:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def view_previous_sales(self):
        """عرض المبيعات المسجلة لتاريخ محدد في جدول العرض"""
        selected_date = self.view_date_input.date().toString("yyyy-MM-dd")
        selected_date = selected_date.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        next_date = (datetime.strptime(selected_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT م.معرف, ج.الاسم, م.المبلغ_الإجمالي, م.ملاحظات
                FROM المبيعات_اليومية م
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                WHERE م.التاريخ >= ? AND م.التاريخ < ?
                ORDER BY م.معرف
            """, (selected_date, next_date))

            data = cursor.fetchall()

            self._current_sales = []
            headers = ["المجموعة", "المبلغ", "ملاحظات"]
            rows = []
            total = 0.0

            for row in data:
                sale_id, group_name, amount, notes = row
                sale_record = {
                    "معرف": sale_id,
                    "التاريخ": selected_date,
                    "المبلغ_الإجمالي": amount,
                    "ملاحظات": notes or "",
                    "اسم_المجموعة": group_name,
                }
                self._current_sales.append(sale_record)
                rows.append([group_name, amount, notes or ""])
                total += amount if amount else 0.0

            self.display_table.set_data(headers, rows, id_column_index=-1)

            cursor.execute("""
                SELECT COALESCE(SUM(م.المبلغ_الإجمالي), 0)
                FROM المبيعات_اليومية م
                WHERE م.التاريخ >= ? AND م.التاريخ < ?
            """, (selected_date, next_date))
            real_total = cursor.fetchone()[0]
            self.total_label.setText(f"إجمالي مبيعات اليوم: {fmt(real_total)}")

        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل المبيعات:\n{str(e)}")
        finally:
            conn.close()

    def _get_sale_by_row(self, row_idx):
        if 0 <= row_idx < len(self._current_sales):
            return self._current_sales[row_idx]
        return None

    def _on_edit_requested(self, row_idx):
        sale = self._get_sale_by_row(row_idx)
        if not sale:
            return

        sale_id = sale.get("معرف")
        if sale_id is None:
            return

        if self.sales_repo.is_day_closed(sale["التاريخ"]):
            QMessageBox.warning(
                self, "تنبيه",
                "لا يمكن تعديل مبيعات يومية مُغلقة. يجب إعادة فتح اليومية من شاشة النقدية أولًا."
            )
            return

        record = self.sales_repo.get_by_id(sale_id)
        if not record:
            return

        dialog = EditSaleDialog(
            record["المبلغ_الإجمالي"],
            record["ملاحظات"],
            self,
        )
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                QMessageBox.warning(self, "تنبيه", "الرجاء إدخال مبلغ صحيح")
                return
            self.sales_repo.update(
                sale_id,
                المبلغ_الإجمالي=data["amount"],
                ملاحظات=data["notes"],
            )
            self.view_previous_sales()
            app_events.emit_data_changed("sales")
            QMessageBox.information(self, "نجاح", "تم تعديل المبيعة بنجاح")

    def _on_delete_requested(self, row_idx):
        sale = self._get_sale_by_row(row_idx)
        if not sale:
            return

        sale_id = sale.get("معرف")
        if sale_id is None:
            return

        if self.sales_repo.is_day_closed(sale["التاريخ"]):
            QMessageBox.warning(
                self, "تنبيه",
                "لا يمكن حذف مبيعات يومية مُغلقة. يجب إعادة فتح اليومية من شاشة النقدية أولًا."
            )
            return

        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            "هل أنت متأكد من حذف هذه المبيعة؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.sales_repo.delete(sale_id)
                self.view_previous_sales()
                app_events.emit_data_changed("sales")
                QMessageBox.information(self, "نجاح", "تم حذف المبيعة بنجاح")
            except Exception as e:
                logger.error(str(e))
                QMessageBox.critical(self, "خطأ", f"فشل حذف المبيعة:\n{str(e)}")

    def _on_sale_double_clicked(self, row_idx):
        sale = self._get_sale_by_row(row_idx)
        if not sale:
            return

        detail_data = {
            "التاريخ": sale["التاريخ"],
            "المجموعة": sale["اسم_المجموعة"],
            "المبلغ": sale["المبلغ_الإجمالي"],
            "ملاحظات": sale["ملاحظات"] or "",
        }

        dialog = EntityDetailDialog(
            title="تفاصيل المبيعة",
            detail_data=detail_data,
            parent=self,
        )
        dialog.exec_()

    def undo_last_sale(self):
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT معرف, معرف_السجل, التاريخ_المتأثر FROM سجل_العمليات_الأخيرة
                WHERE نوع_العملية = 'بيع' AND تم_التراجع = 0
                ORDER BY وقت_التسجيل DESC LIMIT 1
            """)
            row = cur.fetchone()
            if not row:
                QMessageBox.information(self, "معلومة", "لا توجد عملية حديثة للتراجع عنها")
                return

            log_id, record_id, affected_date = row

            next_date = (datetime.strptime(affected_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            cur.execute("SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (affected_date, next_date))
            day_row = cur.fetchone()
            if day_row and day_row[0]:
                QMessageBox.warning(self, "تنبيه", "لا يمكن التراجع، اليومية لهذا التاريخ مغلقة. أعد فتحها أولاً من شاشة النقدية")
                return

            cur.execute("SELECT المبلغ_الإجمالي, ملاحظات FROM المبيعات_اليومية WHERE معرف = ?", (record_id,))
            sale = cur.fetchone()
            if not sale:
                QMessageBox.warning(self, "تنبيه", "السجل المراد التراجع عنه غير موجود")
                return

            msg = f"المبلغ: {sale['المبلغ_الإجمالي']}\nالتاريخ: {affected_date}\nملاحظات: {sale['ملاحظات'] or ''}"
            reply = QMessageBox.question(
                self, "تأكيد التراجع",
                f"هل أنت متأكد من التراجع عن آخر عملية بيع؟\n{msg}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

            cur.execute("BEGIN TRANSACTION")
            cur.execute("DELETE FROM المبيعات_اليومية WHERE معرف = ?", (record_id,))
            cur.execute("UPDATE سجل_العمليات_الأخيرة SET تم_التراجع = 1 WHERE معرف = ?", (log_id,))
            conn.commit()

            self.view_previous_sales()
            app_events.emit_data_changed("sales")
            QMessageBox.information(self, "نجاح", "تم التراجع عن آخر عملية بيع بنجاح")
        except Exception as e:
            logger.error(str(e))
            if conn:
                conn.rollback()
            QMessageBox.critical(self, "خطأ", f"فشل التراجع:\n{str(e)}")
        finally:
            if conn:
                conn.close()
