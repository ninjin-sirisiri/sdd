# SDD Plugin Review

レビュー日: 2026-08-29

対象: `/Users/h-uma/Documents/sdd` の現在の作業ツリー

対象範囲: Python スクリプト、Cursor/Claude Code のプラグインマニフェスト、SDD スキル、今回追加された Superpowers 由来スキル、テスト、仕様・README。未コミット変更と未追跡ファイルを含めて確認した。

## 判定

現状はマージ非推奨。テストは通過しているが、stacked PR の公開、Task brief の抽出、プラグイン導入後の主要ワークフローに影響する未修正の問題がある。

## Findings

### High

#### H-1. 不完全または不正な ledger でも stacked PR の公開を開始する

- 場所: `scripts/sddlib/stack.py:29-47`
- 再現条件: plan に Task 1 と Task 2 がある一方、ledger に Task 1 しかない場合。または、ledger の head/base が存在しない SHA の場合。
- 問題: `run_stack` は ledger が空でないことしか確認せず、plan の全 Task との一対一対応、欠落・重複・余分な Task、SHA の解決、base/head の祖先関係を検証しない。`--dry-run` では revision 検証も行わない。
- 影響: 未完了 Task を見落としたまま公開でき、先行 Task の branch/PR を作成した後に後続 Task の不正が発覚する。plan で記録したコミット範囲と実際の PR 範囲も一致しない可能性がある。
- 修正方向: すべての入力を副作用前に preflight する。plan と ledger の Task 集合、順序、base/head の commit 解決、`base..head` の祖先関係、隣接範囲の連続性を検証し、失敗時は branch 更新・push・`gh` 呼び出しをゼロにする。

#### H-2. final review が未定義の `MERGE_BASE` を参照する

- 場所: `skills/sdd-execute/SKILL.md:29-54`
- 再現条件: 複数 Task の execute が完了し、最後の Task の review を通過した後に Close 手順へ進む。
- 問題: ループ中に記録されるのは Task ごとの `BASE` だけだが、最後の手順は `review-package MERGE_BASE HEAD` を実行するよう指示している。
- 影響: 文字列 `MERGE_BASE` が revision として解釈されてコマンドが失敗するか、利用者が任意の base を推測してレビュー範囲を誤る。
- 修正方向: execute 開始時に branch baseline を解決して永続化し、再開時にも ledger から復元できるようにする。その SHA を final review に渡す。

#### H-3. 有効な Markdown fence 内の Task 見出しで brief 抽出が壊れる

- 場所: `scripts/sddlib/brief.py:14-18`, `scripts/sddlib/ledger.py:37-42`
- 再現条件: Task 本文に `~~~`、4 個以上のバッククォート、またはインデントされた fence があり、その中に `## Task N:` が含まれる場合。
- 問題: brief parser は行頭の3個のバッククォートだけを単純にトグルする。ledger の見出し抽出は fence をまったく考慮しない。
- 影響: Task 本文が途中で切れたり、コード例の偽見出しが PR タイトルとして選択されたりする。実装者に不完全な要件を渡す可能性がある。
- 修正方向: fence の種類、長さ、許容インデントを追跡する共通 Markdown parser を実装し、brief 抽出・Task 完全性確認・PR 見出し取得で共有する。

#### H-4. worktree の ignore 検証が実際の作成先を検証しない

- 場所: `skills/using-git-worktrees/SKILL.md:67-88`
- 再現条件: `worktrees/` だけが存在し、`.worktrees` は ignore されているが `worktrees` は ignore されていない場合。両方が存在して選択先と ignore 済みの候補が異なる場合も同様。
- 問題: `git check-ignore` を2つの候補に対する OR 条件で実行するため、選択先が ignored でなくてももう一方が ignored なら検証が成功する。
- 影響: untracked の linked checkout を作成し、worktree の内容を誤ってコミットする危険がある。
- 修正方向: 優先順位で選択した location を変数に保存し、`git check-ignore -q "$LOCATION"` のみを実行する。

### Medium

#### M-1. `render-docs` が入力ファイルを上書きできる

- 場所: `scripts/sddlib/render.py:23-24,69-80`
- 再現条件: 明示パスとして既存の `.html` ファイルを渡す。
- 問題: `with_suffix(".html")` が入力と同じパスを返すため、変換結果で入力を上書きする。`.HTML` も大文字小文字を区別しないファイルシステムで衝突し得る。
- 影響: Markdown を正本とする前提に反し、誤った引数で入力データを破壊する。
- 修正方向: Markdown 拡張子だけを受け付け、resolved な入力・出力パスが同一でないことを書き込み前に確認する。

#### M-2. `review-package` は逆方向または無関係な revision 範囲を受け付ける

- 場所: `scripts/sddlib/review.py:9-14`
- 再現条件: `BASE` が `HEAD` の子孫でない commit、または別系統の commit を指定する。
- 問題: 両方が commit として解決できることしか確認していない。
- 影響: 空のログ、逆方向の差分、または Task と無関係な差分をレビュー対象として生成する。
- 修正方向: `git merge-base --is-ancestor BASE HEAD` を確認し、forward range でない場合は非ゼロ終了する。

#### M-3. `review-package` が非 UTF-8 の変更で traceback を出す

- 場所: `scripts/sddlib/review.py:12-21,35-39`
- 再現条件: 変更差分にプロセス locale で decode できないバイト列を含むファイルがある場合。
- 問題: `check_output(..., text=True)` の decode 例外を `CalledProcessError` として捕捉していない。
- 影響: CLI が利用者向けエラーに変換されず、レビュー package を生成しない。
- 修正方向: bytes で取得して明示的な decode 方針を選ぶか、decode/filesystem 例外を CLI 境界で処理する。

#### M-4. `render-docs` の出力 HTML で生 HTML が実行可能

- 場所: `scripts/sddlib/render.py:76-78`
- 再現条件: Markdown に `<script>` やイベント属性などの生 HTML が含まれる場合。
- 確認結果: vendored mistune の `mistune.html()` は `<script>alert(1)</script>` をそのまま出力した。
- 影響: untrusted branch や外部から取得した Markdown の HTML をブラウザで開くと XSS になる可能性がある。
- 修正方向: 入力が完全に trusted であることを明記するか、raw HTML を escape/sanitize し、必要に応じて restrictive CSP を付ける。

#### M-5. README の導入手順がホストごとの実行手順になっていない

- 場所: `README.md:7-13`
- 問題: Claude Code は `--plugin-dir`、Cursor は `~/.cursor/plugins/local/` への配置または symlink と reload が必要だが、具体的なコマンドと skill の名前空間がない。
- 影響: 利用者が clone 後に plugin をロードできず、README の manual check を再現できない。
- 修正方向: Claude Code の `claude --plugin-dir .` と `/sdd:sdd-design`、Cursor の local plugin 配置・Reload Window・`/sdd-design` など、実際の導入と reload 手順を明記する。

#### M-6. pack root と format file の参照場所が矛盾する

- 場所: `skills/sdd/SKILL.md:8,31`, `skills/sdd-design/SKILL.md:18,29,39`
- 問題: `skills/sdd/SKILL.md` 自身を pack root と説明する一方、pack root は `skills/` と `scripts/` を含む親ディレクトリである。また `docs/formats/*` を利用側リポジトリから読むようにも解釈できる。
- 影響: インストール済み plugin で scripts や format 定義が見つからず、design の CONTEXT/ADR 作成が停止する。
- 修正方向: pack root の定義を一箇所に統一し、`<pack-root>/docs/formats/context.md` のように vendor 側の絶対的な関係を明示する。

#### M-7. 自動発火 description が本文の除外規則と矛盾する

- 場所: `skills/using-git-worktrees/SKILL.md:1-8`, `skills/requesting-code-review/SKILL.md:1-8`, `skills/dispatching-parallel-agents/SKILL.md:1-8`, `skills/sdd-finish/SKILL.md:1-4`
- 問題: description は「implementation plans」「completing tasks」「2+ independent tasks」など広い条件で skill を候補にするが、本文では sdd-execute の Task implementer には使わない等の除外を定義している。
- 影響: 不要な worktree 作成、execute と重複する review、serial Task の誤った並列化が起こり得る。
- 修正方向: trigger description に `outside sdd-execute`、`human requests isolation`、`independent investigations only` など観測可能な除外条件を含める。

#### M-8. `find-polluter.sh` がテスト未実行でも成功を報告する

- 場所: `skills/systematic-debugging/find-polluter.sh:41-45,68-72`, `skills/systematic-debugging/root-cause-tracing.md:101-105`
- 再現結果: `bash skills/systematic-debugging/find-polluter.sh .git 'tests/*.py'` は、リポジトリに `.git` が既に存在するため全5テストを skip し、`No polluter found` と終了コード0を返した。
- 影響: polluter を特定できていないのに、テストが clean だという誤った診断になる。
- 修正方向: 対象が開始時点で存在する場合は、測定不能として即時非ゼロ終了する。ドキュメント例も開始時点で存在しない一時パスを使う。script の場所は pack root から解決する。

#### M-9. ledger の入力順序を保持せず Task 番号で並べ替える

- 場所: `scripts/sddlib/ledger.py:20-26`
- 問題: `parse_ledger` が completion record を番号順に sort する。
- 影響: ledger に記録された順序が Task 番号順でない場合、stacked PR の base chain が記録内容と異なる。重複・順序異常も検知されない。
- 修正方向: ledger の順序を保持し、番号の一意性と期待する順序を明示的に検証する。

#### M-10. CLI の `--help` が正常終了コードを返さない

- 場所: `scripts/sddlib/stack.py:99-102`, `scripts/sddlib/review.py:31-34`
- 確認結果: `python3 scripts/stack-prs --help` と `python3 scripts/review-package --help` はヘルプ本文を表示するが終了コード2を返した。
- 問題: `SystemExit(0)` を `int(exc.code or 2)` で2に変換している。
- 影響: shell script や自動検証が help を失敗として扱う。
- 修正方向: `exc.code == 0` を明示的に0として保持し、help の return code をテストする。

#### M-11. stacked branch の既存 ref を無条件に移動する

- 場所: `scripts/sddlib/stack.py:72-75`
- 再現条件: `sdd-stack/task-N` が既に存在する場合、または別 worktree で checkout 中の場合。
- 問題: `git update-ref` を old value の期待値なしで実行する。
- 影響: 既存 branch の tip を失わせたり、別 worktree の状態と ref を不整合にしたりする。
- 修正方向: absent または同一 SHA の ref だけを許可し、既存 ref と checkout 状態を確認する。更新時は expected-old-value を使う。

#### M-12. `pyproject.toml` の存在だけで Poetry を実行する

- 場所: `skills/using-git-worktrees/SKILL.md:104-120`
- 問題: `pyproject.toml` は uv、Hatch、PDM、setuptools、単なる PEP 517 設定でも使われるが、常に `poetry install` を実行する。
- 影響: Poetry 未導入環境で失敗するか、リポジトリの実際の環境管理方法を壊す。
- 修正方向: lockfile、tool 設定、README の手順を検出し、判定できない場合は自動実行せず利用者に確認する。

## Test Gaps

- `tests/test_stack_prs.py:130-170` は branch 名だけを検証し、各 branch が期待する full SHA を指すことを検証していない。
- `tests/test_review_package.py:19-46` は log と stat だけを確認し、`## Diff` に全コミットの patch が含まれることを確認していない。
- `tests/fixtures/plan/2026-01-01-example.md` に Global Constraints や required plan sections がなく、brief からの除外を検証できない。
- Task brief と ledger heading の fence-aware parsing、stacked PR の欠落・重複・不正 SHA・不連続範囲、既存 branch 衝突のテストがない。
- Markdown link の HTML 化と HTML golden files が仕様に記載されているが、`tests/test_render_docs.py` では検証されていない。

## Verification

- `PYTHONPATH=scripts:tests uvx --from pytest pytest tests/ -v`: 14 passed
- `claude plugin validate .`: passed
- `git diff --check`: passed
- `python3 scripts/stack-prs --help`: exit code 2
- `python3 scripts/review-package --help`: exit code 2
- `find-polluter.sh` の既存 `.git` 例: 全テストを skip して exit code 0
- 生 HTML の確認: `<script>alert(1)</script>` が mistune の出力に残る

## Positive Notes

- Claude Code の plugin manifest は `claude plugin validate .` を通過した。
- subprocess 呼び出しは shell interpolation ではなく argv 配列を使っており、確認した範囲に hard-coded secret はなかった。
- render-docs は title と CSS href を HTML escape しており、既存の基本テストは通過している。
- review-package は実装上 `BASE..HEAD` と `-U10` diff を使っており、単一コミット専用に退行しているわけではない。
