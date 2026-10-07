import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'agrismart-secret-key-2025'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-agrismart-secret'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL')
        or 'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'agrismart.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    OFFLINE_MODE = False

    FLASH_SALE_DISCOUNT = 0.20
    FLASH_SALE_THRESHOLD_DAYS = 2
    FLASH_SALE_MIN_DISCOUNT = 0.05
    FLASH_SALE_MAX_DISCOUNT = 0.90