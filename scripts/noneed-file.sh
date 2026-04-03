#!/bin/bash

echo "Cleaning Python cache files..."

# Pythonキャッシュ削除
find ../ -type d -name "__pycache__" -exec rm -rf {} +
find ../ -type f -name "*.pyc" -delete

# pytestキャッシュ
rm -rf ../.pytest_cache

# 仮想環境削除
rm -rf ../.venv

echo "Done."