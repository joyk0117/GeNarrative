#!/usr/bin/env python3
"""
Unified Implementation Test Script

統一された content2sis と  の実装をテストします。

Usage:
    python test_unified_implementation.py
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# 統一実装のインポート
from common_base import APIConfig, ProcessingConfig, GenerationConfig
from content2sis_unified import extract_sis_from_content, audio2SIS, image2SIS, text2SIS
from _unified import generate_content, generate_content_with_unsloth


def test_content2sis_unified():
    """統一された content2sis のテスト"""
    print("🧪 Testing Content2SIS Unified Implementation")
    print("=" * 60)
    
    # テストファイルパス（実際のファイルが存在する場合のみテスト）
    test_files = [
        ("/app/shared/music_0264b049.wav", "audio"),
        ("/app/shared/image/story_image_20250726_094413.png", "image"),
        ("/app/shared/text/text_20250804_230132.txt", "text")
    ]
    
    results = []
    
    for file_path, expected_type in test_files:
        if not os.path.exists(file_path):
            print(f"⚠️ Test file not found: {file_path}")
            continue
        
        print(f"\n🔍 Testing {expected_type} file: {os.path.basename(file_path)}")
        
        # 統一エントリーポイントのテスト
        start_time = time.time()
        result = extract_sis_from_content(file_path)
        duration = time.time() - start_time
        
        print(f"⏱️ Processing time: {duration:.2f} seconds")
        
        if result['success']:
            print("✅ SIS extraction successful!")
            sis_data = result['sis_data']
            print(f"📊 SIS summary: {sis_data.get('summary', 'N/A')[:100]}...")
            print(f"🎭 Emotions: {', '.join(sis_data.get('emotions', [])[:3])}")
            print(f"🌟 Mood: {sis_data.get('mood', 'N/A')}")
            
            # 後方互換性テスト
            print(f"\n🔄 Testing backward compatibility...")
            if expected_type == "audio":
                compat_result = audio2SIS(file_path)
            elif expected_type == "image":
                compat_result = image2SIS(file_path)
            elif expected_type == "text":
                compat_result = text2SIS(file_path)
            
            if compat_result['success']:
                print("✅ Backward compatibility: OK")
            else:
                print(f"❌ Backward compatibility failed: {compat_result['error']}")
            
            results.append({
                'file_path': file_path,
                'content_type': expected_type,
                'success': True,
                'duration': duration,
                'sis_data': sis_data
            })
        else:
            print(f"❌ SIS extraction failed: {result['error']}")
            results.append({
                'file_path': file_path,
                'content_type': expected_type,
                'success': False,
                'error': result['error']
            })
    
    return results


def test__unified(sis_results: List[Dict[str, Any]]):
    """統一された  のテスト"""
    print("\n\n🧪 Testing SIS2Content Unified Implementation")
    print("=" * 60)
    
    # 成功したSIS抽出結果を使用
    successful_sis = [r for r in sis_results if r['success']]
    
    if not successful_sis:
    print("❌ No successful SIS results to test with")
        return []
    
    # テスト用のSIS data（サンプル）
    sample_sis = {
        "summary": "A peaceful mountain landscape with gentle flowing water",
        "emotions": ["calm", "peaceful", "serene"],
        "mood": "tranquil",
        "themes": ["nature", "harmony", "solitude"],
        "narrative": {
            "characters": ["lone traveler"],
            "location": "mountain valley with stream",
            "weather": "clear sunny day",
            "tone": "contemplative",
            "style": "nature documentary"
        },
        "visual": {
            "style": "photorealistic landscape",
            "composition": "wide angle mountain view",
            "lighting": "soft golden hour light",
            "perspective": "elevated viewpoint",
            "colors": ["emerald green", "sky blue", "golden yellow"]
        },
        "audio": {
            "genre": "ambient nature sounds",
            "tempo": "slow and flowing",
            "instruments": ["acoustic guitar", "flute", "nature sounds"],
            "structure": "ambient soundscape"
        }
    }
    
    content_types = ['text', 'image', 'music', 'tts']
    results = []
    
    # 設定クラスの作成
    api_config = APIConfig()
    generation_config = GenerationConfig(
        text_word_count=30,  # テスト用に短く
        image_width=256,     # テスト用に小さく
        image_height=256,
        music_duration=15    # テスト用に短く
    )
    
    for content_type in content_types:
        print(f"\n🎨 Testing {content_type} generation...")
        
        # 利用可能なSIS dataを選択
        if successful_sis:
            test_sis = successful_sis[0]['sis_data']
        else:
            test_sis = sample_sis
        
        # TTSモードの特別処理
        if content_type == 'tts':
            # TTSテスト用の設定
            from _unified import ContentGenerator
            
            generator = ContentGenerator(
                api_config=api_config,
                generation_config=generation_config
            )
            
            # テスト用英語テキスト
            test_text = "Hello, this is a test of the text to speech functionality."
            
            print(f"📝 Testing with text: {test_text}")
            
            # TTS機能のテスト
            start_time = time.time()
            tts_result = generator.text2speech(
                test_text,
                test_case_name=f"test_{content_type}",
                output_filename="test_speech"
            )
            duration = time.time() - start_time
            
            print(f"⏱️ Processing time: {duration:.2f} seconds")
            
            if tts_result['success']:
                print(f"✅ TTS generation successful!")
                print(f"📁 Audio output: {tts_result['audio_path']}")
                print(f"📊 File size: {tts_result['audio_size'] / 1024:.1f}KB")
                print(f"📝 Text length: {tts_result['text_length']} characters")
                print(f"🎵 Play command: aplay {tts_result['audio_path']}")
                
                # SISベースのTTSテストも追加
                print(f"\n🔄 Testing SIS-based TTS generation...")
                start_time_sis = time.time()
                result = generate_content(
                    test_sis,
                    'tts',
                    api_config=api_config,
                    generation_config=generation_config,
                    test_case_name=f"test_{content_type}_sis"
                )
                duration_sis = time.time() - start_time_sis
                
                if result['success']:
                    print(f"✅ SIS-based TTS successful!")
                    print(f"📁 Audio output: {result.get('audio_path', 'N/A')}")
                    print(f"⏱️ Total processing time: {duration_sis:.2f} seconds")
                else:
                    print(f"❌ SIS-based TTS failed: {result['error']}")
                
                results.append({
                    'content_type': content_type,
                    'success': True,
                    'duration': duration,
                    'output_path': tts_result['audio_path'],
                    'audio_size': tts_result['audio_size']
                })
            else:
                print(f"❌ TTS generation failed: {tts_result['error']}")
                results.append({
                    'content_type': content_type,
                    'success': False,
                    'error': tts_result['error']
                })
            
            continue
        
        # 統一エントリーポイントのテスト
        start_time = time.time()
        result = generate_content(
            test_sis,
            content_type,
            api_config=api_config,
            generation_config=generation_config,
            test_case_name=f"test_{content_type}"
        )
        duration = time.time() - start_time
        
        print(f"⏱️ Processing time: {duration:.2f} seconds")
        
        if result['success']:
            print(f"✅ {content_type.title()} generation successful!")
            print(f"📁 Output: {result['output_path']}")
            print(f"📝 Generated text length: {len(result['generated_text'])} chars")
            
            # 生成されたコンテンツのプレビュー
            preview = result['generated_text'][:100]
            if len(result['generated_text']) > 100:
                preview += "..."
            print(f"📖 Preview: {preview}")
            
            # 追加生成結果の確認
            if result.get('image_result'):
                img_result = result['image_result']
                status = "✅" if img_result['success'] else "❌"
                print(f"{status} Image generation: {img_result.get('error', 'Success')}")
            
            if result.get('music_result'):
                music_result = result['music_result']
                status = "✅" if music_result['success'] else "❌"
                print(f"{status} Music generation: {music_result.get('error', 'Success')}")
            
            # 後方互換性テスト
            print(f"\n🔄 Testing backward compatibility...")
            compat_result = generate_content_with_unsloth(
                test_sis,
                api_config.unsloth_uri,
                content_type,
                test_case_name=f"compat_{content_type}"
            )
            
            if compat_result['success']:
                print("✅ Backward compatibility: OK")
            else:
                print(f"❌ Backward compatibility failed: {compat_result['error']}")
            
            results.append({
                'content_type': content_type,
                'success': True,
                'duration': duration,
                'output_path': result['output_path']
            })
        else:
            print(f"❌ {content_type.title()} generation failed: {result['error']}")
            results.append({
                'content_type': content_type,
                'success': False,
                'error': result['error']
            })
    
    return results


def test_tts_functionality():
    """TTS機能の専用テスト"""
    print("\n\n🎤 Testing TTS (Text-to-Speech) Functionality")
    print("=" * 60)
    
    from _unified import ContentGenerator
    
    # 設定の作成
    api_config = APIConfig()
    generation_config = GenerationConfig()
    
    generator = ContentGenerator(
        api_config=api_config,
        generation_config=generation_config
    )
    
    # テストケース
    test_cases = [
        {
            'name': 'Short English text',
            'text': 'Hello world.',
            'filename': 'short_test'
        },
        {
            'name': 'Medium English text',
            'text': 'This is a medium length test sentence for text to speech conversion.',
            'filename': 'medium_test'
        },
        {
            'name': 'Long English text',
            'text': 'This is a longer test sentence that contains multiple clauses and should provide a good test of the text to speech system with various words and punctuation marks.',
            'filename': 'long_test'
        },
        {
            'name': 'Text with numbers',
            'text': 'The year is 2025 and there are 365 days in this year.',
            'filename': 'numbers_test'
        },
        {
            'name': 'Text with punctuation',
            'text': 'Hello! How are you today? I hope you are doing well. This is a test.',
            'filename': 'punctuation_test'
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test {i}/{len(test_cases)}: {test_case['name']}")
        print(f"📝 Text: {test_case['text']}")
        
        start_time = time.time()
        result = generator.text2speech(
            test_case['text'],
            test_case_name=f"tts_test_{i}",
            output_filename=test_case['filename']
        )
        duration = time.time() - start_time
        
        print(f"⏱️ Processing time: {duration:.2f} seconds")
        
        if result['success']:
            print(f"✅ TTS successful!")
            print(f"📁 Audio file: {result['audio_path']}")
            print(f"📊 File size: {result['audio_size'] / 1024:.1f}KB")
            print(f"📏 Text length: {result['text_length']} characters")
            print(f"🎵 Play: aplay {result['audio_path']}")
            
            # ファイルの存在確認
            if os.path.exists(result['audio_path']):
                file_size = os.path.getsize(result['audio_path'])
                print(f"✅ File verified (size: {file_size} bytes)")
            else:
                print(f"❌ Generated file not found!")
            
            results.append({
                'test_name': test_case['name'],
                'success': True,
                'duration': duration,
                'audio_path': result['audio_path'],
                'audio_size': result['audio_size'],
                'text_length': result['text_length']
            })
        else:
            print(f"❌ TTS failed: {result['error']}")
            results.append({
                'test_name': test_case['name'],
                'success': False,
                'error': result['error'],
                'duration': duration
            })
    
    # 結果サマリー
    successful_tests = len([r for r in results if r['success']])
    print(f"\n📊 TTS Test Summary:")
    print(f"✅ Successful: {successful_tests}/{len(test_cases)}")
    
    if successful_tests > 0:
        avg_duration = sum(r['duration'] for r in results if r['success']) / successful_tests
        avg_size = sum(r.get('audio_size', 0) for r in results if r['success']) / successful_tests
        print(f"⏱️ Average generation time: {avg_duration:.2f} seconds")
        print(f"📊 Average file size: {avg_size / 1024:.1f}KB")
    
    return results


def test_tts_error_handling():
    """TTSエラーハンドリングのテスト"""
    print("\n\n🧪 Testing TTS Error Handling")
    print("=" * 60)
    
    from _unified import ContentGenerator
    
    # 無効なAPI設定でテスト
    invalid_api_config = APIConfig(tts_uri="http://invalid:9999")
    generator = ContentGenerator(api_config=invalid_api_config)
    
    test_cases = [
        {
            'name': 'Invalid TTS server',
            'text': 'This should fail due to invalid server',
            'expected_error': 'TTS server is not available'
        },
        {
            'name': 'Empty text',
            'text': '',
            'expected_error': None  # 空テキストの挙動確認
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🔍 Testing: {test_case['name']}")
        print(f"📝 Text: '{test_case['text']}'")
        
        result = generator.text2speech(test_case['text'])
        
        if not result['success']:
            print(f"✅ Error handled correctly: {result['error']}")
            if test_case['expected_error'] and test_case['expected_error'] in result['error']:
                print(f"✅ Expected error message found")
        else:
            if test_case['expected_error']:
                print(f"❌ Expected error but got success")
            else:
                print(f"✅ Unexpected success (empty text handled)")
    
    # 正常なAPI設定に戻してサーバー接続テスト
    print(f"\n🔍 Testing TTS server connectivity...")
    normal_api_config = APIConfig()
    normal_generator = ContentGenerator(api_config=normal_api_config)
    
    # サーバー確認のみ
    if normal_generator._check_tts_server():
        print(f"✅ TTS server is accessible at {normal_api_config.tts_uri}")
    else:
        print(f"❌ TTS server is not accessible at {normal_api_config.tts_uri}")
        print(f"💡 Make sure TTS service is running: docker-compose up -d tts")


def test_error_handling():
    """エラーハンドリングのテスト"""
    print("\n\n🧪 Testing Error Handling")
    print("=" * 60)
    
    test_cases = [
        {
            'name': 'Non-existent file',
            'func': lambda: extract_sis_from_content('/nonexistent/file.txt'),
            'expected_error': 'FILE_NOT_FOUND'
        },
        {
            'name': 'Invalid content type',
            'func': lambda: generate_content({}, 'invalid_type'),
            'expected_error': 'UNSUPPORTED_CONTENT_TYPE'
        },
        {
            'name': 'Empty SIS data',
            'func': lambda: generate_content({}, 'text'),
            'expected_error': 'INCOMPLETE_SIS_DATA'
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🔍 Testing: {test_case['name']}")
        
        try:
            result = test_case['func']()
            
            if not result['success']:
                print(f"✅ Error handled correctly: {result['error']}")
                
                # エラーコードの確認
                if 'metadata' in result and 'error_code' in result['metadata']:
                    error_code = result['metadata']['error_code']
                    print(f"📊 Error code: {error_code}")
                    
                    if test_case['expected_error'] in error_code:
                        print("✅ Expected error code found")
                    else:
                        print(f"⚠️ Unexpected error code (expected: {test_case['expected_error']})")
            else:
                print("❌ Error should have occurred but didn't")
                
        except Exception as e:
            print(f"❌ Unexpected exception: {e}")


def generate_test_report(sis_results: List[Dict[str, Any]], content_results: List[Dict[str, Any]], tts_results: List[Dict[str, Any]] = None):
    """テスト結果レポートの生成"""
    print("\n\n📊 Test Report Summary")
    print("=" * 60)
    
    # SIS抽出結果
    sis_success = len([r for r in sis_results if r['success']])
    sis_total = len(sis_results)
    print(f"📥 Content2SIS: {sis_success}/{sis_total} successful")
    
    if sis_results:
        avg_sis_time = sum(r.get('duration', 0) for r in sis_results) / len(sis_results)
    print(f"⏱️ Average SIS extraction time: {avg_sis_time:.2f} seconds")
    
    # コンテンツ生成結果
    content_success = len([r for r in content_results if r['success']])
    content_total = len(content_results)
    print(f"📤 SIS2Content: {content_success}/{content_total} successful")
    
    if content_results:
        avg_content_time = sum(r.get('duration', 0) for r in content_results) / len(content_results)
        print(f"⏱️ Average content generation time: {avg_content_time:.2f} seconds")
    
    # TTS結果
    if tts_results:
        tts_success = len([r for r in tts_results if r['success']])
        tts_total = len(tts_results)
        print(f"🎤 TTS: {tts_success}/{tts_total} successful")
        
        if tts_success > 0:
            avg_tts_time = sum(r.get('duration', 0) for r in tts_results if r['success']) / tts_success
            avg_tts_size = sum(r.get('audio_size', 0) for r in tts_results if r['success']) / tts_success
            print(f"⏱️ Average TTS generation time: {avg_tts_time:.2f} seconds")
            print(f"📊 Average TTS file size: {avg_tts_size / 1024:.1f}KB")
    else:
        tts_success = 0
        tts_total = 0
    
    # 総合評価
    total_success = sis_success + content_success + tts_success
    total_tests = sis_total + content_total + tts_total
    success_rate = (total_success / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n🎯 Overall Success Rate: {success_rate:.1f}% ({total_success}/{total_tests})")
    
    if success_rate >= 80:
        print("🎉 Test suite passed!")
    elif success_rate >= 60:
        print("⚠️ Test suite partially successful")
    else:
        print("❌ Test suite needs improvement")
    
    # 詳細レポートの保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"/workspaces/GeNarrative-dev/dev/scripts/test_report_{timestamp}.json"
    
    report_data = {
        'timestamp': timestamp,
        'sis_results': sis_results,
        'content_results': content_results,
        'tts_results': tts_results or [],
        'summary': {
            'sis_success_rate': sis_success / sis_total if sis_total > 0 else 0,
            'content_success_rate': content_success / content_total if content_total > 0 else 0,
            'tts_success_rate': tts_success / tts_total if tts_total > 0 else 0,
            'overall_success_rate': success_rate / 100
        }
    }
    
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"📄 Detailed report saved: {report_path}")
    except Exception as e:
        print(f"⚠️ Failed to save report: {e}")


def main():
    """メインテスト実行"""
    print("🚀 Starting Unified Implementation Test Suite")
    print("=" * 60)
    
    # Content2SIS のテスト
    sis_results = test_content2sis_unified()
    
    # SIS2Content のテスト
    content_results = test__unified(sis_results)
    
    # TTS機能の専用テスト
    tts_results = test_tts_functionality()
    
    # TTSエラーハンドリングのテスト
    test_tts_error_handling()
    
    # エラーハンドリングのテスト
    test_error_handling()
    
    # テストレポートの生成（TTS結果も含める）
    generate_test_report(sis_results, content_results, tts_results)
    
    print("\n🏁 Test suite completed!")


if __name__ == "__main__":
    main()
