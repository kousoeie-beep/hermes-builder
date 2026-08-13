# Hermes Builder

1行のコマンドからヒアリングを始め、利用目的に合うHermes Agentを構築するbootstrapperです。

Hermes本体の導入だけでなく、専用profile、SOUL、toolsets、gateway、MCP、安全設定、常駐化、疎通確認までを1本のフローにまとめます。

> 現在のreleaseはv0.1.2です。installerとBuilder本体を同じtagへ固定しています。

## Quick start

macOS / Linux / WSL2:

```bash
curl -fsSL --retry 5 --retry-delay 2 https://raw.githubusercontent.com/kousoeie-beep/hermes-builder/v0.1.2/install.sh | bash
```

Windows PowerShell:

```powershell
iex (irm https://raw.githubusercontent.com/kousoeie-beep/hermes-builder/v0.1.2/install.ps1)
```

実行すると、次の順番で進みます。

1. OSと前提条件を確認
2. Nous Research公式Hermes Agentを固定versionで導入
3. Hermesの目的・用途・自律度・利用者・設置場所をヒアリング
4. 専用profileとSOULを生成
5. 用途に応じたtoolsetsとgateway権限を設定
6. Hermes公式wizardでLLM providerを認証
7. 選択したgatewayを設定
8. MCPを選択・認証
9. gatewayをuser serviceとして常駐化（`--no-service`で省略可）
10. `hermes doctor`、security audit、deep statusで検証

POSIX版の1行コマンドには`curl`が必要です。最小LinuxでHermesのNode.js展開に必要な`tar`/`xz`がない場合、Builderが`apt`、`dnf`、`yum`、`apk`、`pacman`のいずれかを使って補完します。

## Architecture

```text
install.sh / install.ps1
        │
        ├─ Layer 1: official Hermes bootstrap
        │    ├─ Python / uv / Node / ffmpeg / ripgrep
        │    └─ Hermes Agent (pinned release)
        │
        └─ Layer 2: Hermes Builder
             ├─ interview
             ├─ deterministic plan
             ├─ profile + SOUL
             ├─ toolset policy
             ├─ gateway onboarding
             ├─ MCP onboarding
             └─ doctor / status verification
```

Hermes本体はforkしません。公式Hermesの更新と、Hermes Builder独自のヒアリング・設定ロジックを分離し、追従コストを抑えます。

## ヒアリング内容

- Hermesの名前と最重要ミッション
- 調査、開発、業務自動化、コンテンツ、営業支援、個人アシスタント
- 対話中心、定期実行＋承認、限定自律
- 自分専用、信頼済みチーム、顧客・外部ユーザー
- 普段使いPC、常時起動PC、VPS・クラウド
- Telegram、Discord、Slack、Google Chat、WhatsApp / Cloud API、Signal、SMS、Email、Home Assistant、Mattermost、Matrix
- DingTalk、Feishu/Lark、WeCom / Callback、Weixin、BlueBubbles / Photon、QQ、Yuanbao、Microsoft Teams、LINE
- ntfy、Raft、IRC、Buzz、SimpleX、A2A、Webhook、OpenAI互換API
- GitHub、Google Workspace、Microsoft 365、Notion、Linear、n8n、Database、監視系、custom MCP
- Nous Portal、OAuth、API key、local model

秘密値はHermes Builderのヒアリングでは入力しません。API key、Bot token、OAuth credentialは各公式wizardへ引き渡し、Hermes側のcredential領域へ保存します。

## 「全gateway対応」の意味

Hermes Builderは、Hermes Gatewayが提供する複数platformを選択・構成できる入口を提供します。全platformを無条件に有効化するものではありません。

外部サービス側の同意は省略できません。

- Slack: Slack App作成とWorkspace承認
- Microsoft Teams: Microsoft login、Bot登録、公開HTTPS webhook、Teamsへのapp install
- LINE: Messaging API channelと公開HTTPS webhook
- WhatsApp: QR loginまたはMeta Cloud API
- Telegram: BotFatherでのBot作成
- Discord: Bot作成とserverへの招待

Builderは必要なplatformだけを選ばせ、公式設定画面を起動し、最後に接続状態を検証します。

Hermes `v2026.8.3`で一部の新しいgatewayはplugin adapterです。この場合もgateway自体の設定は公式wizardへ渡します。チーム・外部向けprofileでは、built-in/pluginを問わずCLIと全gatewayの`platform_toolsets`を明示配列へ置換します。Gatewayには`no_mcp`を付け、Hermes実行環境のregistryを列挙して許可外toolsetを`agent.disabled_toolsets`へ適用します。registryを検査できなければセットアップを停止します。設定はHermes付属の安全なYAML loaderで原子的に更新し、配列を文字列として誤保存しません。

## Safety defaults

- `approvals.mode = smart`
- `approvals.cron_mode = deny`
- destructive slash commandの確認を有効化
- file mutation verifierを有効化
- gatewayはallowlistまたはDM pairing前提
- `GATEWAY_ALLOW_ALL_USERS`を設定しない
- `--yolo`を使わない
- 秘密値をplan、answers、SOUL、logへ保存しない
- チームgatewayではterminal、file、code execution、computer use、cron、delegationを初期無効化
- 外部ユーザーgatewayではmemory、session search、browserも初期無効化
- チーム・外部向けは専用profile全体へ同じdenyを適用（CLIも制限対象）
- チーム・外部向けgatewayではMCPを初期無効化し、認証後に用途別で明示許可
- 既存profileのSOULは既定で上書きせず、`SOUL.proposed.md`へ保存

## CLI

```text
hermes-builder
├── setup       interview → plan → apply
├── plan        planだけ作る
├── apply       保存済みplanを適用・再開
├── doctor      profileを診断
├── catalog     用途・gateway・integration一覧
└── completion  bash / zsh / fish completion
```

### 対話セットアップ

```bash
hermes-builder setup
```

### 変更前の確認

```bash
hermes-builder setup --answers examples/research-operator.json --dry-run --yes
```

### 回答ファイルから構築

```bash
hermes-builder setup \
  --answers examples/research-operator.json \
  --non-interactive \
  --yes
```

`--non-interactive`ではprovider・gateway・MCPのOAuth/秘密値入力をスキップします。後から対話端末で同じplanを適用してください。

```bash
hermes-builder apply ~/.config/hermes-builder/plans/research-operator.json
```

plan内の`commands`やtool policyは監査表示用です。適用時は検証済みの`answers`から再生成し、JSONへ任意コマンドを追加しても実行しません。構成を変える場合は`answers`を変更してplanを作り直してください。

### 個別ステップを後回しにする

```bash
hermes-builder setup --skip-provider
hermes-builder setup --skip-gateways
hermes-builder setup --skip-mcp
hermes-builder setup --no-service
```

`--skip-gateways`は認証wizard、service操作、疎通確認だけを後回しにします。既に稼働中のgatewayから権限が漏れないよう、allowlist、`no_mcp`、global denyなどの安全policyは常に適用します。

### Completion

```bash
hermes-builder completion zsh > ~/.zfunc/_hermes-builder
hermes-builder completion bash > ~/.local/share/bash-completion/completions/hermes-builder
hermes-builder completion fish > ~/.config/fish/completions/hermes-builder.fish
```

## Answers schema

```json
{
  "profile_name": "research-operator",
  "display_name": "Research Operator",
  "purpose": "根拠つきの調査レポートを作る",
  "use_cases": ["research", "operations"],
  "autonomy": "scheduled_review",
  "access_scope": "trusted_team",
  "deployment": "always_on",
  "gateways": ["slack", "teams"],
  "integrations": ["github", "linear"],
  "provider_mode": "decide_later",
  "workspace": "~/work",
  "language": "ja",
  "persona_style": "collaborative"
}
```

API keyやtokenに見えるfieldが含まれている場合、Builderは回答ファイルを拒否します。

## Installer options

```bash
bash install.sh --help
bash install.sh --dry-run --source-dir "$PWD" \
  --answers examples/research-operator.json --non-interactive \
  --skip-gateways
```

`install.sh`と`install.ps1`は、`--skip-provider` / `-SkipProvider`、`--skip-gateways` / `-SkipGateways`、`--skip-mcp` / `-SkipMcp`、`--no-service` / `-NoService`をBuilder本体へ引き渡します。安全policyは`--skip-gateways`でも適用されます。

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `HERMES_REF` | `v2026.8.3` | Hermesのtag/commit pin |
| `HERMES_COMMIT` | releaseの固定SHA | Hermesの厳密なcommit pin |
| `HERMES_BUILDER_REPO` | `kousoeie-beep/hermes-builder` | Builder repository |
| `HERMES_BUILDER_REF` | `v0.1.2` | Builder branch/tag |
| `HERMES_BUILDER_HOME` | `~/.local/share/hermes-builder` | Builder install先 |
| `HERMES_BUILDER_STATE_HOME` | `~/.config/hermes-builder` | plan等のstate保存先 |
| `HERMES_BUILDER_BIN_DIR` | `~/.local/bin` | command install先 |

installer自身と、そこから取得するBuilder本体を同じ`v0.1.2` tagへ固定しています。更新時は新しいrelease tagを発行し、両方を同時に切り替えます。

Hermes本体は`v2026.8.3`のrelease commit `3c27eb6234bf91b8ceee9e9071591b31e9b148cb`へ固定します。POSIX版とPowerShell版の両方が公式installer自体を40文字のcommit SHAから取得し、そのSHAを公式installerへ渡します。そのため、同じtagが将来別のcommitを指しても導入内容は変わりません。別versionで`HERMES_COMMIT`を省略した場合は、`HERMES_REF`をGitHub APIでcommit SHAへ解決します。厳密な再現性が必要なら両方を対で指定してください。

## Development

Builderのbootstrapとplan生成には外部Python packageは不要です。tool policyのYAML配列を適用する段階では、先に導入済みのHermes自身が同梱するPyYAMLを使用し、見つからなければ安全側に停止します。

```bash
PYTHONPATH=src python3 -m hermes_builder --help
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash -n install.sh
bash tests/install_e2e.sh
bash tests/docker/run.sh
bash install.sh --dry-run --source-dir "$PWD" \
  --answers examples/research-operator.json --non-interactive
```

実機E2Eでは空のVMまたは専用OSユーザーを使ってください。普段使いの`~/.hermes`を検証対象にしないでください。

`tests/docker/run.sh`はUbuntu 24.04とDebian 12相当の非rootユーザー上で、Hermes公式installerを含む初回構築とBuilderの再適用を検証します。API keyや外部gateway認証は行いません。

### 検証済み環境

2026-08-13時点のローカルDocker（Apple Silicon / arm64）で、次を実測しています。

| 環境 | 初回の公式Hermes導入 | Builder構築 | 2回目の再適用・backup |
|---|---:|---:|---:|
| Ubuntu 24.04 | PASS | PASS | PASS |
| Debian 12 (`bookworm-slim`) | PASS | PASS | PASS |

各テストは`ca-certificates`、`curl`、`sudo`だけを事前導入した非rootユーザーから開始し、Python 3.11、uv、Git、Node.js、ffmpeg、ripgrep、Playwright Chromium、Hermesの依存関係を公式installer経由で実際に導入しています。詳細は[TEST_REPORT.md](TEST_REPORT.md)を参照してください。

macOS、WSL2、WindowsはCI定義を用意していますが、この時点ではローカルでの完全インストール実測は未完了です。公開tagのraw URLはreleaseごとに疎通確認します。

### 既知の上流依存事項

- Hermes `v2026.8.3`の`uv.lock`は公式installerの`uv sync --locked`で更新要求となり、installer自身のfallbackで`.[all]`を導入します。構築は成功しますが、完全なlockfile再現ではありません。
- 2026-08-13の`hermes security audit`では、Hermes側のPython依存にHIGH 3件（`aiohttp 3.14.1`、`cryptography 48.0.1`）とMODERATE 3件が報告されます。Builderはcriticalのみを失敗条件にしており、この監査は通過します。
- `hermes doctor`はHermes側のnpm build-tool advisoryを報告します。
- Slack、Teams、LINE等の外部認証、公開webhook、LLM provider、MCPの実接続は秘密値とサービス側の承認が必要なためDocker E2Eの対象外です。

これらを隠して「完全」とは扱いません。Builder固有のクリーンインストールと再適用は合格、外部認証と上流依存の解消はrelease判定上の別項目です。

## Current scope

v0.1.2で行うこと:

- macOS / Linux / WSL2 / Windows installer
- 決定論的ヒアリングとplan生成
- 専用profile / SOUL生成
- 利用目的に応じたtoolset policy
- Hermes公式gateway / MCP wizardへの引き渡し
- user service化と診断

今後追加する候補:

- platformごとの認証進捗をmachine-readableに保存
- connection testのplatform別adapter
- profile distributionとしての配布
- 署名済みrelease assetとchecksum検証
- 管理画面版のヒアリング
- team policy templateと監査report

## License

MIT。Hermes Agent本体はNous Researchの別projectであり、それぞれのlicenseと利用規約に従います。
