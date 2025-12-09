#!/usr/bin/env python3
"""
Unslothサーバーのモデル読み込み状況を監視するスクリプト
"""

import requests
import time
import json
from datetime import datetime

def check_model_status():
    """モデル読み込み状況を確認"""
    try:
        response = requests.get("http://unsloth:5006/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('model_loaded', False), data
        else:
            return False, {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}

def monitor_model_loading(max_checks=30, interval=10):
    """モデル読み込みを監視"""
    print("🔍 Monitoring Unsloth model loading...")
    print(f"📊 Will check {max_checks} times every {interval} seconds")
    print("="*60)
    
    for i in range(1, max_checks + 1):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Check {i}/{max_checks}: ", end="")
        
        model_loaded, status_data = check_model_status()
        
        if model_loaded:
            print("✅ Model loaded successfully!")
            print(f"📊 GPU Memory: {status_data.get('gpu_memory', {})}")
            return True
        else:
            print("⏳ Model not loaded yet...")
            if "error" in status_data:
                print(f"❌ Error: {status_data['error']}")
        
        if i < max_checks:
            time.sleep(interval)
    
    print("⏰ Monitoring completed. Model may still be loading in background.")
    return False

if __name__ == "__main__":
    monitor_model_loading()
