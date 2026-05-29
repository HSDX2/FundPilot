#!/usr/bin/env python
"""迁移已有的 AI Provider 明文 API 密钥 → 加密存储.

使用方式:
  cd backend && python scripts/encrypt_api_keys.py

前置条件:
  1. .env 中已配置 ENCRYPTION_KEY
  2. cryptography 已安装
"""

import asyncio
import os
import sys

# 确保能找到 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.utils.encryption import decrypt_value, encrypt_value


async def main():
    if not settings.ENCRYPTION_KEY:
        sys.exit("错误: ENCRYPTION_KEY 未配置，请在 .env 中设置")

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # 查询所有 AI provider
        from app.models.system import AIProvider

        result = await session.execute(select(AIProvider))
        providers = list(result.scalars().all())

        migrated = 0
        already_encrypted = 0
        skipped = 0

        for p in providers:
            if not p.api_key:
                skipped += 1
                continue

            # 尝试解密，如果失败说明是明文
            try:
                decrypt_value(p.api_key)
                already_encrypted += 1
                continue
            except Exception:
                pass

            # 明文密钥 → 加密
            p.api_key = encrypt_value(p.api_key)
            session.add(p)
            migrated += 1
            print(f"  [迁移] {p.name} ({p.provider_type})")

        await session.flush()
        await session.commit()

    await engine.dispose()

    print(f"\n完成: 迁移 {migrated} 条, 已加密 {already_encrypted} 条, 跳过 {skipped} 条")


if __name__ == "__main__":
    asyncio.run(main())
