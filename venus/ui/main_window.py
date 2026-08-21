# Path: D:\acc\venus\ui\main_window.py
# -*- coding: utf-8 -*-
"""
النافذة الرئيسية لتطبيق محاسبة متجر "فينوس كوفي"
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime
from venus.core.database import get_conn
from venus.ui.screens.dashboard import DashboardScreen
from venus.ui.screens.settings import SettingsScreen
from venus.ui.screens.inventory import InventoryScreen
from venus.ui.screens.sales import SalesScreen
from venus.ui.screens.cash import CashScreen
from venus.ui.screens.creditors import CreditorsScreen
from venus.ui.screens.reports import ReportsScreen
from venus.ui.screens.financial_health import FinancialHealthScreen
from venus.ui.styles import (
    Colors, FontSizes, BorderRadius, Spacing, ButtonHeight,
    title_label_style, sidebar_button_style, primary_button_style, input_style,
    status_bar_style
)
from venus.ui.widgets.notes_dialog import NotesDialog
from venus.utils.logger import setup_logger
logger = setup_logger()

class MainWindow(QMainWindow):
    SCREEN_NAMES = [
        "الرئيسية",
        "الصحة المالية",
        "المبيعات اليومية",
        "المواد والمخزون",
        "الدائنون",
        "النقدية والمصروفات",
        "التقارير",
        "الإعدادات"
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Venus Coffee - نظام المحاسبة")
        self.setLayoutDirection(Qt.RightToLeft)
        
        available = QApplication.primaryScreen().availableGeometry()
        min_w, min_h = 1024, 650
        if available.width() < min_w or available.height() < min_h:
            self.showMaximized()
        else:
            target_w = max(min_w, int(available.width() * 0.9))
            target_h = max(min_h, int(available.height() * 0.9))
            x = available.x() + (available.width() - target_w) // 2
            y = available.y() + (available.height() - target_h) // 2
            self.setGeometry(x, y, target_w, target_h)
        self.setMinimumSize(min_w, min_h)
        
        # العنصر المركزي
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # التخطيط الرئيسي الأفقي
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # إنشاء منطقة المحتوى (شريط علوي + صفحات مكدسة)
        self.stacked_widget = QStackedWidget()
        self.screens = {}
        
        for idx, name in enumerate(self.SCREEN_NAMES):
            if idx == 0:
                screen = DashboardScreen()
            elif idx == 1:
                screen = FinancialHealthScreen()
            elif idx == 2:
                screen = SalesScreen()
            elif idx == 3:
                screen = InventoryScreen()
            elif idx == 5:
                screen = CashScreen()
            elif idx == 4:
                screen = CreditorsScreen()
            elif idx == 7:
                screen = SettingsScreen()
            elif idx == 6:
                screen = ReportsScreen()
            else:
                screen = QWidget()
                layout = QVBoxLayout(screen)
                layout.setContentsMargins(40, 40, 40, 40)
                
                label = QLabel(f"شاشة {name}")
                label.setAlignment(Qt.AlignCenter)
                label.setStyleSheet(f"""
                    font-size: {FontSizes.XL7};
                    color: {Colors.LIGHT_TEXT};
                    font-weight: bold;
                    padding: 50px;
                """)
                layout.addWidget(label)
                
                desc = QLabel(f"هنا سيتم عرض محتوى شاشة {name} لاحقاً")
                desc.setAlignment(Qt.AlignCenter)
                desc.setStyleSheet(f"font-size: {FontSizes.XL}; color: {Colors.LIGHT_TEXT};")
                layout.addWidget(desc)
            
            self.stacked_widget.addWidget(screen)
            self.screens[name] = screen
        
        # الشريط العلوي
        top_bar = QWidget()
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet(f"""
            background-color: {Colors.WHITE};
            border-bottom: 2px solid {Colors.PRIMARY};
        """)
        
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(30, 10, 30, 10)
        
        # اسم المتجر من الإعدادات
        store_name = self.get_store_name()
        self.store_name_label = QLabel(f"🏪 {store_name}")
        self.store_name_label.setStyleSheet(title_label_style(font_size=FontSizes.XL4, color=Colors.DARK))
        
        # التاريخ الحالي
        current_date = datetime.now().strftime("%Y-%m-%d")
        self.date_label = QLabel(f"📅 {current_date}")
        self.date_label.setStyleSheet(f"""
            font-size: {FontSizes.MD};
            color: {Colors.DARK_TEXT};
            border: none;
        """)
        
        top_layout.addWidget(self.store_name_label)
        
        refresh_btn = QPushButton("تحديث البيانات")
        refresh_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_btn.setFixedHeight(36)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(primary_button_style(
            bg=Colors.SUCCESS, hover=Colors.SUCCESS_HOVER, font_size=FontSizes.MD,
            padding="6px 14px"
        ))
        refresh_btn.clicked.connect(self.refresh_all_data)
        top_layout.addWidget(refresh_btn)

        calculator_btn = QPushButton("🧮 حاسبة")
        calculator_btn.setFixedHeight(36)
        calculator_btn.setCursor(Qt.PointingHandCursor)
        calculator_btn.setStyleSheet(primary_button_style(
            bg="#7f8c8d", hover="#6c7a7d", font_size=FontSizes.MD,
            padding="6px 14px"
        ))
        calculator_btn.clicked.connect(self._open_calculator)
        top_layout.addWidget(calculator_btn)

        notes_btn = QPushButton("📝 ملاحظات")
        notes_btn.setFixedHeight(36)
        notes_btn.setCursor(Qt.PointingHandCursor)
        notes_btn.setStyleSheet(primary_button_style(
            bg="#8e44ad", hover="#7d3c98", font_size=FontSizes.MD,
            padding="6px 14px"
        ))
        notes_btn.clicked.connect(self._open_notes)
        top_layout.addWidget(notes_btn)

        top_layout.addStretch()
        top_layout.addWidget(self.date_label)
        
        # تجميع المحتوى
        content_layout = QVBoxLayout()
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(top_bar)
        content_layout.addWidget(self.stacked_widget)
        
        # الشريط الجانبي
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(f"background-color: {Colors.SIDEBAR_BG};")
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(6)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)
        
        # عنوان المتجر في الشريط الجانبي
        store_title = QLabel("☕ فينوس كوفي")
        store_title.setAlignment(Qt.AlignCenter)
        store_title.setStyleSheet(f"""
            color: #ecf0f1;
            font-size: {FontSizes.LG};
            font-weight: bold;
            padding: 15px;
            background-color: {Colors.SIDEBAR_TITLE_BG};
            border-radius: {BorderRadius.LG};
            margin-bottom: 10px;
        """)
        sidebar_layout.addWidget(store_title)
        
        # أزرار التنقل
        self.buttons = []
        button_data = [
            ("🏠 الرئيسية", 0),
            ("📈 الصحة المالية", 1),
            ("🛒 المبيعات اليومية", 2),
            ("📦 المواد والمخزون", 3),
            ("👥 الدائنون", 4),
            ("💰 النقدية والمصروفات", 5),
            ("📊 التقارير", 6),
            ("⚙️ الإعدادات", 7)
        ]
        
        self.button_group = QButtonGroup()
        
        for text, index in button_data:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFixedHeight(ButtonHeight.XL)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(sidebar_button_style())
            btn.clicked.connect(lambda checked, idx=index: self.switch_screen(idx))
            sidebar_layout.addWidget(btn)
            self.button_group.addButton(btn, index)
            self.buttons.append(btn)
        
        sidebar_layout.addStretch()
        
        # إضافة العناصر إلى التخطيط الرئيسي
        # في وضع RTL: العنصر المضاف أولاً يظهر على اليمين
        main_layout.addWidget(sidebar)
        main_layout.addLayout(content_layout)
        
        # شريط الحالة
        self.statusBar().showMessage("جاهز - Venus Coffee")
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self.statusBar().setStyleSheet(""))
        self._status_timer.timeout.connect(lambda: self.statusBar().showMessage("جاهز - Venus Coffee"))
        
        # تفعيل الزر الأول بشكل افتراضي
        self.buttons[0].setChecked(True)

        # فحص النزاهة المالية عند البدء
        QTimer.singleShot(3000, self._run_integrity_check)
    
    def _run_integrity_check(self):
        """فحص النزاهة المالية عند بدء التطبيق"""
        try:
            from venus.core.integrity_checker import get_failed_checks
            failed = get_failed_checks(days_back=7)

            if not failed:
                self.statusBar().showMessage(
                    "✅ فحص النزاهة المالية: جميع الحسابات صحيحة",
                    5000
                )
                return

            # يوجد تناقضات - أظهر تنبيهاً
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("⚠️ تنبيه - فحص النزاهة المالية")
            msg.setLayoutDirection(Qt.RightToLeft)

            details = "\n".join(str(r) for r in failed)
            msg.setText(
                f"اكتُشف {len(failed)} تناقض في الحسابات المالية:\n\n"
                f"{details}\n\n"
                "يُنصح بمراجعة هذه الأرقام مع مديرك."
            )
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()

            self.statusBar().showMessage(
                f"⚠️ يوجد {len(failed)} تناقض مالي - راجع التفاصيل",
                10000
            )
        except Exception as e:
            logger.error(f"_run_integrity_check خطأ: {e}")
    
    def closeEvent(self, event):
        try:
            conn = get_conn()
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT COUNT(*) FROM أرصدة_الصندوق WHERE التاريخ = ? AND مغلقة = 0", (today,))
            count = cursor.fetchone()[0]
            conn.close()
            if count > 0:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Question)
                msg.setWindowTitle("تأكيد الإغلاق")
                msg.setText("اليومية لهذا اليوم لا تزال مفتوحة ولم تُغلق بعد. هل تريد الإغلاق على أي حال؟ (بياناتك المُدخلة محفوظة، لكن يُفضّل إجراء التسوية اليومية قبل الإغلاق)")
                btn_close = msg.addButton("إغلاق على أي حال", QMessageBox.AcceptRole)
                btn_cancel = msg.addButton("إلغاء والعودة", QMessageBox.RejectRole)
                msg.setDefaultButton(btn_cancel)
                msg.exec_()
                if msg.clickedButton() == btn_cancel:
                    event.ignore()
                    return
            event.accept()
        except Exception:
            event.accept()
    
    def switch_screen(self, index):
        """التبديل بين الشاشات"""
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        
        self.statusBar().showMessage(f"الشاشة الحالية: {self.SCREEN_NAMES[index]}")
    
    def show_status(self, message, level="info"):
        """عرض رسالة مؤقتة في شريط الحالة بتلوين حسب المستوى"""
        self.statusBar().setStyleSheet(status_bar_style(level))
        self.statusBar().showMessage(message)
        self._status_timer.start(4000)
    
    def get_store_name(self):
        """جلب اسم المتجر من جدول الإعدادات"""
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'اسم_المحل'")
            result = cursor.fetchone()
            return result[0] if result else "فينوس كوفي"
        except Exception:
            return "فينوس كوفي"
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def refresh_all_data(self):
        """تحديث بيانات جميع الشاشات بشكل آمن"""
        refresh_map = {
            "الرئيسية": ["refresh_data"],
            "الصحة المالية": ["load_data"],
            "المبيعات اليومية": ["load_data"],
            "المواد والمخزون": ["load_data"],
            "الدائنون": ["load_data"],
            "النقدية والمصروفات": ["refresh_status", "load_movements"],
            "التقارير": ["load_sales_report", "load_profit_report", "load_inventory", "load_buy_list", "load_debts", "load_cash_movements", "_load_suppliers_combo"],
            "الإعدادات": ["load_data"]
        }

        errors = []
        for screen_name, methods in refresh_map.items():
            screen = self.screens.get(screen_name)
            if not screen:
                continue
            for method_name in methods:
                if hasattr(screen, method_name):
                    try:
                        getattr(screen, method_name)()
                    except Exception as e:
                        logger.error(f"فشل تحديث {screen_name}.{method_name}: {e}")
                        errors.append(method_name)

        if errors:
            self.statusBar().showMessage(f"تم التحديث مع أخطاء في: {', '.join(errors)}")
        else:
            self.statusBar().showMessage("تم تحديث جميع البيانات بنجاح")

    def _open_calculator(self):
        """فتح حاسبة Windows المدمجة"""
        import subprocess
        try:
            subprocess.Popen("calc.exe")
        except Exception as e:
            QMessageBox.warning(self, "تنبيه", f"تعذّر فتح الحاسبة:\n{str(e)}")

    def _open_notes(self):
        """فتح نافذة الملاحظات"""
        dialog = NotesDialog(self)
        dialog.exec_()
