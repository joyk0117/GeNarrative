#!/usr/bin/env python3
"""
デフォルト値での画像生成テスト（簡易版）

新しいデフォルト値 1024×768 での画像生成を直接テストします。
サーバーチェックをスキップして、直接生成処理を実行します。
"""

import os
import time
from datetime import datetime

# 統一実装のインポート
from common_base import APIConfig, ProcessingConfig, GenerationConfig
from _unified import generate_content


def test_direct_image_generation():
    """デフォルト値での直接画像生成テスト"""
    print("🎨 Direct Image Generation Test (1024×768)")
    print("=" * 60)
    
    # テスト用のSIS data
    sample_sis = {
        "summary": "A beautiful sunset over a calm ocean with gentle waves and seagulls flying",
        "emotions": ["peaceful", "serene", "uplifting"],
        "mood": "calm and inspiring",
        "themes": ["nature", "ocean", "sunset", "tranquility"],
        "narrative": {
            "characters": ["seagulls"],
            "location": "Peaceful coastline at sunset",
            "weather": "Clear evening with gentle breeze",
            "tone": "serene and contemplative",
            "style": "nature photography"
        },
        "visual": {
            "style": "realistic seascape photography",
            "composition": "wide ocean view with sunset horizon",
            "lighting": "warm golden sunset lighting",
            "perspective": "beach-level view looking out to sea",
            "colors": ["golden orange", "deep blue", "soft pink", "warm yellow"]
        },
        "audio": {
            "genre": "nature sounds",
            "tempo": "slow and rhythmic",
            "instruments": ["ocean waves", "seagull calls", "gentle wind"],
            "structure": "natural ocean ambiance"
        }
    }
    
    print("📝 Test SIS Summary:")
    print(f"   {sample_sis['summary']}")
    print(f"   Emotions: {', '.join(sample_sis['emotions'])}")
    print(f"   Mood: {sample_sis['mood']}")
    
    # 設定クラスの作成（デフォルト値を使用）
    api_config = APIConfig()
    generation_config = GenerationConfig()  # デフォルト値 1024×768 を使用
    processing_config = ProcessingConfig()
    
    print(f"\n🔧 Configuration:")
    print(f"   Image size: {generation_config.image_width}×{generation_config.image_height}")
    print(f"   SD URI: {api_config.sd_uri}")
    print(f"   Unsloth URI: {api_config.unsloth_uri}")
    print(f"   Output dir: {processing_config.output_dir}")
    
    # 画像生成テスト実行
    print(f"\n🎨 Starting image generation...")
    print(f"   Expected resolution: {generation_config.image_width}×{generation_config.image_height}")
    print(f"   Pixel count: {generation_config.image_width * generation_config.image_height:,} pixels")
    
    start_time = time.time()
    try:
        result = generate_content(
            sample_sis,
            'image',
            api_config=api_config,
            processing_config=processing_config,
            generation_config=generation_config,
            test_case_name="direct_default_test"
        )
        duration = time.time() - start_time
        
        print(f"⏱️ Total processing time: {duration:.2f} seconds")
        
        if result['success']:
            print(f"\n✅ Image generation successful!")
            print(f"📁 Output saved to: {result['output_path']}")
            print(f"📝 Generated prompt length: {len(result['generated_text'])} characters")
            
            # 生成されたプロンプトの表示
            prompt_preview = result['generated_text'][:300]
            if len(result['generated_text']) > 300:
                prompt_preview += "..."
            print(f"📖 Generated prompt:\n   {prompt_preview}")
            
            # 画像生成結果の詳細
            if result.get('image_result'):
                img_result = result['image_result']
                if img_result['success']:
                    print(f"\n🖼️ Image generation details:")
                    print(f"   ✅ Image file: {img_result['image_path']}")
                    print(f"   📊 File size: {img_result['image_size'] / 1024:.1f} KB")
                    print(f"   ⏱️ Image generation time: {img_result['generation_time']:.2f} seconds")
                    print(f"   📐 Expected size: {generation_config.image_width}×{generation_config.image_height}")
                    
                    # ファイルの存在確認
                    if os.path.exists(img_result['image_path']):
                        actual_file_size = os.path.getsize(img_result['image_path'])
                        print(f"   ✅ File verified on disk (size: {actual_file_size} bytes)")
                        
                        # ファイル名の分析
                        filename = os.path.basename(img_result['image_path'])
                        print(f"   📄 Generated filename: {filename}")
                        
                        print(f"\n🎯 Success! Generated 1024×768 image:")
                        print(f"   📁 Full path: {img_result['image_path']}")
                        print(f"   📊 Size comparison:")
                        print(f"      - Old default (512×512): {512*512:,} pixels")
                        print(f"      - New default (1024×768): {1024*768:,} pixels")
                        print(f"      - Increase: {(1024*768)/(512*512):.1f}x more pixels")
                        
                        return True
                        
                    else:
                        print(f"   ❌ Generated image file not found on disk!")
                        return False
                        
                else:
                    print(f"\n❌ Image generation failed: {img_result['error']}")
                    return False
            else:
                print(f"\n⚠️ No image generation result in response")
                return False
                
        else:
            print(f"\n❌ Content generation failed: {result['error']}")
            if 'metadata' in result:
                print(f"   Error details: {result['metadata']}")
            return False
            
    except Exception as e:
        duration = time.time() - start_time
        print(f"⏱️ Failed after: {duration:.2f} seconds")
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_size_comparison():
    """異なるサイズでの比較テスト"""
    print(f"\n\n🔄 Size Comparison Test")
    print("=" * 60)
    
    # 同じSIS data
    sample_sis = {
        "summary": "A cozy cottage in a flower garden during spring",
        "emotions": ["warm", "cozy", "cheerful"],
        "mood": "welcoming and peaceful",
        "themes": ["home", "garden", "spring", "flowers"],
        "narrative": {
            "characters": [],
            "location": "Rural cottage with blooming garden",
            "weather": "Pleasant spring day",
            "tone": "cheerful and inviting",
            "style": "cottage core aesthetic"
        },
        "visual": {
            "style": "charming cottage photography",
            "composition": "cottage surrounded by colorful flowers",
            "lighting": "soft natural daylight",
            "perspective": "garden path view",
            "colors": ["pastel pink", "lavender", "soft green", "cream white"]
        }
    }
    
    test_configs = [
        {"name": "Old Default", "width": 512, "height": 512},
        {"name": "New Default", "width": 1024, "height": 768},
        {"name": "HD Square", "width": 1024, "height": 1024}
    ]
    
    results = []
    
    for config in test_configs:
        print(f"\n🎨 Testing {config['name']} ({config['width']}×{config['height']})...")
        
        # 設定作成
        api_config = APIConfig()
        generation_config = GenerationConfig(
            image_width=config['width'],
            image_height=config['height']
        )
        
        start_time = time.time()
        result = generate_content(
            sample_sis,
            'image',
            api_config=api_config,
            generation_config=generation_config,
            test_case_name=f"comparison_{config['name'].lower().replace(' ', '_')}"
        )
        duration = time.time() - start_time
        
        print(f"   ⏱️ Generation time: {duration:.2f} seconds")
        
        if result['success'] and result.get('image_result', {}).get('success'):
            img_result = result['image_result']
            file_size_kb = img_result['image_size'] / 1024
            pixel_count = config['width'] * config['height']
            
            print(f"   ✅ Success: {file_size_kb:.1f} KB, {pixel_count:,} pixels")
            
            results.append({
                'name': config['name'],
                'width': config['width'],
                'height': config['height'],
                'duration': duration,
                'file_size': img_result['image_size'],
                'pixel_count': pixel_count,
                'success': True
            })
        else:
            error_msg = result.get('error', 'Unknown error')
            if result.get('image_result'):
                error_msg = result['image_result'].get('error', error_msg)
            print(f"   ❌ Failed: {error_msg}")
            
            results.append({
                'name': config['name'],
                'width': config['width'],
                'height': config['height'],
                'duration': duration,
                'success': False,
                'error': error_msg
            })
    
    # 結果比較
    successful_results = [r for r in results if r['success']]
    if len(successful_results) >= 2:
        print(f"\n📊 Comparison Summary:")
        print(f"{'Size':<15} {'Time (s)':<10} {'File (KB)':<12} {'Pixels':<12} {'Status'}")
        print("-" * 60)
        
        for result in results:
            if result['success']:
                print(f"{result['width']}×{result['height']:<7} "
                      f"{result['duration']:<10.1f} "
                      f"{result['file_size']/1024:<12.1f} "
                      f"{result['pixel_count']:<12,} "
                      f"✅")
            else:
                print(f"{result['width']}×{result['height']:<7} "
                      f"{result['duration']:<10.1f} "
                      f"{'—':<12} "
                      f"{result['width']*result['height']:<12,} "
                      f"❌")


def main():
    """メイン実行"""
    print("🚀 Default Image Generation Test (Direct)")
    print("=" * 60)
    print(f"Testing new default image size: 1024×768")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 直接画像生成テスト
    success = test_direct_image_generation()
    
    if success:
        print(f"\n✅ Default size test successful!")
        
        # サイズ比較テスト
        test_size_comparison()
        
        print(f"\n🎉 All tests completed!")
        print(f"\n💡 The new default image size (1024×768) is now active.")
        print(f"   This provides {(1024*768)/(512*512):.1f}x more pixels than the old default (512×512).")
    else:
        print(f"\n❌ Default size test failed.")
        print(f"   Please check that both 'unsloth' and 'sd' services are running:")
        print(f"   docker-compose up -d unsloth sd")


if __name__ == "__main__":
    main()
