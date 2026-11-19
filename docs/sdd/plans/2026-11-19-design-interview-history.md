# Design Interview History Implementation Plan

**Goal:** 重要な設計質問と実際の回答を別セッションでも参照できるようにし、合意と異なる仕様書の保存や既存文書の無断変更を防ぐ。

**Architecture:** OpenCode V2 のプラグインが設計フォームのイベントを受け取り、対象 checkout の SQLite に質問と回答を記録する。ローカル CLI が検索と明示的な過去ログ取り込みを提供し、`sdd-design` は文書保存前に履歴と仕様案を照合する。

**Tech Stack:** OpenCode V2 サーバープラグイン、TypeScript、Python 3.11+、標準ライブラリの SQLite、Git、pytest。

**Spec:** `docs/sdd/specs/2026-11-19-design-interview-history-design.md`

## Global Constraints

- 初版の自動記録は OpenCode V2 のみ。
- Claude Code・Cursor の記録、別 worktree・別マシン・チーム共有、他のリポジトリの会話収集、意味検索の外部サービスは対象外。
- 保存先が Git の除外対象で未追跡であることを作成前に確認する。
- モデルは原記録を書き換えず、回答の解釈を本人の発言や承認として扱わない。
- 添付ファイル、資格情報、ツール出力、セッション全文は保存せず、履歴を外部サービスに送信しない。
- 履歴は合意を照合する根拠であって、承認済み文書に代わる仕様の正本ではない。
- 保存後の文書レビューや実装承認は、この確認で代用しない。
- 既存の spec／roadmap は、対象・変更する意味・依存する作業への影響について明示的に合意するまで書き換えない。

## File Structure

- `adapters/opencode/`：V2 の設計フォームとイベント記録。既存の HTML 用プラグインは変更しない。
- `scripts/design-history`、`scripts/sddlib/`、`tests/`：履歴ストア、読み取り専用検索、ユーザー指定ログの取り込みと回帰テスト。
- `skills/sdd-design/SKILL.md`、`README.md`、`docs/evaluations/design-interview-history.md`：面談・保存前確認ルール、有効化と復旧手順、試用手順と証拠の要約。

## Task 1: Capture and search live interview answers

**Spec and dependencies:** `docs/sdd/specs/2026-11-19-design-interview-history-design.md` の「アーキテクチャと責務」「質問から文書保存まで」の手順 2、「記録できない場合」「検証と完了条件」。先行 Task なし。

**Deliverable:** 記録から検索までを一度通せる OpenCode V2 アダプター、SQLite ストア、読み取り専用 CLI。最初に使い捨てリポジトリと実際の OpenCode V2 で、プラグインが提示したフォームの作成・回答・取消を公開イベントで識別できるか確認する。公開 API の定義やモックで実機結果を代用しない。実機が使えない、または回答を相関できない場合は、結果と阻害要因を報告し、この Task を完了扱いにしない。

- プラグインが設計案件と checkout を紐づけたフォームだけを対象にし、ホストのセッション ID・フォーム ID・項目 ID で対応付ける。技術仕様は OpenCode V2 の現行サーバープラグインと Form API に照らす。モデルに回答ペイロードを渡して記録させない。
- `.sdd/design-history.sqlite3` への書き込み前に、checkout 境界と DB・付随ファイルの Git 除外／未追跡を検査する。重複配信や並行セッションでも同じ組を重複・混同させない。取消、未回答、回答済みを区別し、明示された保留や訂正は原回答を保持する。欠落・停止・書き込み失敗は空の検索結果と区別できるようにする。秘密値を検出した組はログにも出さず、欠落だけを通知する。
- `scripts/design-history` が案件・質問 ID・日本語の部分一致で絞り込んだ組を JSON で返す。質問本文・提示順の選択肢・実際の回答・出所・状態を含み、検索が DB を作成・変更しないことを確認する。

**Verify:** 単体・アダプターテストで複数項目、同じ選択肢名、取消と未回答、再配信、別リポジトリの除外、Git 条件、検索と保存失敗を検証する。使い捨てリポジトリの実機試用で、選択と自由回答を保存し、別セッションで案件・キーワード・質問 ID の各検索を確認する。使用した V2 バージョン、実行手順、実出力、検証範囲を報告する。実データや会話全文は証拠に含めない。

## Task 2: Import explicitly selected past logs

**Spec and dependencies:** `docs/sdd/specs/2026-11-19-design-interview-history-design.md` の「質問から文書保存まで」の手順 3 と「記録できない場合」。Task 1 の保存形式、質問 ID、出所、Git 除外と秘密情報の扱いを再利用する。

**Deliverable:** `scripts/design-history` に、ユーザーがローカルファイルと設計案件を明示して使う取り込み操作を追加する。プレビューでは書き込まず、取り込む組と除外理由を確認できるようにし、明示的な確定操作でだけ保存する。対応が確かめられる組を出所付きで保存し、不明な対応は推測しない。対応するログ形式と入力例を用意し、ログを自動探索・変更しない。

**Verify:** 一意の組、対応が曖昧な組、秘密情報を含む組、未対応形式を持つ合成ログで、プレビュー、確定、再実行時の重複防止、通常の検索での取得を検証する。入力ファイルを変更していないことと、抜粋以外の記録が残っていないことも確認し、コマンドと実出力を報告する。

## Task 3: Confirm design intent before saving documents

**Spec and dependencies:** `docs/sdd/specs/2026-11-19-design-interview-history-design.md` の「質問から文書保存まで」の手順 1・4・5、「記録できない場合」「検証と完了条件」。Task 1 の検索・失敗状態と Task 2 の取り込み手順を利用する。既存の [判断基準](../specs/2026-11-07-skill-judgment-and-handoff-design.md) にある質問の絞り込みは維持する。

**Deliverable:** `skills/sdd-design/SKILL.md` に、選択肢・推奨・理由と自由回答を使う判断基準、関連履歴の検索、保存前の照合と明示確認、既存文書を意味変更する前の承認を組み込む。新規 roadmap は分割と順序も先に確認し、保存後の承認を残す。記録有効時に必要な履歴が欠ければ依存する文書保存を止める。非対応・未有効ならその旨を示し、現在の会話と承認済み文書で確認する。リンクだけの更新に再承認を増やさない。`README.md` に設定、操作、記録範囲、復旧手順を説明する。

**Verify:** 使い捨てリポジトリの複数ターンの試用で、回答と矛盾する案、必要な記録の欠落、既存文書への未承認の変更が保存されないことを確認する。明確な要求、リンクだけの更新、非対応ホストでも適切に進むことを確認する。`docs/evaluations/design-interview-history.md` に入力、実際の質問と判断、変更された文書の有無、実機試用と自動テストの結果を分けて記録する。最終状態で `uv run --no-project --with pytest python -m pytest -q` を実行し、未実施の項目は未確認として報告する。
