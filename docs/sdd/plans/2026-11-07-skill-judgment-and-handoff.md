# SDD Skill Judgment and Handoff Implementation Plan

**Goal:** 重要な共通仕様を前工程で整理して別specへ引き継ぎ、品質と安全を保ったままモデルの裁量を増やす。

**Architecture:** パイプラインskillが判断・共通仕様・実行時引き継ぎの契約を持ち、支援skillはその範囲で手法を提供する。既存の直列subagent実行とデータ形式を保ち、代表シナリオでモデルの振る舞いを確認する。

**Tech Stack:** English skill Markdown、Git、Python 3.11+、pytest、既存SDD CLI、host標準の新規セッションまたはsubagent、静的HTML companion。

**Spec:** `docs/sdd/specs/2026-11-07-skill-judgment-and-handoff-design.md`

## Global Constraints

- 人間に確認するのは、未合意の利用者向け仕様、権限・安全性、破壊的操作、既存の許可を超える外部副作用、高コストまたは不可逆な変更である。
- 支援skillは、合意済みの仕様・制約や呼出元skillの実行契約を上書きしない。
- 分類を下げるために承認や仕様の必要条件を回避してはならない。
- バックエンドspecの中に、後工程と共有する仕様を識別できる節を置く。
- UIだけで完結する変更や後工程のない変更に、架空のバックエンドspecや新しい依存関係は要求しない。
- 重要な未決事項に依存する実装は、合意を捏造して進めない。
- フロントspecは正本のバックエンドspecへのパスと、依存する範囲を示す。
- 後工程に影響する確定・変更事項は、遅くともバックエンド完了を宣言して引き渡す前にspecへ反映する。
- TDDは有力な方法だが、boundedとexecuteの双方で一律の必須条件にはしない。
- subagentの単なる成功宣言や、コミットが増えたことだけでは十分でない。
- finishでは最終状態をカバーするfull suiteの証拠を引き続き必要とし、有効なfull suiteの結果がなければ実行する。
- Taskは直列で実行し、Taskごとに隔離されたsubagentを使う。隔離subagentが使えない場合の`HOST_SUBAGENT_UNAVAILABLE`とcontrollerで代行しない規則を維持する。
- Taskとstacked PRの対応、branch名、コミット範囲、完了台帳、stack reviewのattach・push・land規則を変更しない。Task未完了時の再開は既存どおり一度とする。
- 必須レビューゲートを追加せず、人間が求めたレビューの経路を維持する。調査委譲の裁量を、Task実装の並列化の許可として扱わない。
- planヘッダ、Global Constraintsの明示的な伝達、`## Task N:`、既存CLIの入出力を変更しない。
- HTML関連の対象範囲と運用は現行のままとする。本spec・後続planのcompanionも、既存の文書契約に従う。
- 新しい必須設定、独立した共通仕様書、二重の仕様正本、追加のLLM実行依存を利用側へ要求しない。
- すべての代表シナリオで期待する判断を確認する。期待からの逸脱や未実施があれば、その項目と影響を報告し、改善の検証完了とは扱わない。

## File Structure

| Path | Responsibility |
|---|---|
| `skills/sdd/SKILL.md` | 判断方針の入口、支援skillの適用範囲、bounded開始時のworkspace確認 |
| `skills/sdd-design/SKILL.md` | リスクに基づく質問、共通仕様の先行整理、既存specからの引き継ぎ |
| `skills/sdd-plan/SKILL.md` | 成果・受入条件中心のTask設計、仕様参照と制約の伝達 |
| `skills/sdd-execute/SKILL.md` | Task実行時の裁量、検証証拠、仕様の反映期限、workspace失敗時の扱い |
| `skills/sdd-execute/implementer-prompt.md` | 実装者へ渡す判断範囲、依存する仕様、検証・引き継ぎ報告 |
| `skills/sdd-finish/SKILL.md` | 完了前の仕様反映と、最終状態をカバーする検証証拠 |
| `skills/test-driven-development/SKILL.md`、`skills/test-driven-development/writing-good-tests.md` | 任意で選ぶTDD手法と、振る舞いに基づくテスト |
| `skills/verification-before-completion/SKILL.md` | 主張を支える証拠、再利用条件、失効条件 |
| `skills/using-git-worktrees/SKILL.md` | 隔離要求の尊重、失敗時の許可確認、既存設定に合うsetup |
| `skills/systematic-debugging/SKILL.md`、`skills/systematic-debugging/root-cause-tracing.md`、`skills/systematic-debugging/defense-in-depth.md` | 問題に比例した診断と秘密値を出さない例 |
| `skills/requesting-code-review/SKILL.md`、`skills/requesting-code-review/code-reviewer.md`、`skills/receiving-code-review/SKILL.md` | 依頼されたレビューの範囲、指摘の検証、独立項目の継続 |
| `skills/dispatching-parallel-agents/SKILL.md` | 調査委譲の使い分けと共有状態の安全境界 |
| `skills/sdd-goal/SKILL.md`、`skills/sdd-review-fix/SKILL.md` | 新方針との衝突確認。必要な文言修正のみ |
| `README.md` | 変更後の利用方法と実行構造が不変であることの説明 |
| `docs/evaluations/skill-judgment-and-handoff.md` | パック所有の試用手順、入力fixture、応答用の事実、判定基準、結果の要約 |

全Taskは記載順に実行する。skillとpromptの言語は既存どおり英語とし、本文の言い換えだけでなく例文・チェックリスト・参照文書も整合させる。`scripts/`、`tests/`、`adapters/`、`hooks/`、CSS、`html-visual-clarity`、既存ADR、過去specは変更しない。本planのMarkdown・HTMLは計画成果物として上表と別に扱う。試用結果の詳細は既存の作業領域`.sdd/`へ保存し、利用側に新しい必須成果物を増やさない。

## Task 1: Define risk-based design and shared-spec handoffs

**Depends on:** なし。

**Files:** `skills/sdd/SKILL.md`、`skills/sdd-design/SKILL.md`、`skills/sdd-plan/SKILL.md`を更新。`docs/evaluations/skill-judgment-and-handoff.md`を作成。

**Read:** 承認specのArchitecture、Data flow、Error handling、Testing、Compatibility and boundaries。参照先は`docs/sdd/specs/2026-11-07-skill-judgment-and-handoff-design.md`。

**Implementation:**

1. 試用手順を、設計変更の確認に使う成果物として作成する。承認specの全代表シナリオについて、入力、モデルへ渡さない応答用の事実、期待する判断、観察する副作用、実施記録を定義する。新しい評価runnerやモデル依存は作らない。
2. skill変更前の基準revisionは`4437cf759c900e8c63186e9e2437a7b65582a677`とする。利用可能なhostの新規セッションまたはsubagentで、同じ入力を使って変更前の質問・判断を記録する。作業中の会話履歴を継承させず、試用用の使い捨てリポジトリ以外には実装させない。実行できない項目は未実施として残し、結果を捏造しない。
3. 主要な引き継ぎfixtureは「自分の項目一覧を閲覧・削除できる機能」とする。バックエンド設計の入力では一覧の順序と削除の取消可否を未定にする。応答用の事実は「作成日時降順、同時刻はID降順。削除は即時確定し取消不可。所有者以外は操作不可」とする。フロント引き継ぎの入力では、これらが確定したバックエンドspecと対応する小さな実装・テストを渡す。UIの配置・配色は未定のままとする。
4. `sdd`と`design`に、重要な仕様・権限・不可逆な変更は確認し、合意の範囲内の可逆的な実装判断はモデルが行う方針を明記する。事実は調査してから質問する。全件質問、frontier全枝の消化、最低質問数、分類の一方向化、固定の質問表示、節ごとの承認待ちを必須条件から外す。目的・受入条件・重要な制約の合意と実装前の承認は残す。
5. `design`に、後工程の利用を踏まえた共通仕様の確認とバックエンドspecへの記録を追加する。フロント開始時は関連spec・必要な実装を読み、既知事項を再質問しない。重大な未決・矛盾・新要求だけを影響付きで確認する。既存specに専用節がない場合は既知事項を回収し、面談全体をやり直さない。UIだけの変更には不要なバックエンド設計を要求しない。
6. `plan`から全ステップの完成コード・ファイル全文の義務を外し、成果物・受入条件・依存関係・関連パス・検証方法を求める。正本への参照と必要な文脈をTaskへ含める。既存ヘッダ、Global Constraints、`## Task N:`は変更しない。`sdd`ではTDDを選ばないbounded実装も扱い、workspace希望の確認を失わない。

**Acceptance:** 重要なバックエンド仕様を先に確認し、UI詳細は後に残せる。フロントは別spec・別セッションでも正本を参照できる。軽微な判断に承認待ちを作らない。試用手順には全シナリオの入力と判定基準があり、基準revisionの実施済み・未実施を区別している。

**Verification:**

```bash
uvx --from pytest pytest -q tests/test_md.py tests/test_task_brief.py
git diff --check
git diff -- skills/sdd/SKILL.md skills/sdd-design/SKILL.md skills/sdd-plan/SKILL.md docs/evaluations/skill-judgment-and-handoff.md
```

試用では上記fixtureで、未決事項の早期確認、確定済み事項の参照、UI局所判断の自律進行を確認する。文面一致ではなく、質問・参照・記録の実際の動作をTask reportへ残す。

## Task 2: Align testing, verification evidence, and execution handoffs

**Depends on:** Task 1の判断方針、共通仕様の正本、試用fixture。

**Files:** `skills/test-driven-development/SKILL.md`、`skills/test-driven-development/writing-good-tests.md`、`skills/verification-before-completion/SKILL.md`、`skills/sdd-execute/SKILL.md`、`skills/sdd-execute/implementer-prompt.md`、`skills/sdd-finish/SKILL.md`、`docs/evaluations/skill-judgment-and-handoff.md`を更新。

**Read:** `docs/sdd/specs/2026-11-07-skill-judgment-and-handoff-design.md`のPlan and task handoff、Verification policy、Compatibility and boundaries。`scripts/sddlib/md.py`、`scripts/sddlib/ledger.py`は読み取りのみ。

**Implementation:**

1. TDD skillと`writing-good-tests.md`を、必要に応じて選ぶテスト先行の手法として揃える。description、Always、Iron Law、Rationalizations、Red Flags、完了チェック、Debugging Integration、Final Ruleまで確認し、一律の実装削除・全関数への個別テスト・全変更へのテスト順序の強制を残さない。TDDを選んだ場合に失敗の理由を確かめる説明は残す。
2. verificationに、実行者・コマンド・実際の結果・対象変更・検証範囲が確認できる証拠の契約を記す。同じmessage内での再実行やcontroller自身の実行を一律必須にしない。単なる成功宣言、検証後の対象変更、根拠不足は別扱いにし、必要な再実行を求める。実行していない結果を成功扱いしない。
3. executeとimplementer promptを同じ判断基準に揃える。実装者は制約内の可逆的判断を進め、重要な未合意仕様は`BLOCKED`または`NEEDS_CONTEXT`で返す。reportに検証証拠と、後工程に影響する決定・specへの反映状況を残す。controllerは必要な共通仕様参照とGlobal Constraintsを明示して渡す。
4. 後工程の前提を変える決定は、遅くともバックエンド完了前に正本へ反映する。関連Taskの成果物・コミットに含め、台帳の完了範囲を後から変更しない。finishにも仕様の反映確認を追加し、最終状態をカバーするfull suiteの証拠が有効なら再利用し、なければ実行する。
5. Task単位の直列subagent、完了の成果物確認、HEADとBASE、再開上限一度、台帳構文、レビューを人間の依頼時だけ使う経路、統合メニューの意味を維持する。新しいTask・PR境界や必須reviewerを追加しない。
6. 試用fixtureで、テストより先に実装がある場合、有効なsubagent検証証拠がある場合、報告だけの場合、検証後に対象が変わった場合を分ける。実装中の共通仕様変更が正本へ戻るケースも確認する。

**Acceptance:** boundedとexecuteのTDD適用に矛盾がない。有効な証拠を二重実行せず、不足・失効した証拠を取り直す。後工程の決定が会話・台帳だけに残らない。既存の実行・台帳・stack契約は変わらない。

**Verification:**

```bash
uvx --from pytest pytest -q tests/test_md.py tests/test_task_brief.py tests/test_stack_prs.py
git diff --check
git diff -- skills/test-driven-development skills/verification-before-completion skills/sdd-execute skills/sdd-finish
```

試用用の小さな実装は標準ライブラリのテストで検証できる形にし、fixture内では`python3 -m unittest discover -s tests -v`の実際の出力を使う。結果と対象変更の対応をTask reportへ残す。

## Task 3: Preserve isolation intent during workspace setup

**Depends on:** Task 1のbounded入口とTask 2のexecute変更。

**Files:** `skills/using-git-worktrees/SKILL.md`、`skills/sdd-execute/SKILL.md`、`docs/evaluations/skill-judgment-and-handoff.md`を更新。`skills/sdd/SKILL.md`は入口との矛盾がある場合だけ調整。

**Read:** `docs/sdd/specs/2026-11-07-skill-judgment-and-handoff-design.md`のError handling、Components、Compatibility and boundaries。

**Implementation:**

1. worktreeのIsolate本文、Quick Reference、Common Rationalizationsから、permission failure時に無断でin-placeへ移る説明を除く。隔離を要求されたまま失敗した場合は、代替手段またはin-placeの許可を確認する。既に有効な許可がある場合を除き、自動継続しない。
2. executeのWorkspaceにある「作成失敗後のin-place記録」を同じ条件へ揃える。許可のないfallbackを成功として記録せず、実際に決まったcheckoutだけを台帳へ記録する。通常のworkspace希望確認は従来どおり一度とし、隔離失敗時の代替許可と区別する。
3. setupはREADME、lockfile、既存設定、作業に必要な範囲から選ぶ。`package.json`だけで`npm install`を決めず、不要なinstallやlockfileの生成・変更を避ける。ignore確認、submodule判別、ユーザー変更の保護を維持する。
4. Attachは既存branchをcurrent→reuse→attachで選び、新branchや別branchへのfallbackを作らない。Attach側の本文とQuick Referenceにも、削除したIsolate自動fallbackへの参照を残さない。
5. 試用では、使い捨てfixtureへの作成失敗を入力として与え、モデルが無断移行しないことを確認する。実リポジトリの権限変更、sandbox無効化、共有branchの切り替えで失敗を再現しない。異なるlockfileのfixtureで、既存設定に沿うsetup判断も確認する。

**Acceptance:** 隔離の希望が失敗後も尊重される。無断in-placeや誤った台帳記録がない。Attachの安全規則を維持し、setupで不要な変更を増やさない。

**Verification:**

```bash
uvx --from pytest pytest -q tests/test_stack_prs.py
git diff --check
git diff -- skills/using-git-worktrees/SKILL.md skills/sdd-execute/SKILL.md skills/sdd/SKILL.md
```

失敗時の応答、選んだcheckout、要求した許可、実際の変更をTask reportへ記録する。ユーザーの作業checkoutや既存worktreeを試用用に変更しない。

## Task 4: Make debugging proportional and redact diagnostics

**Depends on:** Task 2の任意TDDと検証証拠の方針。

**Files:** `skills/systematic-debugging/SKILL.md`、`skills/systematic-debugging/root-cause-tracing.md`、`skills/systematic-debugging/defense-in-depth.md`、`docs/evaluations/skill-judgment-and-handoff.md`を更新。

**Read:** `docs/sdd/specs/2026-11-07-skill-judgment-and-handoff-design.md`のJudgment policy、Verification policy、Error handling。

**Implementation:**

1. 再現・証拠収集・原因仮説・修正後の検証を中心にし、全phaseを常に同量行う規則、参考実装の全行読解、三回失敗しただけでarchitecture議論へ進む規則を推奨へ変える。行き詰まりは進捗・不確実性・影響で再評価し、呼出元の再開上限を上書きしない。
2. 失敗テスト先行だけを唯一の修正方法にしない。原因と回帰リスクに応じた検証を求め、Task 2のTDD・証拠契約と揃える。根拠のない変更の積み重ねや、未確認の成功宣言は許可しない。
3. secret有無の診断例を、値を展開しない実際の例へ置き換える。例えば`if [ -n "${IDENTITY:-}" ]; then echo 'IDENTITY: SET'; else echo 'IDENTITY: UNSET'; fi`を用い、`env | grep IDENTITY`のような実値を出す例は除く。root-cause-tracingの環境情報にも同じ制約を適用する。
4. defense-in-depthとroot-cause-tracingの、全レイヤーへ必ず同じ検証を追加する説明や「バグを不可能にした」という保証を改める。信頼境界・実際の迂回経路に対して必要な検証を選び、一般的な防御の原則は残す。`find-polluter.sh`など補助プログラムの動作は変更しない。
5. 試用fixtureには実在しないtoken値を使い、診断結果へ値が出ないことと、有無は確認できることを確認する。単純な不具合で、不要な全体面談・全行読解・追加レイヤー実装へ進まないことも確認する。

**Acceptance:** 原因と証拠を重視しつつ、問題の規模に合う診断を選べる。本文・例文・参照文書が任意TDDと矛盾しない。秘密値をログへ出す手順がない。

**Verification:**

```bash
uvx --from pytest pytest -q tests/test_find_polluter.py
git diff --check
git diff -- skills/systematic-debugging/SKILL.md skills/systematic-debugging/root-cause-tracing.md skills/systematic-debugging/defense-in-depth.md
```

診断例は使い捨てfixtureで実行し、出力と終了状態を確認する。実ユーザーの環境変数や認証情報は使わない。

## Task 5: Align review and investigation support skills

**Depends on:** Task 1の判断範囲とTask 2の呼出元・支援skill間の契約。

**Files:** `skills/requesting-code-review/SKILL.md`、`skills/requesting-code-review/code-reviewer.md`、`skills/receiving-code-review/SKILL.md`、`skills/dispatching-parallel-agents/SKILL.md`、`docs/evaluations/skill-judgment-and-handoff.md`を更新。

**Read:** `docs/sdd/specs/2026-11-07-skill-judgment-and-handoff-design.md`のComponents、Judgment policy、Compatibility and boundaries。

**Implementation:**

1. requesting-code-reviewのdescription、利用条件、任意利用の例、reviewer promptを、人間が求めたレビューの経路に揃える。feature完了や行き詰まりだけを理由に、executeへ自動レビューを復活させない。read-only、根拠付きの指摘、重大性の区別を維持する。
2. receiving-code-reviewから、感謝表現の一律禁止と、一項目が不明ならすべて止める規則を外す。コードとの照合と技術的な反論を残し、依存する項目だけ確認・保留する。独立した修正はまとめてもよいが、影響範囲をカバーする検証を残す。
3. dispatching-parallel-agentsで、独立調査の委譲は効果・費用・文脈から選ぶことを明記する。読み取り調査と並列編集を区別し、後者では所有するファイル・共有資源・統合責任を確認する。同一responseの呼出し形式だけで並列性が保証される説明は避ける。
4. executeのTask実装を並列化しないこと、review-fixで既存stack branchを扱うこと、reviewerが作業checkoutのHEAD・index・branchを変更しないことを維持する。ホスト固有の新しい必須ツールやモデル固定は追加しない。
5. 試用で、明確な独立修正と不明な指摘を混ぜ、不明項目だけを保留できることを確認する。独立調査とTask実装の依頼を分け、前者の裁量が後者の並列化や未依頼レビューの許可にならないことを確認する。

**Acceptance:** 技術的に指摘を検証し、依存項目だけ確認できる。文体の儀礼や自動レビューを再導入せず、共有状態とstack branchを保護する。

**Verification:**

```bash
uvx --from pytest pytest -q tests/test_review_package.py tests/test_stack_prs.py
git diff --check
git diff -- skills/requesting-code-review skills/receiving-code-review/SKILL.md skills/dispatching-parallel-agents/SKILL.md
```

実際に保留した項目、継続した独立作業、委譲判断の理由をTask reportへ残す。レビューの合否をcontrollerの新しい必須ゲートにはしない。

## Task 6: Validate workflows and publish operating guidance

**Depends on:** Task 1からTask 5の変更と検証記録。

**Files:** `README.md`、`docs/evaluations/skill-judgment-and-handoff.md`を更新。`skills/sdd-goal/SKILL.md`、`skills/sdd-review-fix/SKILL.md`は新方針と衝突する文言がある場合だけ修正。

**Read:** `docs/sdd/specs/2026-11-07-skill-judgment-and-handoff-design.md`全体、各Taskのreport、変更済みskillとその参照文書。過去のspec・ADRは読み取りのみ。

**Implementation:**

1. READMEのbounded・TDD・検証・worktree・レビューの説明を実際のskillへ揃える。バックエンド共通仕様→実装中の決定の反映→別セッションのフロントspec、という利用例と、UIだけで完結する変更の例を加える。HTMLの仕様・導入手順は変更しない。
2. goalとreview-fixの表現を確認し、支援skillが新しい全体停止・TDD・検証再実行の必須条件を持ち込まないようにする。goalの機能、review-fixの対象PR、attach・push・land規則は拡張しない。呼出元・支援skill・参照例文を通した整合性レビューを記録する。
3. 最終候補の全代表シナリオを、Task 1と同じ入力で、新しいセッションまたはsubagentから試す。モデルへ判定基準や応答用の事実を先渡ししない。該当skillの変更後の内容が読まれていることを確認する。fixtureの期待を満たしていないのに、少ない質問数だけで合格にしない。
4. 有効な既存結果は、対象skillと必要文脈が変わっていないことを確認して再利用する。変更後の対象をカバーしない結果は取り直す。host・modelを比較条件として記録するが、パックがモデル名を固定する変更はしない。
5. packのrevision、host・model、入力、実際の質問・判断、参照・更新文書、検証出力、期待からの逸脱を記録する。詳細は`.sdd/evaluations/skill-judgment-and-handoff/`、各Taskの報告は`.sdd/reports/`を使う。評価手順書には非機密の結果要約と参照を残し、実行時の秘密値や会話全体をコミットしない。
6. 未実施や失敗があれば、該当項目と理由を報告し、このTaskを検証完了として扱わない。hostで試用できなければ`BLOCKED`または`NEEDS_CONTEXT`を返す。新しい評価基盤の実装や、CIでのモデル起動で迂回しない。修正が必要なら関係するskillに限定して直し、影響する試用を再実行する。

**Acceptance:** 全代表シナリオで期待する判断を確認し、既存の実行・データ契約を保っている。未決事項の早期発見、確定事項の引き継ぎ、重要な質問の維持、可逆的判断の自律進行を実際の記録で示せる。READMEと支援文書に相反する指示がない。

**Verification:**

```bash
uvx --from pytest pytest -q
git diff --check
git diff --name-only 4437cf759c900e8c63186e9e2437a7b65582a677
python3 scripts/html-docs check --staged
```

変更ファイル一覧をFile Structureと照合し、HTML policy・adapter・CSS・CLI・parser・台帳を変更していないことを確認する。Python suiteの成功と、モデル試用の合否を分けて報告する。全Taskの完了後に既存の`sdd-finish`へ進み、push・merge・公開は人間の選択を待つ。
