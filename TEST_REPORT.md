# Hermes Builder テスト報告

最終更新: 2026-08-13

## 結論

Hermes Builder `v0.1.1`は、Apple Silicon上のクリーンなUbuntu 24.04およびDebian 12コンテナで、Nous Research公式Hermes installerを含む初回構築と2回目の再適用に成功しました。

外部サービスのOAuth、Bot登録、公開webhook、API keyを使う疎通確認と、macOS / WSL2 / Windowsでの完全インストールは未検証です。

## 対象

- Builder: `v0.1.1`
- Hermes ref: `v2026.8.3`
- Hermes commit: `3c27eb6234bf91b8ceee9e9071591b31e9b148cb`
- Docker host: macOS / Apple Silicon / arm64
- Container user: passwordless sudoを持つ非rootユーザー
- 初期package: `ca-certificates`、`curl`、`sudo`

## 実行した検証

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash -n install.sh
bash tests/install_e2e.sh
bash tests/docker/run.sh
```

Docker E2Eは各OSで次を確認します。

1. 不足する`tar` / `xz`の自動導入
2. 公式installerによるPython 3.11、uv、Git、Node.js、ffmpeg、ripgrep、Playwright Chromiumの導入
3. Hermes repositoryの固定commit checkout
4. 71個のbundled skill同期
5. `research-operator` profile、SOUL、planの生成
6. profileとplanのpermissionが`0600`
7. CLI / gateway toolset policyの適用
8. `agent.disabled_toolsets`とplugin型Teams allowlistがYAML文字列ではなく配列であること
9. `hermes doctor`と`hermes security audit --fail-on critical`
10. `--skip-hermes`を使ったBuilder再適用
11. 同一秒を含む連続再適用でのbackup名衝突回避と既存SOUL保護

## 結果

| Test | Ubuntu 24.04 | Debian 12 |
|---|---:|---:|
| Docker image build | PASS | PASS |
| Official Hermes install | PASS | PASS |
| Exact commit checkout | PASS | PASS |
| Builder profile / SOUL / plan | PASS | PASS |
| Permission checks | PASS | PASS |
| Global deny / Teams allowlistの配列型検査 | PASS | PASS |
| Doctor / critical audit gate | PASS | PASS |
| Second apply / backup | PASS | PASS |

Python unit testは41件すべてPASS、fake Hermesを使うローカルinstaller 3連続適用E2EもPASSしています。

PowerShell版はMicrosoft公式PowerShell 7.5 Docker imageで構文解釈と既定commitのdry-runがPASSしています。これはWindows実機の完全E2Eではありません。

## Docker検証で発見・修正した問題

### 最小Linuxに`xz`がない

公式Hermes installerがNode.jsの`.tar.xz`を展開できませんでした。Builder installerにarchive toolの事前確認を追加し、`apt`、`dnf`、`yum`、`apk`、`pacman`で補完するよう修正しました。

### release tagを`--commit`へ渡していた

Hermes公式POSIX installerの`--commit`はcommit SHAを要求します。Builderは既定releaseを40文字のSHAへ固定し、custom refはGitHub APIでSHAへ解決するよう修正しました。POSIX版とPowerShell版の両方で、公式installer自体もそのSHAから取得し、同じSHAを`--commit` / `-Commit`へ渡します。

### tool policyの配列が文字列として保存されていた

Hermes `config set`はJSON風文字列を配列へ変換しないため、旧方式では`agent.disabled_toolsets`が実効的なdenyになりませんでした。Hermes付属のPyYAMLを使う原子的更新へ変更し、plugin型gatewayにも明示allowlistを保存しました。Docker内で両方の型と値を直接検査しています。

### GitHub rawの一時的なHTTP 429

クリーンDocker再検証中に公式installer取得がHTTP 429となりました。POSIX版とPowerShell版のdownloadへ有限回retryを追加し、再実行で完走しました。

### 追加hardening

- critical auditを必須ステップ化
- SOUL、plan、YAML policyを`0600`の一時ファイルから原子的に置換
- 同一秒の再適用でも衝突しないSOUL backup名
- answers内の既知secret形式・terminal制御文字を拒否
- answers 1 MiB、plan 2 MiBの入力上限と過剰nestingのclean error
- 公式plugin catalogとの差分を再監査し、A2A adapterを追加
- Windows実行時に`PYTHONUTF8=1`を設定し、日本語・記号出力のlocale依存エラーを防止
- POSIX permissionとfake executableのテストをOS capabilityに合わせて分離

## 残る制約と上流リスク

- Hermes `v2026.8.3`の`uv.lock`は`uv sync --locked`で更新要求となり、公式installerがPyPI resolveへfallbackします。
- Hermes側のPython依存にHIGH 3件、MODERATE 3件の既知脆弱性があります。critical findingはありません。
- Hermes側のbrowser / web / ui-tui workspaceにnpm build-tool advisoryがあります。
- 初回導入はffmpegとPlaywrightを含むため、数百MB規模のdownloadとdisk消費が発生します。
- 認証情報を使わないDocker E2Eでは、LLM provider、Slack、Teams、LINE、その他gateway、MCPの実接続を検証していません。
- Windows installerはsyntax CIのみで、完全E2Eは未実施です。

## Release判定

ローカル配布物としてのLinux bootstrap、決定論的plan生成、profile再適用は合格です。各releaseではGitHub tag作成後にraw URLを確認します。macOS実機、WindowsまたはWSL2、代表gateway 1つの認証付きsmoke testは継続課題です。
