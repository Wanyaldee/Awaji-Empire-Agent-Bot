# /discord_bot/config.py

# 🚨 必須項目: Discord Botの各種ID設定 🚨

# 管理者ユーザーID (DMログ送信先)
ADMIN_USER_ID = 738880478823841932  # 👈 あなたのDiscord ID (整数値) に置き換えてください！

# オレマシンコードチャンネルID (フィルタリング対象)
# IDが長いため、安全のため文字列として扱います。
CODE_CHANNEL_ID = "1447584603425476720"  # 👈 実際のチャンネルID (文字列) に置き換えてください！

# 通知を抑制したいチャンネル名のリスト
# 🚨 サーバー内でのチャンネル名と完全に一致させてください 🚨
MUTE_CHANNEL_NAMES = ["参加ログ", "配信コメント"]
# 例: MUTE_CHANNEL_NAMES = ["general", "bot-spam"]
