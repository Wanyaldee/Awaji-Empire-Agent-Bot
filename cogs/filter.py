# /discord_bot/cogs/filter.py

import discord
from discord.ext import commands
import re
import traceback

# 修正点: config.py と bot.py から必要なものを直接インポート
from config import CODE_CHANNEL_ID
from bot import send_admin_dm

# 8桁の英数字（オレマシンコード）に完全に一致する正規表現
CODE_PATTERN = re.compile(r'^[a-zA-Z0-9]{8}$', re.ASCII)


class FilteringCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # 1. Bot自身のメッセージは無視
        if message.author.bot:
            return

        # 2. 対象チャンネル以外は無視 (IDは文字列として比較)
        if str(message.channel.id) != CODE_CHANNEL_ID:
            return

        # 3. コードパターンに一致する場合は無視 (正規のオレマシンコード投稿)
        if CODE_PATTERN.fullmatch(message.content):
            return

        # 4. フィルタリング実行 (削除とDM送信)
        try:
            await message.delete()

            title = "フィルタリング削除成功"
            description = (f"チャンネル: **#{message.channel.name}**\n"
                           f"ユーザー: {message.author.mention} ({message.author.id})\n"
                           f"投稿内容:\n```\n{message.content}\n```")

            await send_admin_dm(self.bot, title, description, discord.Color.green())

        except discord.Forbidden:
            # Botにメッセージ削除権限がない場合の通知
            title = " フィルタリング権限エラー"
            description = (f"チャンネル **#{message.channel.name}** でメッセージを削除できませんでした。\n"
                           f"Botの権限（メッセージの管理）を確認してください。\n"
                           f"ユーザー: {message.author.mention}\n"
                           f"投稿内容:\n```\n{message.content}\n```")

            await send_admin_dm(self.bot, title, description, discord.Color.red())
        except Exception:
            # その他の予期せぬエラー
            traceback.print_exc()


async def setup(bot):
    await bot.add_cog(FilteringCog(bot))
