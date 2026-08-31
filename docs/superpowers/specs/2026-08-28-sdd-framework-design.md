# SDD フレームワーク

Superpowers の分類・承認ゲート・plan・サブエージェント実行・ブランチ終了と、grill-with-docs の問い詰め・用語集・ADR を一本化したスキルパック。正本は Markdown。人間向けに HTML を生成する。実装は 1 ブランチで進め、終了時に Task と 1 対 1 の stacked PR を選べる。

## Problem

二つの参照源は相補的だが、そのまま繋ぐと壊れる。

- Superpowers は spec → plan → 実装実行まで強い。設計の問い詰めは会話中心で、用語と決定がディスクに残りにくい。
- grill-with-docs は用語と重い決定をその場で書く。glossary ではない合意は会話に残り、SDD ラッパーから呼ぶとファイル書き込みが落ちることがある。
- 終了メニューはローカル merge / 単一 PR / 保持の 3 択で、Task 単位の stacked PR がない。
- Markdown 正本はエージェント向きだが、人間が spec / plan / 用語集を読むには HTML の方が楽なことがある。

このリポジトリは空で、フレームワーク本体をここから作る。

## Goals

- 設計から終了まで、Cursor と Claude Code で同じスキル正本が動く。
- 設計中に解決した語はすぐ `CONTEXT.md` へ、3 条件を満たす決定だけ ADR へ書く。それ以外の合意は同じセッションで spec に載せる。
- 実行時に Superpowers プラグインにも grill-with-docs にも委譲しない。TDD / デバッグ / 検証 / worktree / レビューは Superpowers 6.3.0 からパックへ vendor する。
- 正本は Markdown。対応 HTML は生成物として隣に置く。
- 実行は 1 ブランチ。終了選択肢に Task 1:1 の stacked PR を足す。

## Non-goals

- Codex、named custom agent、モデルルーティング（既存の `sdd-model-routed-development` は取り込まない）。
- `CONTEXT-MAP.md` による複数コンテキストの自動ルーティング。
- Visual companion、wayfinder、マルチセッションの decision map。
- マーケットプレイス公開。
- 実行前に新しい git worktree を必須にすること（現在の worktree で動く）。
- スキル本文のユニットテスト、CI でのサブエージェント実行。
- HTML 正本化、JS フレームワーク、独自デザインシステム。

## Shape

このリポジトリはスキルパックである。ランタイム依存は Python 3.11+（スクリプト）と、終了の PR 系に `gh`。Node は使わない。

インストールはパック単位。単一の `SKILL.md` をコピーして使ってはならない。スクリプトはパックルートの `scripts/` を、スキルからの相対パスで解決する。

```text
skills/sdd/
skills/sdd-design/
skills/sdd-plan/
skills/sdd-execute/          # implementer / task-reviewer / final-reviewer
skills/sdd-finish/
skills/test-driven-development/   # Superpowers 6.3.0, vendored
skills/systematic-debugging/
skills/verification-before-completion/
skills/using-git-worktrees/
skills/requesting-code-review/
skills/receiving-code-review/
skills/dispatching-parallel-agents/
scripts/render-docs
scripts/task-brief
scripts/review-package
scripts/stack-prs
scripts/_vendor/             # Markdown→HTML。実行時ネットワーク禁止
assets/sdd.css               # 初回 render で利用側へコピー
docs/formats/context.md
docs/formats/adr.md
tests/                       # pytest。スクリプトのみ
.claude-plugin/plugin.json   # 同じ skills/ を指す
pyproject.toml               # pytest。アプリランタイムではない
README.md                    # Cursor と Claude Code のローカル導入
LICENSE
LICENSE-superpowers.txt
```

Claude Code はローカルプラグインマニフェストから同じ `skills/` を読む。Cursor は同じディレクトリをスキルパックとして読む。スキル本文をホスト別に複製しない。

スキルとプロンプトの言語は英語（モデルが手順を追いやすい）。利用側リポジトリの成果物の言語は、書かれた Markdown の言語に従う。

## Pipeline

```text
sdd-design → sdd-plan → sdd-execute → sdd-finish
```

入口スキル `sdd` が経路を選ぶ。spec なしの architectural 実装、plan なしの `sdd-execute` は止める。

| 分類 | spec ファイル | plan | execute | finish |
|---|---|---|---|---|
| spike | 作らない | 使わない | 使わない | 使わない |
| bounded | 作らない。チャットの短い設計が正 | 使わない | 使わない。承認後に同じセッションで `test-driven-development` | 1〜3 は使える。4 はレジャーが無いので出さない |
| architectural | 必須 | 必須 | 必須 | 必須 |

分類は最初に口に出す。迷ったら重い方。途中で複雑さが顔を出したらダウングレードせず、重いパスへ上げて宣言する。

## Consuming repo paths

利用側リポジトリのパスは固定する。フレームワークが別パスを推測しない。

| 用途 | パス |
|---|---|
| 用語集正本 | `CONTEXT.md`（ルート） |
| 用語集 HTML | `CONTEXT.html` |
| ADR 正本 | `docs/adr/NNNN-slug.md` |
| ADR HTML | `docs/adr/NNNN-slug.html` |
| spec 正本 | `docs/sdd/specs/YYYY-MM-DD-<topic>-design.md` |
| spec HTML | 同名 `.html` |
| plan 正本 | `docs/sdd/plans/YYYY-MM-DD-<feature>.md` |
| plan HTML | 同名 `.html` |
| 共有 CSS | `docs/sdd/assets/sdd.css` |
| 作業スクラッチ | `.sdd/`（gitignore） |

`.sdd/` の中身:

- `briefs/task-N-brief.md`
- `reports/task-N-report.md`
- `reviews/task-N.diff.md`（review-package の出力）
- `progress.md`（`Worktree: created <path>` / `in-place` / `existing <path>`、`Branch baseline: <full-sha>`、各 Task の complete 行）

正本は git のコミットと `CONTEXT.md` / ADR / spec / plan。レジャーは復旧用スクラッチで、コミットしない。

v1 はルートの `CONTEXT.md` のみ。`CONTEXT-MAP.md` がある場合は、どの単一 `CONTEXT.md` を使うかを人間に聞いてから進む。マップを解釈して複数ファイルへ自動振り分けない。

## `sdd`（入口）

いつどのスキルを使うかを決める。ユーザーが実装だけを頼んでも、architectural 相当なら `sdd-design` から始める。plan がある状態で「実行して」なら `sdd-execute`。コントローラが実装を始める直前（execute の Task 1、または execute の implementer ではない TDD）に、隔離 worktree を作るかを一度聞く。実装が終わりテストが緑なら `sdd-finish`。バグやテスト失敗は `systematic-debugging`。bounded 実装は `test-driven-development`。完了宣言の前は `verification-before-completion`。

## `sdd-design`

Superpowers の分類と承認ゲートを残し、問い詰めとディスク書き込みをこのスキルに埋め込む。`grilling` や `domain-modeling` や `grill-with-docs` を Skill ツールで呼ばない。

### 問い詰め

- 一度に一つの質問。可能なら選択肢。毎回推奨アンサーを付ける。
- 既存の `CONTEXT.md`、ADR、README、コードが答えられることは人間に聞かない。
- 人間の語が glossary と衝突したら、衝突を先に解消する。
- 依存する決定は、先に決める枝から降りる。

### `CONTEXT.md`

用語が解決した瞬間に書く。バッチしない。glossary 以外を書かない（実装詳細、spec、スクラッチ禁止）。

書式はパックの `docs/formats/context.md` と同一にする:

```markdown
# {Context Name}

{このコンテキストが何か、1〜2文}

## Terms

**{Term}**:
{それが何か、1〜2文。動作の説明ではなく定義}

_Avoid_: {使わない同義語}
```

プロジェクト固有の語だけ入れる。一般的なプログラミング概念は入れない。同概念に複数の語があるときは一つを正とし、他は `_Avoid_` に列挙する。ファイルが無ければ最初の語で作る。

書いたらすぐ `render-docs` で `CONTEXT.html` を更新する。

### ADR

次の 3 つがすべて真のときだけ提案し、承認されたら書く。一つでも欠ければ ADR を作らず、必要な内容は spec に書く。

1. 後から覆すコストが大きい
2. 文脈なしだと、なぜこうなったか分からない
3. 本当にトレードオフがあり、理由を持って選んだ

パスは `docs/adr/NNNN-slug.md`。`NNNN` は既存の最大番号 + 1。無ければ `0001`。本文の書式はパックの `docs/formats/adr.md` に従い、1〜3 文で状況・選択・理由だけ。書いたら HTML を生成する。

### パス別の終わり方

**spike:** 2〜3 文でプローブを出し、頷きを得てから安く調べ、推奨を返す。残すコードは throwaway と明記する。spec / plan は作らない。問い詰め中に用語や ADR ゲートを満たした決定があれば、通常どおりディスクへ書く。

**bounded:** 短い設計をチャットに出し、明示の yes まで実装しない。yes のあと、隔離 worktree を作るかを一度だけ聞く（execute と同じ文言。必須ではない）。既に linked worktree にいるか、会話で希望が済んでいれば聞かない。作るなら `using-git-worktrees` のあと、同じセッションで `test-driven-development` する。spec ファイルも plan も作らない。

**architectural:** アプローチを 2〜3 出し、推奨を先に述べる。デザインはセクションごとに出し、各セクションの承認を待つ。全セクション承認後に spec Markdown と HTML を書き、プレースホルダ・矛盾・曖昧さ・範囲を自己レビューして直す。spec と、このセッションで更新した `CONTEXT.md` / ADR / 対応 HTML をまとめてコミットする。ユーザーに spec ファイルのレビューを求める。変更があれば新しいコミットにする（amend しない）。承認後に `sdd-plan` へ渡す。writing-plans スキルは呼ばない。

spec に残すもの: 分類結果、選んだアプローチ、アーキテクチャ、コンポーネント、データフロー、エラー処理、テスト、Goals / Non-goals、利用側パス。問い詰め中に ADR にならなかった数値・否定要件・順序保証は spec に明示する。会話だけに残してセッションを切ってはならない。

## `sdd-plan`

入力は architectural spec のパス。出力は `docs/sdd/plans/YYYY-MM-DD-<feature>.md` と HTML。書き終わったら plan（と新規 HTML）をコミットする。

plan 先頭は次のヘッダを必須とする:

- Goal（1 文）
- Architecture（2〜3 文）
- Tech stack
- Spec パス
- Global Constraints（spec から数値と文言をそのままコピー）

その後、ファイル構成、Task 列。各 Task は独立したテストとレビューを持てる最小単位。セットアップやドキュメントだけの Task は作らず、それが必要な成果物の Task に含める。Task 見出しは正確に `## Task N: <title>`（例: `## Task 1: Render docs script`）。この番号が brief 抽出と stacked PR の境界になる。step は Task 内の作業であり、PR 単位ではない。

## `sdd-execute`

1 ブランチのまま、Task を直列に実行する。実装サブエージェントを並列に出さない。TDD は `test-driven-development` スキルに従う。implementer プロンプトにも RED-GREEN の最低契約を残し、スキルが読めないサブエージェントでも TDD する。再レビューも同じ task-reviewer 雛形を使う。`requesting-code-review` は execute の Task ゲートには使わない。

ホスト: Cursor は Task ツールで新規サブエージェントを出す。Claude Code は Agent ツールで出す。モデル名はフレームワークが固定しない。ホストが隔離サブエージェントを出せないときは `HOST_SUBAGENT_UNAVAILABLE` で止まり、コントローラセッションで実装しない。

`.gitignore` に `.sdd/` が無ければ追記し、そのファイルだけを先にコミットする。Task 1 の前に plan を一度スキャンし、矛盾や Global Constraints 違反になりうる指定があれば、発見をまとめて一度だけ人間に聞く。問題が無ければ、隔離 worktree を作るかを一度だけ聞く（必須ではない）。既に linked worktree にいる、会話で希望が済んでいる、またはレジャーに `Worktree:` がある場合は聞かない。作るなら `using-git-worktrees` を使い、その worktree で execute を続ける。拒否なら現在の checkout で進む。同意は execute 側で取るので、worktree スキルで二度聞かない。答えは `.sdd/progress.md` に残し、コンパクション後に聞き直さない。実装する checkout が（`.gitignore` 追記コミットの後も）汚れていれば止まり、コミットか退避を人間に確認する。元の checkout の汚れは、新しい worktree に移ったあとは止めない。

`git clean -fdx` はレジャーを消す。消えたら `git log` から復旧し、完了済み Task を再実行しない。execute 開始時（または再開時）に `.sdd/progress.md` の `Branch baseline: <full-sha>` を読む。無ければ現在の `HEAD` のフル SHA を書いて、final review の base にする。

各 Task:

1. ディスパッチ前に `HEAD` を base として記録する。
2. `task-brief` で `.sdd/briefs/task-N-brief.md` を切る。実装サブエージェントに plan 全体を読ませない。質問があれば実装前に答え、同じ implementer 契約で再開する。
3. implementer は TDD、コミット、自己レビューをし、`.sdd/reports/task-N-report.md` にフルレポートを書く。チャットには status、コミット、テスト 1 行、concerns だけ返す。
4. status は `DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED` のいずれか。
5. `DONE_WITH_CONCERNS` の懸念が正しさや範囲なら、レビュー前に解消する。観察（ファイルが大きい等）ならレジャーに残してレビューへ進む。
6. `DONE` または観察のみの `DONE_WITH_CONCERNS` なら、`review-package BASE HEAD -o .sdd/reviews/task-N.diff.md` で diff ファイルを作り（再レビュー時は上書き）、task reviewer に brief・report・diff パスと Global Constraints を渡す。
7. reviewer は spec 準拠と品質の 2 つの判定を返す。Critical / Important は fix して再レビュー。Minor はレジャーに残し、final review で扱う。
8. reviewer が plan 本文と矛盾する finding を出したら、fix せず、plan 原文と finding を並べて人間に一度だけ聞く。
9. レビュー通過後、`.sdd/progress.md` に `Task N: complete (commits <base7>..<head7>, review clean)` を追記する。head は fix コミットを含む最終 `HEAD`。この範囲が stacked PR の入力になる。

コントローラが止まってよいのは次だけ: 破壊的操作、セキュリティ、worktree 外の副作用（共有ブランチへの push、merge、公開）、計画が壊れていて次が推測になるとき。それ以外の曖昧さは spec を正とし、判断をレジャーに `Ruling: <決定> — <理由> — <間違えたときのコスト>` と書いて進む。

コンパクション後はレジャーと `git log` を信じ、完了済み Task を再ディスパッチしない。`NEEDS_CONTEXT` / `BLOCKED` は文脈を足すか Task を割るか plan を直してから再ディスパッチする。同じ指示で同じ失敗を繰り返さない。

全 Task 通過後に `review-package` へその branch baseline と `HEAD` を渡し、final reviewer を 1 回出す。finding があれば fix サブエージェントは 1 つ（finding ごとに切らない）。その後 `sdd-finish`。

プロンプト雛形は `skills/sdd-execute/` に置く。implementer、task-reviewer、final-reviewer。差分をプロンプトに貼らない。

## `sdd-finish`

テストスイートが赤ならメニューを出さない。base branch は plan か会話か upstream から取り、不明なら確認する。

通常リポジトリと named-branch worktree のメニューは次の 4 択だけ:

1. base branch へローカル merge
2. push して単一 PR
3. ブランチをそのまま残す
4. Task ごとの stacked PR を push して作る

detached HEAD では 1 を出さない（2 / 3 / 4）。

4 は `stack-prs` にレジャー、確認済み base、plan パスを渡す。レジャーに Task 完了行が無い、またはコミット範囲が欠けているなら PR を作らず非ゼロで止まる。履歴は書き換えない。force-push しない。既存コミットにブランチを指すだけにする。

ブランチ名は `sdd-stack/task-N`。Task 1 の PR の base は確認済み base branch。Task N の PR の base は `sdd-stack/task-(N-1)`。途中失敗時は、作れた PR の URL と未作成 Task を報告する。

`gh` が必要なのは 2 と 4。1 と 3 は git のみ。

## Scripts

パックルートからの相対パスで呼ぶ。利用側リポジトリの cwd で実行し、成果物は利用側に書く。

スクリプトは欠けている親ディレクトリを自分で作る。呼び出しは `python3 <pack>/scripts/<name> ...`。

**`render-docs`** — 引数の Markdown パス（`.md` / `.markdown` のみ。または既定ルート: `CONTEXT.md`、`docs/adr/`、`docs/sdd/specs/`、`docs/sdd/plans/`）を HTML にする。正本は書き換えない。入力と出力の解決済みパスが同一なら書き込まずに失敗する。隣接する `.html` を書く。生 HTML は escape し、restrictive CSP を付ける。最初の実行で `docs/sdd/assets/sdd.css` が無ければパックの `assets/sdd.css` をコピーする。変換器は `scripts/_vendor/` に置いた mistune を使い、実行時ネットワークに依存しない。同じ入力で同じ HTML（タイムスタンプを埋め込まない）。失敗しても正本は残し、非ゼロ終了と stderr 警告にする。呼び出し元スキルは終了コードを記録して設計を続行する。

**`task-brief`** — `task-brief PLAN_FILE N`。`## Task N:` から次の `## Task` 直前（または EOF）までを抜き、`.sdd/briefs/task-N-brief.md` に書く。パスを stdout に出す。Task N が無ければ非ゼロ。前後の Task を混ぜない。Global Constraints は brief に含めない（execute が別途渡す）。

**`review-package`** — `review-package BASE HEAD -o PATH`。`-o` は必須。`BASE` が `HEAD` の祖先でなければ非ゼロ。ログ、stat、`-U10` diff をそのファイルに書く。git 出力は UTF-8 として decode し、不正バイトは置換する。`HEAD~1` を使わない。パスを stdout に出す。

**`stack-prs`** — `stack-prs --base BRANCH --ledger PATH --plan PATH [--dry-run]`。副作用の前に plan と ledger の Task 集合・順序、base/head の commit 解決、祖先関係、隣接範囲の連続性、既存 `sdd-stack/task-N` ref を検証する。失敗時は branch 更新・push・`gh` をしない。`--dry-run` では検証だけ行い、branch 作成・push・`gh` をしない。`--help` は終了コード 0。本番はレジャー順に `sdd-stack/task-N` を各 Task の head に置き、PR を積む。既存 ref は欠落か同一 SHA のときだけ更新し、`update-ref` に expected-old-value を付ける。PR 本文に plan の当該 `## Task N:` 見出しと plan 先頭の Goal を載せる。

## Error handling

- HTML 生成失敗: 正本は残す。警告。設計は続行。
- glossary 衝突: 質問を進めず衝突を先に解消。
- ADR ゲート不足: ADR を書かない。
- execute のホスト不能: `HOST_SUBAGENT_UNAVAILABLE`。コントローラで実装しない。
- execute 開始時、実装する checkout の未コミット変更（`.gitignore` 追記コミットの後）: 止まる。
- レビューの plan 矛盾: 人間に一度聞く。
- stacked PR の入力不足: 作らない。非ゼロ。
- stacked PR の途中失敗: 部分成功を報告。履歴を書き換えない。

## Testing

自動化対象はスクリプトだけ。`pytest`。git 操作は一時リポジトリ fixture。

| 対象 | 検証すること |
|---|---|
| `render-docs` | fixture の glossary / ADR / spec / plan から見出し・リンク・用語定義が HTML に残る。正本バイトが変わらない。再実行で HTML が安定する。CSS を正本ディレクトリへコピーする。 |
| `task-brief` | 複数 Task の plan から N だけ抜ける。N の本文に N-1 / N+1 が混ざらない。 |
| `review-package` | 複数コミットの Task で `BASE..HEAD` が全部入り、`HEAD~1` 相当に潰れない。 |
| `stack-prs` | レジャー通りにブランチが積まれる。`--dry-run` で push / `gh` が呼ばれない。完了行欠けで非ゼロ。 |

ホスト分岐は手動チェックリスト（Cursor と Claude Code で入口 → design の 1 セクション → スクリプト dry-run）。CI でサブエージェントを回さない。

`tests/fixtures/` に golden を置く: 空から語を 1 つ足した `CONTEXT.md`、ADR 1 本、spec 1 本、plan 2 Task、対応 HTML。

## License

フレームワークは MIT。Superpowers 由来の plan / execute / finish / プロンプトを適応する部分と、vendor した TDD / デバッグ / 検証 / worktree / レビュー skills は、Superpowers の MIT 表示を `LICENSE-superpowers.txt` に残す。grill-with-docs は規律の参照であり、そのスキルファイルはコピーしない。パイプライン skills（brainstorming, writing-plans, executing-plans, subagent-driven-development, finishing-a-development-branch, using-superpowers）はコピーせず、sdd-* が担う。

## Success

v1 が成功するのは次がすべて真のとき。

- architectural な変更で、問い詰め中に `CONTEXT.md` が語ごとに更新され、HTML が隣にあり、ADR は 3 条件を満たすものだけである。
- spec と plan が Markdown + HTML で残り、execute が Task ごとに brief / report / レジャーを残す。
- finish で 4 を選ぶと、Task 数と同じ stacked PR がレジャーのコミット範囲から作られる。
- Cursor と Claude Code で同じ `skills/` が使える。
- 実行時に Superpowers も grill-with-docs も必須ではない。
