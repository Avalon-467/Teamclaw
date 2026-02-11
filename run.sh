#!/bin/bash
# Mini TimeBot 一键运行（环境配置 + API Key + 注册用户 + 启动服务）

cd "$(dirname "$0")"

echo "========== 1/4 环境检查与配置 =========="
bash scripts/setup_env.sh
if [ $? -ne 0 ]; then
    echo "❌ 环境配置失败，请检查错误信息"
    exit 1
fi

echo ""
echo "========== 2/4 API Key 配置 =========="
source scripts/setup_apikey.sh

echo ""
echo "========== 3/4 用户管理 =========="
read -p "是否需要添加新用户？(y/N): " answer
if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
    bash scripts/adduser.sh
fi

echo ""
echo "========== 4/4 启动服务 =========="
bash scripts/start.sh
