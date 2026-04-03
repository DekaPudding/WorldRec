## 目的
- 既存の `RecommendationService` を GUI から利用可能にし、AI検索機能を「未実装」状態から実用状態にする。
- 既存の環境変数ベース運用を維持しつつ、検索実行・結果表示・未設定時フォールバックをユーザーから使えるようにする。

## 制約
- 作業対象は `D:\WorldRec` 配下に限定する。
- 変更は最小限かつ局所的にする。依存関係の追加、DB スキーマ変更、ワークスペース外編集は行わない。
- API キーは既存どおり環境変数 `WORLDREC_OPENAI_API_KEY` / `OPENAI_API_KEY` のみを使い、設定ファイル保存は行わない。
- ネットワーク関連の新規実行確認は行わず、ローカルで完結するテストを優先する。

## 対象ファイル
- `app/gui/chat_panel.py`
- `app/gui/main_window.py`
- `app/core/recommendation_service.py`
- `app/models/dto.py`
- `tests/test_recommendation_service.py`
- `tests/` 配下の AI検索関連テスト追加先
- `README.md`
- `local/docs/README.md`
- `local/docs/WorldRec-Developer-Overview.md`
- `local/docs/WorldRec-User-Guide.md`

## 非対象
- API キー入力 UI の追加
- 依存ライブラリの追加・更新
- OpenAI / VRChat API の通信仕様変更
- 2FA 周りや既存のワールド詳細機能の改修

## 実装手順
1. AI検索の現状導線を整理し、未実装表示の箇所を特定する。
2. `chat_panel` と `main_window` を更新し、検索パネルの開閉・入力・実行を有効化する。
3. `RecommendationResponse.source` を使って応答文を出し分け、OpenAI 利用時とローカルフォールバック時のメッセージを整える。
4. 必要なら `RecommendationService` の返却内容や DTO を最小限補強し、UI が理由つき候補を自然に表示できるようにする。
5. AI検索のユニットテストを追加・更新する。
6. README とローカル文書の「未実装」表記を現行仕様に合わせて更新する。

## 検証手順
- `python -m unittest tests.test_recommendation_service`
- 必要に応じて `python -m unittest tests.test_settings_service tests.test_world_detail_service`

## 未解決事項または前提
- OpenAI API キーが未設定でも、履歴ベースのローカル推薦を返す既存仕様を AI検索機能の最低要件とみなす。
- OpenAI 実通信はこの作業では検証しないため、API 応答互換性は既存実装前提とする。
- ドキュメント上の「AI検索」は、OpenAI 未設定時も利用可能な履歴推薦 UI として説明する。
