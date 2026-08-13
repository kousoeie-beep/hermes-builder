from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    key: str
    label: str
    description: str


USE_CASES = (
    Choice("research", "調査・情報収集", "Web、X、資料を調べて根拠つきで整理する"),
    Choice("software", "開発・コード", "設計、実装、テスト、レビューを支援する"),
    Choice("operations", "業務自動化", "定型作業、監視、定期処理を自動化する"),
    Choice("content", "コンテンツ制作", "記事、SNS、画像、動画の制作を支援する"),
    Choice("sales_support", "営業・顧客対応", "提案、調査、顧客対応、CRM作業を支援する"),
    Choice("personal_assistant", "個人アシスタント", "予定、情報整理、日常タスクを支援する"),
)

AUTONOMY = (
    Choice("interactive", "対話中心", "人が依頼した時だけ動く"),
    Choice("scheduled_review", "定期実行＋承認", "定期処理するが外部操作前に人が確認する"),
    Choice("autonomous_limited", "限定自律", "事前に許可した範囲だけ自動実行する"),
)

ACCESS_SCOPES = (
    Choice("owner", "自分専用", "所有者だけが使う"),
    Choice("trusted_team", "信頼済みチーム", "allowlistに入れたメンバーが使う"),
    Choice("public", "顧客・外部ユーザー", "不特定または広い利用者を想定する"),
)

DEPLOYMENTS = (
    Choice("laptop", "普段使いPC", "ログイン中に使うMac・Windows・Linux PC"),
    Choice("always_on", "常時起動PC", "Mac miniや社内サーバーなど常時稼働する端末"),
    Choice("server", "VPS・クラウド", "外部から常時アクセスするサーバー"),
)

PROVIDERS = (
    Choice("nous", "Nous Portal", "OAuth中心で最短セットアップ"),
    Choice("oauth", "既存サブスクリプション", "ChatGPT、Claude等のOAuthを使う"),
    Choice("api_key", "APIキー", "OpenRouter等のAPIキーを使う"),
    Choice("local", "ローカルモデル", "LM Studio、Ollama等を使う"),
    Choice("decide_later", "ウィザードで決める", "Hermes公式model wizardで比較して決める"),
)

GATEWAYS = (
    Choice("telegram", "Telegram", "Bot API。個人利用の導入が比較的簡単"),
    Choice("discord", "Discord", "Botをサーバーへ招待して利用"),
    Choice("slack", "Slack", "Socket Mode対応。Workspace承認が必要"),
    Choice("teams", "Microsoft Teams", "公開HTTPS webhookとMicrosoft認証が必要"),
    Choice("google_chat", "Google Chat", "Google Cloud側のBot設定が必要"),
    Choice("whatsapp", "WhatsApp", "QRで個人アカウントへ接続"),
    Choice("whatsapp_cloud", "WhatsApp Cloud API", "Meta Businessと公開webhookが必要"),
    Choice("signal", "Signal", "電話番号とsignal-cli系の設定が必要"),
    Choice("sms", "SMS / Twilio", "Twilio等のprovider設定が必要"),
    Choice("email", "Email", "IMAP/SMTPまたは対応providerを設定"),
    Choice("homeassistant", "Home Assistant", "URLとlong-lived tokenで接続"),
    Choice("mattermost", "Mattermost", "Bot tokenとserver URLを設定"),
    Choice("matrix", "Matrix", "homeserverとaccess tokenを設定"),
    Choice("dingtalk", "DingTalk", "DingTalk Appのcredentialを設定"),
    Choice("feishu", "Feishu / Lark", "QR作成またはApp credentialで接続"),
    Choice("wecom", "WeCom", "Enterprise WeChat Appとして接続"),
    Choice("wecom_callback", "WeCom Callback", "callback受信用adapter"),
    Choice("weixin", "Weixin / WeChat", "QRでiLink Botへ接続"),
    Choice("bluebubbles", "BlueBubbles / iMessage", "Mac上のBlueBubbles serverが必要"),
    Choice("photon", "Photon / iMessage", "Photonのmanaged iMessageへ接続"),
    Choice("qqbot", "QQ Bot", "QQ Open PlatformのBotを設定"),
    Choice("yuanbao", "Yuanbao", "Tencent Yuanbao adapterを設定"),
    Choice("line", "LINE", "Messaging APIチャネルとwebhookが必要"),
    Choice("ntfy", "ntfy", "通知topicへ接続"),
    Choice("raft", "Raft", "Raft adapterを設定"),
    Choice("irc", "IRC", "IRC serverとchannelへ接続"),
    Choice("buzz", "Buzz", "Buzz adapterを設定"),
    Choice("simplex", "SimpleX", "SimpleX Chat adapterへ接続"),
    Choice("a2a", "A2A", "Agent-to-Agent protocol。既定はlocalhost限定"),
    Choice("webhook", "Webhook", "HMAC署名付きHTTP endpointを公開"),
    Choice("api_server", "OpenAI互換API", "loopbackまたは認証付きAPIとして公開"),
)

INTEGRATIONS = (
    Choice("github", "GitHub", "Issue、PR、repository操作"),
    Choice("google_workspace", "Google Workspace", "Drive、Gmail、Calendar"),
    Choice("microsoft_365", "Microsoft 365", "Outlook、SharePoint、Teams会議"),
    Choice("notion", "Notion", "ページ・DBの読み書き"),
    Choice("linear", "Linear", "Issue・project操作"),
    Choice("n8n", "n8n", "workflowの管理・実行"),
    Choice("database", "Database", "Postgres等への限定接続"),
    Choice("observability", "監視・分析", "Sentry、PostHog等"),
    Choice("custom", "その他のMCP", "URLまたはstdio commandで追加"),
)

TOOLSETS_BY_USE_CASE: dict[str, set[str]] = {
    "research": {"web", "browser", "x_search", "session_search", "file", "memory"},
    "software": {"terminal", "file", "code_execution", "vision", "delegation", "session_search"},
    "operations": {"web", "browser", "terminal", "file", "cronjob", "delegation"},
    "content": {"web", "browser", "file", "vision", "image_gen", "skills"},
    "sales_support": {"web", "browser", "file", "memory", "session_search"},
    "personal_assistant": {"web", "browser", "memory", "cronjob", "session_search"},
}

MCP_RECOMMENDATIONS: dict[str, list[str]] = {
    "github": ["GitHub MCPをpickerまたはcustom MCPとして接続"],
    "google_workspace": ["Google Drive / Gmail / Calendar MCPを必要なものだけ接続"],
    "microsoft_365": ["Microsoft 365 / Graph系MCPを最小権限で接続"],
    "notion": ["Notion MCPを対象workspace限定で接続"],
    "linear": ["Hermes公式catalogのLinear MCPを候補にする"],
    "n8n": ["Hermes公式catalogのn8n MCPを候補にする"],
    "database": ["read-only credentialを使うDatabase MCPから開始"],
    "observability": ["Sentry / PostHog等のread-only MCPから開始"],
    "custom": ["hermes mcp addでURLまたはstdio MCPを追加"],
}
