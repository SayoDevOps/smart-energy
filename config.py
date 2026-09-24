import os
from dotenv import load_dotenv

load_dotenv()


def _database_uri():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return None
    if database_url.startswith('postgres://'):
        return 'postgresql+psycopg://' + database_url[len('postgres://'):]
    if database_url.startswith('postgresql://'):
        return 'postgresql+psycopg://' + database_url[len('postgresql://'):]
    return database_url


class Config:
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-only-fallback-key'
    SQLALCHEMY_DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI or 'sqlite:///energy.db'


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}
