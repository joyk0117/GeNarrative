# 🧩 GeNarrative – Semantic Interface Structure (SIS) 仕様書

## 🎯 1. 概要（Overview）

Semantic Interface Structure（SIS）は、**「作品やシーンの意味情報」を取り出し、生成・検索・再利用の“ハブ”にする中間表現**です。  
「何を作るか（意味）」と「どう作るか（モデル・プロンプト）」を分離し、生成・検索・学習の全フェーズで共通言語として機能します。

### 主なメリット

1. **モジュール分離 & コントロール性**
   - 意味（SIS）は固定したまま、モデル（SD/MusicGen等）やパラメータだけを差し替え可能。
2. **再現性・説明性**
   - 「どんな意味指定から生まれたか」をJSONで記録。出所確認や再生成の基盤となる。
3. **編集しやすい“パラメータ”と人手補正**
   - LLMの抽出が不完全でも、構造化されたデータなので人手で修正・補完が可能。
4. **検索・推薦の共通インターフェース**
   - 「しんみり＋夜＋ピアノ」のような意味ベースの検索・推薦が可能。
5. **学習データ・評価の基盤**
   - SISを正解データとして、プロンプト生成、QA作成、モデル評価（整合性判定）に活用できる。
6. **ベクトルDB・他モデルのハブ**
   - SISの各要素をベクトル化し、外部DBやEmbeddingモデルとの橋渡し役となる。

---

## 🏗 2. レイヤ構造（Story / Scene / Media の三層）

GeNarrative のスコープでは、SISは以下の3種類のオブジェクトで構成されます。

### StorySIS（上位：作品全体）

- 作品全体の意味構造を保持するオブジェクト。
- ストーリータイプ（起承転結、三幕構成など）
- 作品全体テーマ、キャラクター設定
- 作品全体のスタイル方針（文体・画風・音楽方針）

### SceneSIS（中位：意味の単位）

- 作品を構成する**最小意味単位（1シーン）**を表すオブジェクト。
- シーンの意味（summary / semantics）
- シーンレベルの生成方針（text / visual / audio）
  - 再利用性のため、SceneSIS には story_id は含めない（同一Sceneを複数Storyで使い回す）。

### MediaSIS（下位：表現の単位）

- SceneSIS の内部をさらに分解する**「シーン構成要素（表現単位）」**を表すオブジェクト。
- 例：ショット（構図）、台詞、ナレーション、字幕、効果音、BGMセグメント、小物（object）など。

#### レイヤ間のつながりと外部インデックス

- StorySIS・SceneSIS・MediaSIS のつながり（`story_id`・`scene_id`・`media_id` の対応関係）は、各 SIS の JSON 内には直接保持せず、外部のインデックスとして管理します。
- こうすることで、1つの SceneSIS / MediaSIS を複数の StorySIS から再利用できるようにし（再利用性）、また Story / Scene / Media 本体を変更せずに関係だけを差し替えることで、更新作業に強い構造にします。
- 具体的には、グラフ構造（グラフデータベース）やリレーショナルデータベースの関係テーブルなどに、Story / Scene / Media 間の対応関係を保存することを想定します。

---

## 📘 3. StorySIS 仕様

### 3.1 StorySIS – JSON スキーマ（概念）

```jsonc
{
  "sis_type": "story",
  "story_id": "123e4567-e89b-12d3-a456-426614174000",

  "title": "The Girl and the Forest",
  "summary": "A curious girl explores a mysterious forest.",
  "story_type": "kishotenketsu", // 例: "kishotenketsu" | "three_act" | "attempts" | "circular" | "catalog"

  // 作品全体の意味構造（テーマ・スタイル方針）
  "semantics": {
    // 作品全体の共通の意味情報
    "common": {
      "themes": ["trust", "learning"],
      "descriptions": [
        "A gentle story about a girl learning to trust the forest and herself.",
        "Focuses on emotional growth rather than fast-paced action."
      ]
    },

    // 作品全体のスタイル方針（任意）
    "text":  {"language": "English", "tone": "gentle", "point_of_view": "third"},
    "visual": {"style": "watercolor"},
    "audio": {"genre": "ambient"}
  },

}
```

### 3.2 フィールド詳細（抜粋）

| フィールド | 型 | 説明 |
|---|---|---|
| story_type | string | ストーリー構造の種類（例：起承転結） |
| semantics.common.themes | array | 作品全体のテーマ |
| semantics.common.descriptions | array | 作品全体の補足説明文（summary では表しきれないニュアンスや意図など） |
| semantics.text / semantics.visual / semantics.audio | object | 作品全体のスタイル方針（SceneSIS / MediaSIS 側で上書き可） |

### 3.3 story_type 標準値

代表的なパターンと `SceneSIS.scene_type` の対応は次の通りです。

| story_type | 概要 | scene_type（SceneSIS.scene_type） |
|---|---|---|
| three_act | ドラマ型（困難→解決） | setup / conflict / resolution |
| kishotenketsu | オチ・ひねり型（最後に意味が反転） | ki / sho / ten / ketsu |
| circular | 旅して帰る型（行って変わって戻る） | home_start / away / change / home_end |
| attempts | 複数回チャレンジ型（試行錯誤） | problem / attempt（反復） / result |
| catalog | 図鑑・紹介型（順番が薄い） | intro / entry（反復） / outro |

---

## 🎬 4. SceneSIS 仕様

SceneSIS は 1 シーンを記述する JSON オブジェクトです。  
保存形式は **JSON / JSONL いずれも利用可能**ですが、多数のシーンを扱う場合は **JSONL（1行1Scene）** を推奨します。

以下の JSON スキーマ例は説明用の **JSONC（コメント付き JSON）** です。実際に保存するファイルはコメントのないプレーンな JSON / JSONL としてください。

### 4.1 SceneSIS – JSON スキーマ（概念）

```jsonc
{
  "sis_type": "scene",
  "scene_id": "123e4567-e89b-12d3-a456-426614174000",

  "summary": "Introduction of the girl and the forest.",
  "scene_type": "ki",

  // シーンの意味＋生成方針（多モーダル共通の背景）
  "semantics": {
    "common": {
      "mood": "calm",
      "characters": [
        {
          "name": "Nancy",
          "traits": ["girl", "curious"],
          "visual": {
            "hair": "brown curly hair",
            "clothes": "striped shirt and purple skirt"
          }
        }
      ],
      "location": "forest",
      "time": "day",
      "weather": "sunny",
      // 目立つモチーフや色（意味づけしやすいもの）
      "objects": [
        { "name": "big_sun", "colors": ["yellow", "orange"] },
        { "name": "small_house", "colors": ["red", "brown"] },
        { "name": "tree", "colors": ["green", "brown"] }
      ],
      "descriptions": [
        "Nancy quietly observes the forest, feeling both curiosity and a slight nervousness.",
        "The scene emphasizes gentle light and a peaceful, exploratory mood."
      ]
    },

    // 各モーダルの意味情報
    "text": { "style": "simple", "language": "English", "tone": "gentle", "point_of_view": "third" },
    "visual": { "style": "watercolor", "composition": "mid-shot", "lighting": "soft", "perspective": "eye-level" },
    "audio": { "genre": "ambient", "tempo": "slow", "instruments": ["piano", "pad"] }
  },

}
```

### 4.2 フィールド詳細（抜粋）

#### 4.2.1 semantics（シーンの意味情報）
画像・テキスト・音のすべてが参照する「意味の背景」。`semantics.common` に次のようなフィールドを持つ。

| フィールド | 説明 |
|---|---|
| characters | シーンに登場するキャラ詳細（ID, 名前, 外見など）。シーン固有の服装などを記述可能 |
| location | 場所名 |
| time | 時間帯 |
| weather | 天候 |
| mood | 空気感 |
| objects | 目立つモチーフや色など、シーン内で重要なオブジェクト |
| descriptions | summary では表現しきれないシーンの意図やニュアンス、解釈メモなどのテキスト（複数可） |

#### 4.2.2 semantics.text / semantics.visual / semantics.audio（Sceneレベル方針）
- `semantics.text/semantics.visual/semantics.audio` は **Sceneレベルの方針（デフォルト）**。

---

## 🧩 5. MediaSIS 仕様

MediaSISは、SceneSISの内部を分解した「構成要素（表現単位）」です。  
生成・編集・出力の最小単位を MediaSIS に揃えることで、粒度の粗いシーンも細かいシーンも同じ枠組みで扱えます。

### 5.1 MediaSIS – JSON スキーマ（概念）

※以下は、**画像（visual）から抽出した MediaSIS のサンプル**であり、text や audio の要素は含めていません。

```jsonc
{
  "sis_type": "media",
  "media_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",

  // 構成要素の種別で、どのモーダルに対する要素か（この例では画像）
  // この Media 要素全体の短い要約
  "summary": "a happy scene in a park with a big sun and a small house",
  
  // 構成要素の種別で、どのモーダルに対する要素か（この例では画像）
  "media_type": "visual",

  // 意味構造（抽出対象）
  "semantics": {
    "common": {
      // 全体の雰囲気
      "mood": "happy",
      // summary / description では分割しづらい意味情報や解釈メモ（複数可）
      "descriptions": [
        "The drawing conveys a strong sense of safety and warmth between the two figures.",
        "Colors are intentionally vivid to reflect a child's joyful perception of the world."
      ],

      "location": "park",
      "time": "day",
      "weather": "sunny",

      // 登場人物
      "characters": [
        {
          "name": "girl",
          "traits": ["small", "smiling"],
          "visual": {
            "hair": "brown curly hair",
            "clothes": "striped shirt and purple skirt"
          }
        }
      ],

      // 目立つモチーフや色
      "objects": [
        { "name": "big_sun", "colors": ["yellow", "orange"] },
        { "name": "small_house", "colors": ["red", "brown"] },
        { "name": "tree", "colors": ["green", "brown"] }
      ]

    }
  },

  // 出所・生成記録
  "provenance": {
    "assets": [
      {
        "asset_id": "child_drawing_001",
        "uri": "shared/.../child_drawing_001.png"
      }
    ],
    "generator": {
      "system": "ollama",
      "model": "...",
    }
  }
}
```

#### 5.2 semantics.text / semantics.visual / semantics.audio（Mediaレベル方針）
- `semantics.text/semantics.visual/semantics.audio` は **MediaSIS レベルの方針**で、SceneSIS 側の方針を継承しつつ、必要に応じて上書きします。
- モーダルごとの典型的なフィールド例は次の通りです。

| モーダル | 例示フィールド |
|---|---|
| text | `style`（文体）, `language`, `tone`, `point_of_view` など |
| visual | `style`（画風）, `composition`（構図）, `lighting`, `perspective` など |
| audio | `genre`, `tempo`, `instruments`, `mood` など |

## 🚀 6. 応用例（Use Cases）

### A. GeNarrative内の典型ユースケース
- **子どもの絵 → SIS抽出:** 画像から意味を抽出してSIS化し、そこからストーリー・BGMを生成。

### B. 既存コンテンツのカタログ化
- 市販絵本や青空文庫からSISを自動抽出し、「絵本レコメンド」や「場面に合うBGM検索」などの意味ラベリングに活用。

### C. 教育・研究系
- 同じSISで「画像だけ変える」「BGMだけ変える」実験を行い、学習効果への影響を検証する比較実験の基盤として利用。

### D. 評価プロトコルとの接続
- SISを「正解の意味構造」とし、生成されたコンテンツがSISとどれだけ一致しているかを測定することで、モデルの定量評価を行う。

----

## 🛠 7. 保存形式

- StorySIS: `story.json`（単一の StorySIS オブジェクトを格納する JSON）
- SceneSIS: `story_scenes.json` / `story_scenes.jsonl`（複数 SceneSIS を格納する場合は JSON / JSONL いずれも可）
- MediaSIS: `story_media.json` / `story_media.jsonl`（複数 MediaSIS を格納する場合は JSON / JSONL いずれも可）

StorySIS / SceneSIS / MediaSIS 同士の紐づけ（`story_id`・`scene_id`・`media_id` 間の対応）は、別ファイルやデータベースなどの **外部インデックスで管理する** ことを基本とします。

----

## 🧪 8. LLM生成ワークフロー（推奨）

1. MediaSIS を用意（任意）
   - 既存の素材（画像/文章/音など）から抽出して作る、または人手で作る
2. SceneSIS を生成
   - Scene の意味背景（`semantics.common`）と、モーダル別の方針（`semantics.text/visual/audio`）を定義
   - 必要なモーダル（text/visual/audio）の MediaSIS を生成し、`scene_id` と `media_id` の対応を外部インデックス（例：DB や別 JSON）で管理
3. StorySIS を生成
   - story_type に従い scene_type を決定し、外部インデックス上で Story ↔ Scene の対応を管理

----

## 🔗 9. 関連概念（Inspirations / Related Concepts）

SIS は独自の仕様ですが、設計思想として以下の既存概念と共通点があります。  
※ここで挙げるのは **参考（アナロジー）**であり、SIS がこれらへの準拠や互換性を保証するものではありません。

### OpenUSD（シーン記述 ↔ レンダリングの分離）

OpenUSD は 3D 制作で「編集対象としてのシーン記述」と「出力工程（レンダリング）」を分離し、差し替え・合成・再利用を容易にする考え方を提供します。  
SIS はこの発想を 3D に限定せず、物語・画像・音声などマルチモーダル創作に拡張し、「意味」を編集可能な中間表現として扱うことを目的とします。

### W3C PROV（provenance：出所・生成履歴のモデル）

SIS の `provenance` は、素材（assets）や生成器（generator）など「どの入力・どの生成条件から生まれたか」を保持するための領域です。  
この領域の考え方は、出所・生成履歴を表現する汎用モデル（W3C PROV：Entity / Activity / Agent）と親和性があります（将来の拡張・相互運用の参考）。

### JSON Schema（編集可能JSONのバリデーション）

SIS は人手編集を前提とするため、スキーマに基づくバリデーション（必須項目・型・列挙値など）を導入すると、破損や表記揺れを抑えられます。  
将来的に SIS のスキーマ進化（後方互換）やツール連携（フォームUI生成など）を行う際の基盤として、JSON Schema は有用です。

## 🧭 10. SIS以外の方式との比較（参考）

SISは「モーダル間の連携のための“中間表現”」という位置づけですが、同じ目的は別の設計でも達成できます。
ここでは代表的な代替アプローチと、SISとの違いを整理します。

---

### 10.1 各方式の概要

#### A) SIS（明示スキーマJSON）
- **概要**：画像・テキスト・音楽などの生成をつなぐために、意味情報を **明示的なスキーマ（JSON）**として保持し、必要に応じて人間が編集できるようにする方式。
- **向いている**：反復改善（生成→修正→再生成）、差分管理、検証、モデル差し替え、説明可能性が必要なケース。
- **弱点**：スキーマ設計・変換（SIS→各モーダル条件）・運用のコストがかかりやすい。最短で“それっぽく”出すだけなら過剰になりうる。

#### B) 直結（中間なし：画像or文章→LLM→各生成）
- **概要**：画像や文章からキャプション/指示文を作り、そのまま各モーダル生成（文章/画像/音楽など）に流す。中間表現を固定せず、パイプで直結する方式。
- **向いている**：最短で動く試作、デモ、個人用途の一発生成。
- **弱点**：再現性・差分管理・検証が弱く、意図した属性だけを安定して調整しにくい。モデル変更で挙動が変わりやすい。

#### C) 自然言語台本/設定書（Story bible）
- **概要**：構造化JSONではなく、章立てされた文章（世界観、人物設定、シーン概要、雰囲気など）を中間成果物として扱う方式。
- **向いている**：人間が読みやすい編集、創作の自由度を保ったままの反復。
- **弱点**：機械的な検証（型チェック）や差分の意味解釈が難しい。検索・再利用も工夫が必要。

#### D) 埋め込み/latent（ベクトル中間）
- **概要**：画像や音声などを埋め込みベクトルに落とし、「近いもの」を検索したり条件付けに使ったりする方式（中間表現がベクトル）。
- **向いている**：大量資産の検索・推薦、類似性ベースの再利用。
- **弱点**：人間が編集しにくくブラックボックス寄り。検証や「この属性だけ変える」が難しい。

#### E) グラフ（知識グラフ/シーングラフ）
- **概要**：「登場人物Aが物体Bを持つ」「場所は森」など、ノード・エッジの関係構造として中間表現を持つ方式。
- **向いている**：関係性の整合性チェック、依存関係の管理、推論・制約の付与。
- **弱点**：設計・実装コストが高くなりがち。創作の自由度を確保するには設計が難しい。

#### F) 既存標準＋拡張（例：OpenUSD等）
- **概要**：既存の標準フォーマット（特にシーン/アセット管理の標準）に寄せ、必要な意味情報を拡張メタデータとして持つ方式。
- **向いている**：既存の制作/資産管理パイプラインとの統合、標準エコシステム活用。
- **弱点**：導入・運用コストが大きい。物語や感情など“非シーン”的意味は結局別レイヤが必要になることが多い。

---

### 10.2 バランス比較表（〇/△/×）

- **〇**：得意 / そのまま実現しやすい  
- **△**：条件次第 / 工夫や追加設計で対応可能  
- **×**：苦手 / 別途仕組みが必要になりがち  

| 方式 | 立ち上げ速度（最短でそれっぽく） | 人が編集しやすい | 再現性/差分管理 | 型/制約で検証 | モデル差し替え耐性 | ブラックボックスになりにくい | 検索/再利用 | 実装/運用コスト | 創作の自由度 |
|---|---|---|---|---|---|---|---|---|---|
| **SIS（明示スキーマJSON）** | △ | 〇 | 〇 | 〇 | 〇 | 〇 | 〇 | △ | △ |
| 直結（中間なし） | 〇 | × | × | × | △ | × | △ | 〇 | 〇 |
| 自然言語台本/設定書（Story bible） | 〇 | 〇 | △ | × | △ | 〇 | △ | 〇 | 〇 |
| 埋め込み/latent（ベクトル中間） | △ | × | 〇 | × | × | × | 〇 | △ | △ |
| グラフ（知識グラフ/シーングラフ） | × | △ | 〇 | 〇 | 〇 | 〇 | 〇 | × | × |
| 既存標準＋拡張（OpenUSD等） | × | △ | 〇 | 〇 | 〇 | 〇 | 〇 | × | △ |

---

### 10.3 運用指針：SIS＋自然言語descriptionのハイブリッド（推奨）

実運用では、**SIS（骨格）＋ description（肉付け）** の併用が扱いやすいです。

#### 基本方針
- **SISは「編集したい最小限の要素」だけを固定化**する（必要十分・小さく保つ）
- **自由記述は description に逃がす**（細部・余韻・例示・候補列挙など）
- 生成時は「SISの確定情報」を優先し、description は補助情報として使う

#### 使い分けの目安（何をSISに入れるか）
- **SISに入れる（固定化したい）**
  - ストーリー構造・シーン構造（型として検証したいもの）
  - 登場人物/場所/時代/視点/トーンなど、出力全体を左右するパラメータ
  - 禁則・制約（例：暴力表現なし、子ども向け、特定の語彙は禁止）
  - 生成の整合性に関わる参照（scene_id の参照、親子関係、対応関係）
- **descriptionに入れる（柔らかく持つ）**
  - 具体例、連想、言い回し候補、雰囲気の補足
  - 解釈の余地を残したい要素（「〜のような」「〜かもしれない」）
  - モデルやプロンプトに依存しやすい細部（詩的表現、比喩、長い情景描写）
  - 複数案を保持したい内容（候補を箇条書きで並べる等）

#### 最小SIS（例：まずこれだけ固定）という考え方
- StorySIS：`genre / audience / tone / structure / theme / constraints / scenes[]`
- SceneSIS：`scene_id / summary / characters / setting / mood / key_events / constraints`
- MediaSIS：`asset_id / type / purpose / style / constraints / source_refs`

※上記以外は、まず description に寄せてから必要に応じて昇格（description → SISフィールド化）する。

## 🎉 11. まとめ

本仕様は以下を満たします：

- 起承転結などのストーリー構造（StorySIS）
- Scene の意味＋生成方針の一貫管理（SceneSIS）
- Media による表現単位への分解と編集（MediaSIS）
- マルチモーダル生成に最適化
- UI / LLM / ファイル保存の全方向で扱いやすい
