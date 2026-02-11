#!/bin/bash
# DeepSeek API Key 配置脚本

cd "$(dirname "$0")/.."

ENV_FILE="config/.env"
EXAMPLE_FILE="config/.env.example"

# 已有 .env 且 Key 已配置，跳过
if [ -f "$ENV_FILE" ]; then
    KEY=$(grep -oP '(?<=DEEPSEEK_API_KEY=).+' "$ENV_FILE")
    if [ -n "$KEY" ] && [ "$KEY" != "your_deepseek_api_key_here" ]; then
        echo "[OK] API Key 已配置"
        return 0 2>/dev/null || exit 0
    fi
fi

echo "================================================"
echo "  需要配置 DeepSeek API Key 才能使用"
echo "  获取地址: https://platform.deepseek.com/api_keys"
echo "================================================"
echo ""

read -p "请输入你的 DeepSeek API Key: " api_key

if [ -z "$api_key" ]; then
    echo "❌ 未输入 API Key，跳过配置"
    echo "   请稍后手动编辑 config/.env"
    return 1 2>/dev/null || exit 1
fi

# 读取 API_BASE（如果已有 .env 就保留，否则用默认值）
if [ -f "$ENV_FILE" ]; then
    API_BASE=$(grep -oP '(?<=DEEPSEEK_API_BASE=).+' "$ENV_FILE")
fi
API_BASE="${API_BASE:-https://api.deepseek.com}"

# 写入 .env
cat > "$ENV_FILE" << EOF
DEEPSEEK_API_KEY=$api_key
DEEPSEEK_API_BASE=$API_BASE
EOF

echo "✅ API Key 已保存到 config/.env"
