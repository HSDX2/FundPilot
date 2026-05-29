"""API 密钥加密/解密工具及 SQLAlchemy 类型装饰器."""

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator as SA_TypeDecorator


def _is_encryption_enabled() -> bool:
    from app.core.config import settings

    return bool(settings.ENCRYPTION_KEY)


def _get_fernet() -> Fernet:
    from app.core.config import settings

    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_value(plain: str) -> str:
    """加密明文，返回字符串密文。"""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(cipher: str) -> str:
    """解密密文，返回明文。"""
    return _get_fernet().decrypt(cipher.encode()).decode()


class EncryptedText(SA_TypeDecorator):
    """透明加解密 Text 字段。

    写入时自动加密，读取时自动解密。
    ENCRYPTION_KEY 未配置时透传（开发环境不做加密）。
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not _is_encryption_enabled():
            return value
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not _is_encryption_enabled():
            return value
        try:
            return decrypt_value(value)
        except (InvalidToken, Exception):
            # 向后兼容：数据库中是明文时直接返回
            return value
