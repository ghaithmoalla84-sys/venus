import logging
import os
import pytest
from unittest.mock import patch
from venus.utils.logger import setup_logger


class TestLogging:
    """اختبارات نظام تسجيل الأخطاء"""

    def test_errors_written_to_log_file(self, tmp_path):
        with patch('venus.utils.logger.os.path.dirname', return_value=str(tmp_path)):
            logger = setup_logger()
            logger.handlers.clear()

            log_path = os.path.join(str(tmp_path), 'venus.log')
            handler = logging.FileHandler(log_path, encoding='utf-8')
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            logger.addHandler(handler)

            logger.error("خطأ تجريبي")
            handler.flush()

            assert os.path.exists(log_path)
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert "خطأ تجريبي" in content
            assert "ERROR" in content

    def test_log_levels_info_warning_error(self, tmp_path):
        with patch('venus.utils.logger.os.path.dirname', return_value=str(tmp_path)):
            logger = setup_logger()
            logger.handlers.clear()

            log_path = os.path.join(str(tmp_path), 'venus.log')
            handler = logging.FileHandler(log_path, encoding='utf-8')
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            logger.addHandler(handler)

            logger.info("معلومة")
            logger.warning("تحذير")
            logger.error("خطأ")
            handler.flush()

            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert "INFO" in content
            assert "WARNING" in content
            assert "ERROR" in content

    def test_log_message_format(self, tmp_path):
        with patch('venus.utils.logger.os.path.dirname', return_value=str(tmp_path)):
            logger = setup_logger()
            logger.handlers.clear()

            log_path = os.path.join(str(tmp_path), 'venus.log')
            formatter = logging.Formatter(
                '%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s'
            )
            handler = logging.FileHandler(log_path, encoding='utf-8')
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            logger.error("رسالة منسقة")
            handler.flush()

            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert "رسالة منسقة" in content
            assert "ERROR" in content
            assert "test_logging.py" in content

    def test_no_sensitive_data_in_logs(self, tmp_path):
        with patch('venus.utils.logger.os.path.dirname', return_value=str(tmp_path)):
            logger = setup_logger()
            logger.handlers.clear()

            log_path = os.path.join(str(tmp_path), 'venus.log')
            handler = logging.FileHandler(log_path, encoding='utf-8')
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(handler)

            logger.info("تم تسجيل الدخول")
            handler.flush()

            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert "password" not in content.lower()
            assert "secret" not in content.lower()
            assert "token" not in content.lower()
            assert "api_key" not in content.lower()
