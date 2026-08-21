# -*- coding: utf-8 -*-
"""
نظام الأحداث المركزي - Venus Coffee
يوفّر كائناً عالميًا app_events يُستقبل منه إشارة data_changed(str)
لكي تتفاعل الشاشات المراقبة معًا بعد أي تغيير بيانات.
"""

from PyQt5.QtCore import QObject, pyqtSignal


class AppEvents(QObject):
    """مجموعة مركزية للإشارات العامة للتطبيق."""

    # يمرّر اسم الكيان المتأثر (مثال: "materials"، "creditors"، "groups")
    data_changed = pyqtSignal(str)

    def emit_data_changed(self, entity_name):
        """إطلاق إشارة تغيّر البيانات لكيان محدد."""
        self.data_changed.emit(entity_name)


# كائن عام يمكن استيراده من أي شاشة:
#   from venus.core.events import app_events
app_events = AppEvents()
