# -*- coding: utf-8 -*-
"""
نظام تسجيل الأخطاء لتطبيق Venus Coffee
"""

import logging
import os


def setup_logger():
    logger = logging.getLogger('venus')
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_path = os.path.join(project_root, 'venus.log')
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
