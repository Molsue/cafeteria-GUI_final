#!/bin/bash
# simulator_web 启动脚本
# 用法: ./generate.sh [--once] [--interval 30]
cd "$(dirname "$0")"
exec python3 generator.py "$@"
