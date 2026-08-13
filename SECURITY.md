# Security Policy

Hermes Builderは、terminal・filesystem・外部サービスへ接続できるHermes Agentを構築します。利便性より、最小権限と明示的な認証を優先します。

## Secrets

- API key、Bot token、OAuth token、passwordをissueやlogへ貼らないでください。
- answers JSONとplan JSONへ秘密値を保存しないでください。
- `.env`、`auth.json`、provider credentialをrepositoryへcommitしないでください。
- 漏えいが疑われる場合は、先にprovider側でcredentialを失効・再発行してください。

## Installer trust

`curl | bash` / `irm | iex` は取得先のcodeを実行します。

- READMEの公式repository URLだけを使う
- productionではrelease tagまたはcommitへ固定する
- release assetのchecksum/signature対応後は必ず検証する
- forkや短縮URLからinstallerを実行しない

## Gateway

- allowlistまたはDM pairingを必須にする
- `GATEWAY_ALLOW_ALL_USERS=true`をproductionで使わない
- Teams、LINE等のwebhookはTLSと認証を持つendpointだけを公開する
- team/public gatewayへterminal・file・code executionを初期公開しない
- tool policyの配列型を保持できない場合は構築を停止し、文字列へ劣化させない
- critical security auditが失敗した場合は構築成功として扱わない

## Reporting

脆弱性は公開issueへ詳細を書かず、repository ownerへ非公開で連絡してください。報告には影響version、再現条件、想定される影響を含めてください。秘密値や実データは添付しないでください。
