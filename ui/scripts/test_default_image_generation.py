#!/usr/bin/env python3
"""
デフォルト値での画像生成テスト

新しいデフォルト値 1024×768 での画像生成をテストします。
"""

import os
import time
from datetime import datetime

# 統一実装のインポート
from common_base import APIConfig, ProcessingConfig, GenerationConfig
from _unified import generate_content, ContentGenerator


def test_default_image_generation():
    """デフォルト値での画像生成テスト"""
    print("🎨 Testing Default Image Generation (1024×768)")
    print("=" * 60)
    
    # テスト用のSIS data
    sample_sis = {
        "summary": "A serene mountain landscape with a crystal clear lake reflecting snow-capped peaks",
        "emotions": ["peaceful", "majestic", "inspiring"],
        "mood": "tranquil and breathtaking",
        "themes": ["nature", "mountains", "reflection", "serenity"],
        "narrative": {
            "characters": [],
            "location": "High mountain valley with alpine lake",
            "weather": "Clear day with gentle breeze",
            "tone": "contemplative and awe-inspiring",
            "style": "nature photography"
        },
        "visual": {
            "style": "photorealistic landscape photography",
            "composition": "wide panoramic view with lake in foreground",
            "lighting": "golden hour soft lighting",
            "perspective": "slightly elevated viewpoint",
            "colors": ["deep blue", "snow white", "golden yellow", "emerald green"]
        },
        "audio": {
            "genre": "ambient nature",
            "tempo": "slow and peaceful",
            "instruments": ["wind sounds", "water lapping", "distant birds"],
            "structure": "continuous ambient soundscape"
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
    print(f"   Output dir: {processing_config.output_dir}")
    
    # サーバー状態確認
    print(f"\n🔍 Checking server status...")
    generator = ContentGenerator(api_config, processing_config, generation_config)
    
    if generator._check_sd_server():
        print("✅ Stable Diffusion server is accessible")
    else:
        print("❌ Stable Diffusion server is not accessible")
        print("💡 Make sure SD service is running: docker-compose up -d sd")
        return False
    
    if generator._check_unsloth_server():
        print("✅ Unsloth server is accessible")
    else:
        print("❌ Unsloth server is not accessible")
        print("💡 Make sure Unsloth service is running: docker-compose up -d unsloth")
        return False
    
    # 画像生成テスト実行
    print(f"\n🎨 Starting image generation with default size...")
    
    start_time = time.time()
    result = generate_content(
        sample_sis,
        'image',
        api_config=api_config,
        processing_config=processing_config,
        generation_config=generation_config,
        test_case_name="default_size_test"
    )
    duration = time.time() - start_time
    
    print(f"⏱️ Total processing time: {duration:.2f} seconds")
    
    if result['success']:
        print(f"\n✅ Image generation successful!")
        print(f"📁 Output saved to: {result['output_path']}")
        print(f"📝 Generated prompt length: {len(result['generated_text'])} characters")
        
        # 生成されたプロンプトの表示
        prompt_preview = result['generated_text'][:200]
        if len(result['generated_text']) > 200:
            prompt_preview += "..."
        print(f"📖 Generated prompt preview:\n   {prompt_preview}")
        
        # 画像生成結果の詳細
        if result.get('image_result'):
            img_result = result['image_result']
            if img_result['success']:
                print(f"\n🖼️ Image generation details:")
                print(f"   ✅ Image file: {img_result['image_path']}")
                print(f"   📊 File size: {img_result['image_size'] / 1024:.1f} KB")
                print(f"   ⏱️ Generation time: {img_result['generation_time']:.2f} seconds")
                print(f"   📐 Expected size: {generation_config.image_width}×{generation_config.image_height}")
                
                # ファイルの存在確認
                if os.path.exists(img_result['image_path']):
                    actual_size = os.path.getsize(img_result['image_path'])
                    print(f"   ✅ File verified (actual size: {actual_size} bytes)")
                    
                    # 画像ファイルの詳細情報
                    try:
                        from PIL import Image
                        with Image.open(img_result['image_path']) as img:
                            width, height = img.size
                            print(f"   📏 Actual image dimensions: {width}×{height}")
                            if width == generation_config.image_width and height == generation_config.image_height:
                                print("   ✅ Image dimensions match expected size")
                            else:
                                print("   ⚠️ Image dimensions differ from expected size")
                    except ImportError:
                        print("   ⚠️ PIL not available for dimension verification")
                    except Exception as e:
                        print(f"   ⚠️ Could not verify image dimensions: {e}")
                    
                    print(f"\n🎯 To view the generated image:")
                    print(f"   file://{img_result['image_path']}")
                    
                else:
                    print(f"   ❌ Generated image file not found!")
                    
            else:
                print(f"\n❌ Image generation failed: {img_result['error']}")
                return False
        else:
            print(f"\n⚠️ No image generation result in response")
            return False
        
        return True
        
    else:
        print(f"\n❌ Content generation failed: {result['error']}")
        return False


def test_comparison_with_old_default():
    """旧デフォルト値との比較テスト"""
    print(f"\n\n🔄 Comparison Test: New Default vs Old Default")
    print("=" * 60)
    
    # 同じSIS data
    sample_sis = {
        "summary": "A vintage library with warm lighting and old books",
        "emotions": ["nostalgic", "cozy", "scholarly"],
        "mood": "warm and intellectual",
        "themes": ["knowledge", "history", "learning"],
        "narrative": {
            "characters": ["elderly librarian"],
            "location": "Historic university library",
            "weather": "Indoor, warm ambiance",
            "tone": "scholarly and peaceful",
            "style": "academic setting"
        },
        "visual": {
            "style": "warm interior photography",
            "composition": "library shelves with reading area",
            "lighting": "soft warm lamplight",
            "perspective": "eye level view",
            "colors": ["warm brown", "golden yellow", "deep red", "cream white"]
        }
    }
    
    # 新デフォルト値での生成
    print(f"\n🆕 Testing with NEW default (1024×768)...")
    api_config = APIConfig()
    new_generation_config = GenerationConfig()  # 新デフォルト値
    
    start_time = time.time()
    new_result = generate_content(
        sample_sis,
        'image',
        api_config=api_config,
        generation_config=new_generation_config,
        test_case_name="new_default_comparison"
    )
    new_duration = time.time() - start_time
    
    # 旧デフォルト値での生成
    print(f"\n🔄 Testing with OLD default (512×512) for comparison...")
    old_generation_config = GenerationConfig(
        image_width=512,
        image_height=512
    )
    
    start_time = time.time()
    old_result = generate_content(
        sample_sis,
        'image',
        api_config=api_config,
        generation_config=old_generation_config,
        test_case_name="old_default_comparison"
    )
    old_duration = time.time() - start_time
    
    # 結果の比較
    print(f"\n📊 Comparison Results:")
    print(f"   🆕 New default (1024×768): {'✅ Success' if new_result['success'] else '❌ Failed'}")
    print(f"      ⏱️ Generation time: {new_duration:.2f} seconds")
    if new_result['success'] and new_result.get('image_result', {}).get('success'):
        new_img = new_result['image_result']
        print(f"      📊 File size: {new_img['image_size'] / 1024:.1f} KB")
    
    print(f"   🔄 Old default (512×512): {'✅ Success' if old_result['success'] else '❌ Failed'}")
    print(f"      ⏱️ Generation time: {old_duration:.2f} seconds")
    if old_result['success'] and old_result.get('image_result', {}).get('success'):
        old_img = old_result['image_result']
        print(f"      📊 File size: {old_img['image_size'] / 1024:.1f} KB")
    
    if (new_result['success'] and old_result['success'] and 
        new_result.get('image_result', {}).get('success') and 
        old_result.get('image_result', {}).get('success')):
        
        new_img = new_result['image_result']
        old_img = old_result['image_result']
        
        size_ratio = new_img['image_size'] / old_img['image_size']
        time_ratio = new_duration / old_duration
        
        print(f"\n📈 Performance Comparison:")
        print(f"   📊 File size ratio (new/old): {size_ratio:.2f}x")
        print(f"   ⏱️ Time ratio (new/old): {time_ratio:.2f}x")
        print(f"   🎯 Resolution increase: {(1024*768)/(512*512):.2f}x pixels")


def main():
    """メイン実行"""
    print("🚀 Default Image Generation Test")
    print("=" * 60)
    print(f"Testing new default image size: 1024×768")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # デフォルト値での画像生成テスト
    success = test_default_image_generation()
    
    if success:
        # 比較テスト
        test_comparison_with_old_default()
        print(f"\n🎉 All tests completed successfully!")
    else:
        print(f"\n❌ Basic test failed. Skipping comparison test.")
    
    print(f"\n📝 Note: Make sure both 'unsloth' and 'sd' services are running:")
    print(f"   docker-compose up -d unsloth sd")


if __name__ == "__main__":
    main()
