from PyQt5.QtWidgets import QStyledItemDelegate, QLineEdit
from PyQt5.QtGui import QDoubleValidator


class NumericDelegate(QStyledItemDelegate):
    """ديلجيت لتقييد الإدخال بالأرقام فقط في الجداول"""
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setValidator(QDoubleValidator())
        return editor
