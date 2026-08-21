# -*- coding: utf-8 -*-
"""
نافذة الملاحظات - Venus Coffee
ملاحظات يومية مستقلة عن حسابات التطبيق
"""

import sqlite3
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


NOTES_DB_PATH = "venus_notes.db"


def get_notes_conn():
    """اتصال بقاعدة بيانات الملاحظات المستقلة"""
    conn = sqlite3.connect(NOTES_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS الملاحظات (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            التاريخ TEXT NOT NULL,
            المحتوى TEXT NOT NULL,
            تاريخ_الإنشاء TEXT DEFAULT CURRENT_TIMESTAMP,
            تاريخ_التعديل TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_الملاحظات_التاريخ ON الملاحظات(التاريخ)"
    )
    conn.commit()
    return conn


class MarkedCalendar(QCalendarWidget):
    """تقويم يرسم علامة مرئية للأيام التي تحوي ملاحظات."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._marked = set()

    def set_marked_dates(self, dates):
        """dates: iterable من QDate"""
        self._marked = set(dates)
        self.updateCells()

    def paintCell(self, painter, rect, date):
        if date in self._marked:
            painter.save()
            painter.fillRect(rect.adjusted(0, 0, -1, -1), QColor("#f0e6f6"))
            painter.setPen(QColor("#8e44ad"))
            f = painter.font()
            f.setBold(True)
            painter.setFont(f)
        super().paintCell(painter, rect, date)
        if date in self._marked:
            painter.setBrush(QColor("#8e44ad"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect.center().x() - 2, rect.bottom() - 6, 4, 4)
            painter.restore()


class NotesDialog(QDialog):
    """نافذة الملاحظات اليومية بتقويم شهري"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📝 الملاحظات اليومية")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumSize(800, 600)
        self.resize(900, 650)
        self._current_note_id = None
        self._init_ui()
        self._load_marked_dates()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ── العمود الأيسر: التقويم + قائمة ملاحظات اليوم ──
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        # التقويم
        cal_group = QGroupBox("📅 التقويم")
        cal_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px; font-weight: bold; color: #8e44ad;
                border: 2px solid #8e44ad; border-radius: 8px;
                margin-top: 8px; padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin; right: 10px;
                padding: 0 8px;
            }
        """)
        cal_layout = QVBoxLayout(cal_group)
        cal_layout.setContentsMargins(10, 10, 10, 10)

        self.calendar = MarkedCalendar()
        self.calendar.setLayoutDirection(Qt.RightToLeft)
        self.calendar.setGridVisible(True)
        self.calendar.setMinimumDate(QDate(2020, 1, 1))
        self.calendar.setMaximumDate(QDate(2099, 12, 31))
        self.calendar.setStyleSheet("""
            QCalendarWidget QToolButton {
                color: #2c3e50; font-size: 13px; font-weight: bold;
            }
            QCalendarWidget QMenu { font-size: 13px; }
            QCalendarWidget QAbstractItemView:enabled {
                font-size: 12px; color: #2c3e50;
                selection-background-color: #8e44ad;
                selection-color: white;
            }
            QCalendarWidget QAbstractItemView:disabled { color: #bdc3c7; }
        """)
        self.calendar.clicked.connect(self._on_date_selected)
        self.calendar.currentPageChanged.connect(
            lambda y, m: self._load_marked_dates()
        )
        cal_layout.addWidget(self.calendar)

        # مؤشر أيام لها ملاحظات
        self._legend = QLabel("● أيام لها ملاحظات")
        self._legend.setStyleSheet("color: #8e44ad; font-size: 12px; padding: 4px;")
        self._legend.setAlignment(Qt.AlignCenter)
        cal_layout.addWidget(self._legend)

        left_panel.addWidget(cal_group)

        # قائمة ملاحظات اليوم المختار
        day_group = QGroupBox("📋 ملاحظات هذا اليوم")
        day_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px; font-weight: bold; color: #2c3e50;
                border: 2px solid #bdc3c7; border-radius: 8px;
                margin-top: 8px; padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin; right: 10px; padding: 0 8px;
            }
        """)
        day_layout = QVBoxLayout(day_group)
        day_layout.setContentsMargins(8, 8, 8, 8)

        self.notes_list = QListWidget()
        self.notes_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd; border-radius: 6px;
                font-size: 13px; background-color: #fafafa;
            }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #eee; }
            QListWidget::item:selected {
                background-color: #8e44ad; color: white;
            }
            QListWidget::item:hover { background-color: #f0e6f6; }
        """)
        self.notes_list.itemClicked.connect(self._on_note_selected)
        day_layout.addWidget(self.notes_list)

        left_panel.addWidget(day_group)

        # ── العمود الأيمن: محرر الملاحظة ──
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        editor_group = QGroupBox("✏️ محرر الملاحظة")
        editor_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px; font-weight: bold; color: #27ae60;
                border: 2px solid #27ae60; border-radius: 8px;
                margin-top: 8px; padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin; right: 10px; padding: 0 8px;
            }
        """)
        editor_layout = QVBoxLayout(editor_group)
        editor_layout.setSpacing(10)
        editor_layout.setContentsMargins(12, 12, 12, 12)

        # التاريخ المختار
        self.selected_date_label = QLabel(
            f"📅 {QDate.currentDate().toString('yyyy-MM-dd')}"
        )
        self.selected_date_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #8e44ad; padding: 4px;"
        )
        editor_layout.addWidget(self.selected_date_label)

        # محرر النص
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText(
            "اكتب ملاحظتك هنا...\n\nمثال:\n- استلمت بضاعة من أبو أحمد\n- دفعت إيجار الشهر\n- مبيعات اليوم كانت ممتازة"
        )
        self.note_editor.setStyleSheet("""
            QTextEdit {
                border: 2px solid #ddd; border-radius: 8px;
                padding: 10px; font-size: 14px;
                background-color: #fffef7;
                line-height: 1.6;
            }
            QTextEdit:focus { border-color: #8e44ad; }
        """)
        self.note_editor.setMinimumHeight(250)
        editor_layout.addWidget(self.note_editor)

        # أزرار الإجراءات
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        save_btn = QPushButton("💾 حفظ")
        save_btn.setFixedHeight(40)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white;
                border: none; border-radius: 6px;
                font-size: 14px; font-weight: bold; padding: 8px 20px;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
        """)
        save_btn.clicked.connect(self._save_note)

        new_btn = QPushButton("➕ ملاحظة جديدة")
        new_btn.setFixedHeight(40)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border: none; border-radius: 6px;
                font-size: 14px; font-weight: bold; padding: 8px 20px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        new_btn.clicked.connect(self._new_note)

        delete_btn = QPushButton("🗑️ حذف")
        delete_btn.setFixedHeight(40)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                border: none; border-radius: 6px;
                font-size: 14px; font-weight: bold; padding: 8px 20px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        delete_btn.clicked.connect(self._delete_note)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        editor_layout.addLayout(btn_layout)

        right_panel.addWidget(editor_group)

        # إحصائيات سريعة
        stats_group = QGroupBox("📊 إحصائيات")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px; font-weight: bold; color: #7f8c8d;
                border: 1px solid #bdc3c7; border-radius: 8px;
                margin-top: 8px; padding-top: 12px;
                background-color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin; right: 10px; padding: 0 8px;
            }
        """)
        stats_layout = QHBoxLayout(stats_group)
        stats_layout.setContentsMargins(12, 8, 12, 8)
        self.stats_label = QLabel("جاري التحميل...")
        self.stats_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        stats_layout.addWidget(self.stats_label)
        right_panel.addWidget(stats_group)

        # تجميع العمودين
        main_layout.addLayout(left_panel, 2)
        main_layout.addLayout(right_panel, 3)

        # تحديد اليوم الحالي
        self.calendar.setSelectedDate(QDate.currentDate())
        self._on_date_selected(QDate.currentDate())

    def _get_selected_date_str(self):
        return self.calendar.selectedDate().toString("yyyy-MM-dd")

    def _on_date_selected(self, date):
        date_str = date.toString("yyyy-MM-dd")
        self.selected_date_label.setText(f"📅 {date_str}")
        self._load_day_notes(date_str)
        self._new_note()

    def _load_day_notes(self, date_str):
        self.notes_list.clear()
        conn = None
        try:
            conn = get_notes_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT معرف, المحتوى FROM الملاحظات
                WHERE التاريخ = ? ORDER BY معرف
            """, (date_str,))
            rows = cursor.fetchall()
            for row in rows:
                preview = str(row["المحتوى"] or "")[:50].replace("\n", " ")
                item = QListWidgetItem(f"📌 {preview}...")
                item.setData(Qt.UserRole, row["معرف"])
                self.notes_list.addItem(item)
        except Exception as e:
            pass
        finally:
            if conn:
                conn.close()
        self._update_stats()

    def _on_note_selected(self, item):
        note_id = item.data(Qt.UserRole)
        conn = None
        try:
            conn = get_notes_conn()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT معرف, المحتوى FROM الملاحظات WHERE معرف = ?",
                (note_id,)
            )
            row = cursor.fetchone()
            if row:
                self._current_note_id = row["معرف"]
                self.note_editor.setPlainText(row["المحتوى"] or "")
        except Exception:
            pass
        finally:
            if conn:
                conn.close()

    def _new_note(self):
        self._current_note_id = None
        self.note_editor.clear()
        self.notes_list.clearSelection()
        self.note_editor.setFocus()

    def _save_note(self):
        content = self.note_editor.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "تنبيه", "الرجاء كتابة ملاحظة أولاً")
            return
        date_str = self._get_selected_date_str()
        conn = None
        try:
            conn = get_notes_conn()
            cursor = conn.cursor()
            if self._current_note_id:
                cursor.execute("""
                    UPDATE الملاحظات
                    SET المحتوى = ?, تاريخ_التعديل = CURRENT_TIMESTAMP
                    WHERE معرف = ?
                """, (content, self._current_note_id))
            else:
                cursor.execute("""
                    INSERT INTO الملاحظات (التاريخ, المحتوى)
                    VALUES (?, ?)
                """, (date_str, content))
                self._current_note_id = cursor.lastrowid
            conn.commit()
            self._load_day_notes(date_str)
            self._load_marked_dates()
            QMessageBox.information(self, "تم", "تم حفظ الملاحظة بنجاح ✅")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _delete_note(self):
        if not self._current_note_id:
            QMessageBox.warning(self, "تنبيه", "اختر ملاحظة من القائمة أولاً")
            return
        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            "هل أنت متأكد من حذف هذه الملاحظة؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        conn = None
        try:
            conn = get_notes_conn()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM الملاحظات WHERE معرف = ?",
                (self._current_note_id,)
            )
            conn.commit()
            self._current_note_id = None
            self.note_editor.clear()
            date_str = self._get_selected_date_str()
            self._load_day_notes(date_str)
            self._load_marked_dates()
            QMessageBox.information(self, "تم", "تم حذف الملاحظة بنجاح")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل الحذف:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _load_marked_dates(self):
        """تلوين الأيام التي لها ملاحظات في التقويم"""
        year = self.calendar.yearShown()
        month = self.calendar.monthShown()
        conn = None
        try:
            conn = get_notes_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT التاريخ FROM الملاحظات
                WHERE التاريخ LIKE ?
            """, (f"{year}-{month:02d}-%",))
            marked = set()
            for row in cursor.fetchall():
                d = QDate.fromString(row[0], "yyyy-MM-dd")
                if d.isValid():
                    marked.add(d)
            self.calendar.set_marked_dates(marked)
        except Exception:
            pass
        finally:
            if conn:
                conn.close()

    def _update_stats(self):
        conn = None
        try:
            conn = get_notes_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM الملاحظات")
            total = cursor.fetchone()[0]
            date_str = self._get_selected_date_str()
            cursor.execute(
                "SELECT COUNT(*) FROM الملاحظات WHERE التاريخ = ?",
                (date_str,)
            )
            today_count = cursor.fetchone()[0]
            self.stats_label.setText(
                f"إجمالي الملاحظات: {total} | ملاحظات هذا اليوم: {today_count}"
            )
        except Exception:
            pass
        finally:
            if conn:
                conn.close()
