#!/bin/bash
# ============================================================
# PrismaMate 棱镜 - 后端生产启动脚本 (Linux/Mac)
# ============================================================
# 用法: ./start_backend.sh
# ============================================================

set -e

echo "========================================"
echo "PrismaMate 棱镜 - 后端启动"
echo "========================================"

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查虚拟环境
VENV_DIR="venv"
if [ ! -d "$VENV_DIR/bin/python" ]; then
    echo "错误: 虚拟环境不存在，正在创建..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install -r requirements.txt
    deactivate
fi

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "警告: .env 文件不存在，正在创建..."
    cp ".env.example" ".env"
    echo "请编辑 .env 文件配置您的 API 密钥"
fi

# 检查 API Key
if ! grep -q "DEEPSEEK_API_KEY=sk-" ".env" 2>/dev/null; then
    echo "警告: DEEPSEEK_API_KEY 未配置，请确保已在 .env 中设置"
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source "$VENV_DIR/bin/activate"

# 启动服务
echo ""
echo "启动后端服务 (生产模式)..."
echo "API 文档: http://localhost:8000/docs"
echo "按 Ctrl+C 停止服务"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
