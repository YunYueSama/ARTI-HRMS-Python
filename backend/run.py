"""
一键启动脚本

用法：
    python run.py          # 开发模式（热重载）
    python run.py --prod   # 生产模式（无热重载）

也可以直接双击 start.bat 启动（Windows）。
"""

import os
import sys

# 自动切换到脚本所在目录，避免因工作目录不同导致 import 失败
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    is_prod = "--prod" in sys.argv

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not is_prod,
    )
