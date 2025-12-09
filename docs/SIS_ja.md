# 🧩 GeNarrative – Semantic Interface Structure (SIS) 仕様書

## 🎯 1. 概要（Overview）

Semantic Interface Structure（SIS）は、**「作品やシーンの意味情報」を取り出し、生成・検索・再利用の“ハブ”にする中間表現**です。
「何を作るか（意味）」と「どう作るか（モデル・プロンプト）」を分離し、生成・検索・学習の全フェーズで共通言語として機能します。

### 主なメリット

1.  **モジュール分離 & コントロール性**
    *   意味（SIS）は固定したまま、モデル（SD/MusicGen等）やパラメータだけを差し替え可能。
2.  **再現性・説明性**
    *   「どんな意味指定から生まれたか」をJSONで完全記録。出所確認や再生成の基盤となる。
3.  **編集しやすい“つまみ”と人手補正**
    *   LLMの抽出が不完全でも、構造化されたデータなので人手で容易に修正・補完が可能。
    *   意味（SIS）を調整するだけで、画風やテンポなどの微調整も簡単に行える。
4.  **検索・推薦の共通インターフェース**
    *   テキスト・画像・音楽を横断して、「しんみり＋夜＋ピアノ」のような意味ベースの検索・推薦が可能。
5.  **学習データ・評価の基盤**
    *   SISを正解データとして、プロンプト生成、QAペア作成、モデルの自動評価（整合性判定）に活用できる。
6.  **ベクトルDB・他モデルのハブ**
    *   SISの各要素をベクトル化し、外部DBやEmbeddingモデルとの橋渡し役となる。
7.  **リソース制限対策**
  *   重い生成（高解像度画像・長尺BGM・動画など）を段階的に分割・後回しにでき、一部モーダルだけの作り直しも可能。

## 🏗 2. レイヤ構造（Story / Scene の二層）

GeNarrative のスコープでは、SISは以下の2種類のオブジェクトで構成されます：

### StorySIS（上位）

- 作品全体の意味構造を保持するオブジェクト。
- ストーリーの基本情報（タイトルなど）
- ストーリータイプ（起承転結、三幕構成など）
- キャラクター設定
- 各シーンの一覧と役割（role）
- 作品全体のスタイル方針（文体・画風・音楽方針）

### SceneSIS（下位）

- 作品を構成する 最小意味単位（1シーン） を表すオブジェクト。
- シーンの意味（summary, emotions など）
- テキスト生成パラメータ
- ビジュアル生成パラメータ（image/video）
- オーディオ生成パラメータ（music/speech/sfx）
- SceneSIS は 1 行1 JSON の JSONL ファイルとして保存されます。
 - 再利用性のため、SceneSIS には story_id は含めません（同一シーンを複数ストーリーで使い回せます）。

## 📘 3. StorySIS 仕様

### 3.1 StorySIS – JSON スキーマ（概念）

```jsonc
{
  "sis_type": "story",
  "story_id": "string",
  "title": "string or null",
  "summary": "string or null",

  // ストーリー構造タイプ（必須）
  "story_type": "kishotenketsu", 
  // 例: "kishotenketsu" | "three_act" | "three_attempts" | "circular"

  // 作品全体のテーマ
  "themes": ["trust", "learning"],

  // 登場キャラクター
  "characters": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Nancy",
      "traits": ["girl", "curious"],
      "visual": {
        "hair": "brown curly hair",
        "clothes": "striped shirt and purple skirt"
      }
    }
  ],

  // シーン一覧（構成情報を兼ねる）
  "scenes": [
    {
      "scene_id": "123e4567-e89b-12d3-a456-426614174000",
      "role": "ki",       // 起
      "summary": "Introduction of the girl and the forest."
    }
  ]
}
```

### 3.2 フィールド詳細

| フィールド            | 型     | 説明                                                   |
|-----------------------|--------|--------------------------------------------------------|
| story_type            | string | ストーリー構造の種類（例：起承転結）                  |
| themes                 | array  | 作品全体のテーマ            |
| scenes[].role         | string | そのシーンの役割（例：ki/sho/ten/ketsu）              |
| characters[]          | array  | キャラクターの特徴・外見情報                     |


### 3.3 story_type 標準値

| story_type       | roles（scene.role）                                 |
|------------------|-----------------------------------------------------|
| kishotenketsu    | ki / sho / ten / ketsu                              |
| three_act        | setup / conflict / resolution                       |
| three_attempts   | problem / attempt1 / attempt2 / attempt3 / result   |
| circular         | home_start / away / change / home_end               |

## 🎬 4. SceneSIS 仕様

SceneSIS は 1 シーンを記述する JSON オブジェクトです。
保存時は JSONL（1行1Scene） を推奨。

### 4.1 SceneSIS – JSON スキーマ（概念）

```jsonc
{
  "sis_type": "scene",
  // StorySISと一致
  "scene_id": "123e4567-e89b-12d3-a456-426614174000",
  "role": "ki",       // 起
  "summary": "Introduction of the girl and the forest.",
  
  // シーンの背景的意味（多モーダル共通）
  "semantics": {
    "mood": "calm",
    "characters": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Nancy",
        "visual": { "clothes": "raincoat" }
      }
    ],
    "location": "forest",
    "time": "day",
    "weather": "sunny"
  },

  // テキスト生成
  "text": {
    "mode": "narrative",   // narrative/expository/dialogue/caption/question
    "style": "simple",
    "language": "English",
    "tone": "gentle",
    "point_of_view": "third"
  },

  // 画像 / 動画生成
  "visual": {
    "mode": "image",       // image | video
    "style": "watercolor",
    "composition": "mid-shot",
    "lighting": "soft",
    "perspective": "eye-level"
  },

  // 音楽 / 音声 / 効果音
  "audio": {
    "mode": "music",       // music | speech | sfx | ambience
    "genre": "ambient",
    "tempo": "slow",
    "instruments": ["piano", "pad"]
  }
}
```

### 4.2 フィールド詳細

#### 4.2.1 共通フィールド

| フィールド | 説明           |
|------------|----------------|
| summary    | シーンの要約   |
| mood       | 空気感         |
| themes     | 主題           |

#### 4.2.2 semantics（シーンの意味情報）

画像・テキスト・音のすべてが参照する「意味の背景」

| フィールド   | 説明                                   |
|--------------|----------------------------------------|
| characters   | シーンに登場するキャラの詳細情報リスト（ID, 名前, 外見など）。シーン固有の服装などを記述可能 |
| location     | 場所名                                 |
| time         | 時間帯                                 |
| weather      | 天候                                   |

#### 4.2.3 text（テキスト生成）

| フィールド      | 説明                                  |
|-----------------|---------------------------------------|
| mode            | narrative / expository / dialogue など |
| style           | 文体                                  |
| tone            | 文のトーン                            |
| point_of_view   | 一人称/三人称など                     |

#### 4.2.4 visual（画像/動画生成）

| フィールド   | 説明                                  |
|--------------|---------------------------------------|
| mode         | image or video                        |
| style        | watercolor, anime, realistic など     |
| composition  | 構図                                  |
| lighting     | 光源・雰囲気                          |
| perspective  | 視点                                  |

#### 4.2.5 audio（音楽/音声/SE）

| フィールド   | 説明                                  |
|--------------|---------------------------------------|
| mode         | music / speech / sfx / ambience       |
| genre        | 音楽ジャンル                          |
| tempo        | 速度                                  |
| instruments  | 楽器リスト                            |

## 🔗 5. StorySIS と SceneSIS の関係

```
StorySIS
 ├── scenes[0] → SceneSIS(scene_001)
 ├── scenes[1] → SceneSIS(scene_002)
 ├── scenes[2] → SceneSIS(scene_003)
 ...
```

## 🚀 6. 応用例（Use Cases）

### A. GeNarrative内の典型ユースケース
*   **子どもの絵 → SIS抽出:** 画像から意味を抽出してSIS化し、そこからストーリー・BGMを生成。

### B. 既存コンテンツのカタログ化
*   市販絵本や青空文庫からSISを自動抽出し、「絵本レコメンド」や「場面に合うBGM検索」などの意味ラベリングに活用。

### C. 教育・研究系
*   同じSISで「画像だけ変える」「BGMだけ変える」実験を行い、学習効果への影響を検証する比較実験の基盤として利用。

### D. 評価プロトコルとの接続
*   SISを「正解の意味構造」とし、生成されたコンテンツがSISとどれだけ一致しているかを測定することで、モデルの定量評価を行う。

## 🛠 7. 保存形式

- StorySIS: `story.json`
- SceneSIS: `story_scenes.jsonl（1行1Scene）`

## 🧪 8. LLM生成ワークフロー（推奨）

1. StorySIS を生成（story_type に従い role を決定）
2. scenes[].scene_id に基づき SceneSIS を1つずつ生成
3. SceneSIS を JSONL に保存
4. SceneSIS → テキスト/画像/音楽/動画に変換

## 🎉 9. まとめ

本仕様と設計方針は、次の点を満たします：

- 起承転結などのストーリー構造を、StorySIS / SceneSIS で明示的に管理できる。
- Scene の意味＋生成条件を一貫して扱い、マルチモーダル生成に最適化されている。
- SIS を「生成インターフェース」と「評価インターフェース」の両方に用いることで、
  生成・検索・評価・再利用が同じ意味表現（SIS）上でつながる。


## 📎 付録A: SISベース評価と既存指標との関係

この章は、SIS を用いた自動評価指標の設計指針をまとめたものであり、SIS JSON フィールド自体の仕様ではありません。

### 9.1 SIS評価の基本イメージ

- Gold SIS（人間が確認・確定したSIS）を「正解」とみなす。
- 生成コンテンツ（テキスト／画像／音声／動画など）から Predicted SIS を再抽出し、Gold SIS と比較して評価する。
- 比較は「スロット単位」で行う（例：`scene.role`, `semantics.location`, `semantics.characters`, `semantics.mood`, `visual.style`, `audio.tempo` など）。
- その結果、単なる1つのスコアだけでなく、「どの要素が崩れているか／忠実か」を可視化できる評価になる。

### 9.2 SPICEなど既存指標との位置づけ

**SPICE の特徴**

- 参照キャプションと生成キャプションを依存文法解析し、シーングラフ（objects, attributes, relations）に変換。
- シーングラフ同士の F 値にもとづき、画像⇄テキスト（主に画像⇄キャプション）の意味的一致度を測る。
- 「意味構造ベースの評価」だが、対象は基本的に「キャプション文」に限定される。

**SISベース評価の特徴**

- 入力・出力の両方に JSON の意味構造（SIS）を使う。
- テキストだけでなく、画像・音声・動画など、すべてのモーダルを同じ SIS で評価できる。
- `story_type` や `scene.role` といったストーリー構造、`mood` や BGM の `tempo` などマルチモーダルな要素を含む、一貫した評価が可能。
- 構造的な発想は SPICE に近く、「SPICE 的な意味評価」をマルチモーダル＋ストーリー構造に拡張したもの、と位置づけられる。

### 9.3 Gold SIS とアノテーションコスト

**既存指標も Gold 作成コストを持つ**

- BLEU / ROUGE: 参照テキスト（ゴールド文）を書く必要がある。
- SPICE: 参照キャプションを書く必要があり、さらに研究側でパーサを回す前提がある。

**SIS の場合**

- `summary` は短い文章であり、参照キャプションに近い役割を果たす。
- それに加えて、`mood`, `location`, `characters`, `visual.style`, `audio.genre` などのスロットを埋めることで、キャプション＋ラベルを兼ねた構造になる。
- 人手でゼロから SIS を書くと、単純なキャプション記述より重い可能性は高い。
- ただし、**LLM でドラフトを生成 → 人間が修正する** というフローを前提にすれば、実務的に許容できるコストに収まりうる。
- いったん Gold SIS を作れば、評価だけでなく検索・生成制御・SIS DB などにも使い回せるため、「評価専用のキャプション」を用意する場合より投資回収率が高い。

**GeNarrative における前提**

- GeNarrative では、もともと生成の入力として SIS を標準的に用いる。
- そのため「作品内部の評価」に限れば、新たに Gold SIS を用意する追加コストはほぼ不要、という設計思想になっている。

### 9.4 SISベース評価のメリット／デメリット

**メリット**

- マルチモーダル＋ストーリー構造を、一貫した SIS で評価できる。
- スロット単位で一致度を見られるため、「どこが崩れたか／忠実か」が可視化される。
- Gold SIS は評価だけでなく、検索・生成制御・SIS DB 構築などにも再利用できる。

**デメリット / 課題**

- Gold SIS をゼロから人手で書くのは重い（→ LLM ドラフト＋人手修正で緩和）。
- 再抽出用モデル（VLM / LLM / 音楽タグ付けモデルなど）の品質に、評価精度が依存する（SPICE も同様にパーサ品質に依存）。

## 📎 付録B: 再抽出ループ：SIS → コンテンツ → SIS

この章は、SIS を評価と生成の両方のインターフェースとして使う際の、再抽出ループ設計の参考情報です。

SIS を「評価」と「生成」の両方のインターフェースにするため、生成後に再度 SIS を抽出して比較するループを前提とします。

### 10.1 基本ループ

1. **ターゲットSIS（Gold SIS）を決める**  
   手作り／既存作品からの抽出／UI 操作など、いずれの経路でもよい。
2. **SIS からコンテンツを生成**  
   - テキスト
   - 画像
   - 音楽・音声・効果音
   - 動画
3. **生成コンテンツから Predicted SIS を再抽出**  
   - 画像：VLM や LLM＋Vision を用いて SIS スロットを推定。
   - テキスト：LLM で要約・スタイル・構造などを SIS にマッピング。
   - 音声／BGM：ジャンル・テンポ・楽器などの分類器／タグ付けモデルを用いる。
4. **Gold SIS と Predicted SIS を比較**  
   - スロット単位（`location` や `mood` など）が一致しているかを見る。
   - 必要に応じて、全体スコア（例：スロット一致率の平均）も算出する。

### 10.2 用途

**評価**

- 画像モデルやテキストモデルなどを、「SIS 準拠度」に基づいて評価できる。
- 同じ Gold SIS を使って、テキスト版／画像版／音楽版など、モーダルをまたいだ比較が可能。

**生成モデルのデバッグ**

- 例：`mood = "bright"` のはずなのに、
  - 画像側では `visual.lighting` が暗くなっている → そのスロットだけ不合格、といった診断が可能。

**制御ループ**

- Gold SIS と Predicted SIS の差分をもとに、再プロンプトや追加生成を行うことができる。
- 例：`location = forest` のはずが `city` になった場合、
  次のプロンプトに `"definitively in a forest, no buildings"` などを追加する。

### 10.3 課題・注意点

- 抽出モデルの誤りにより、評価が「生成モデル＋抽出モデル」の複合誤差になる。
- ただし、SPICE におけるシーングラフパーサと同様の構造的問題であり、
  「意味構造ベースの自動評価」としては許容範囲、と整理している。
- モーダルごとに抽出難度が異なる。
  - 画像・テキストは VLM / LLM により比較的扱いやすい。
  - 音楽やBGMは `mood`, `tempo`, `instruments` など専用分類モデルが必要で、今後の実装・研究トピックになりうる。

## 📎 付録C: 生成順序の制御と再生成コスト削減

この章は、SIS を用いて生成順序を制御し、計算資源や再生成コストを削減するためのワークフロー設計例です。

ここでは、「プロンプト一発でマルチモーダルを生成する」のではなく、SIS を介して段階的に生成することで、負荷や再生成回数を抑える考え方を整理します。

### 11.1 SISありワークフローの段階

大枠として、次の 3 ステージに分けて考えます。

1. **意味設計フェーズ（軽い：LLM中心）**
   - StorySIS を生成（`story_type`, `themes`, 登場キャラクターなど）。
   - SceneSIS を生成（各シーンの `summary`, `semantics`, `visual`, `audio` 方針）。
   - ここまではテキスト＋LLM が中心で、CPU だけでも回しやすい。

2. **軽量プレビュー生成フェーズ**
   - 小さめモデルや低解像度設定で、ラフ画像／ラフ BGM を生成。
   - テキストも短い版を出して、ストーリー全体の流れを確認。
   - ユーザーはこの段階で「シーン構成」や SIS の内容を確認・修正する。

3. **本番生成フェーズ（重い：SD / MusicGen など）**
   - ユーザーが OK したシーンだけ、高解像度画像や長め BGM を生成。
   - 似た SIS のシーンは過去生成物を再利用する。

### 11.2 一発生成との比較

**一発生成（長文プロンプト → 動画／マルチモーダル）**

- 利点：実装がシンプルで、UX も直感的。
- 欠点：気に入らない場合は「丸ごと再生成」になりやすく、再生成コストが大きい。
- 欠点：どこが悪かったのか（シーン単位／要素単位）が解析しづらく、局所修正もしにくい。

**SIS分割生成**

- 利点：失敗や調整が SceneSIS の一部フィールドに局所化される。
  - 例：`visual.style` だけ変える、`audio.tempo` だけ速くする、など。
- 利点：ユーザーが意味レベルで介入できる（UI で SIS を直接編集）。
- 利点：SIS DB があれば「まず既存アセットを検索」し、そもそも生成しない選択肢も取れるため、再生成コストを抑えられる。
- 欠点：中間表現・ストレージ・UI といった仕組みが必要になり、実装と設計は複雑になる。
- 欠点：短期的には「一発生成」より手数が多く見える可能性がある。


