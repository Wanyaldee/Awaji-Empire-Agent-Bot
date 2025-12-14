# /discord_bot/cogs/mass_mute.py

import discord
from discord.ext import commands, tasks
from datetime import time, timezone, timedelta
import traceback

# 🚨 修正点: bot.py から関数を直接インポート 🚨
from bot import send_admin_dm

# 通知を無効化したいチャンネル名リスト
MUTE_CHANNEL_NAMES = [
    "配信コメント",
    "参加ログ",
]

# JSTのタイムゾーンオブジェクトを正確に定義 (日本時間 +9時間)
JST = timezone(timedelta(hours=+9), 'JST')


class MassMuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # チャンネルに特定の権限設定を適用する内部関数
    async def _apply_notification_mute_to_channel(self, channel, mute_role):
        try:
            # チャンネルの現在の権限上書きを取得
            overwrite = channel.overwrites_for(mute_role)

            # 通知を無効化 (メッセージの送信を明示的に拒否)
            if overwrite.send_messages is not False:
                overwrite.send_messages = False
                await channel.set_permissions(mute_role, overwrite=overwrite, reason="自動ミュートタスク: 通知無効化のため")
                return True # 変更があった
        except Exception:
            # 権限変更中にエラーが発生しても Bot は落とさない
            traceback.print_exc()
        return False # 変更がなかった、またはエラー

    @commands.Cog.listener()
    async def on_ready(self):
        # 定時タスクの開始
        if not self.daily_mute_check.is_running():
            self.daily_mute_check.start()
            print("🔄 SCHEDULED TASK STARTED: 毎日16:00の自動ミュートチェックを開始しました。")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """新しいチャンネルが作成されたとき、自動でミュートを適用"""
        if channel.name in MUTE_CHANNEL_NAMES and isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            # ギルドの @everyone ロールを取得
            mute_role = channel.guild.default_role
            if await self._apply_notification_mute_to_channel(channel, mute_role):
                print(f"✅ Auto-Mute: 新規チャンネル {channel.name} に通知ミュートを適用しました。")
                title = "📢 Auto-Mute 適用"
                description = f"新規チャンネル **#{channel.name}** に通知ミュート（@everyone のメッセージ送信拒否）を適用しました。"
                await send_admin_dm(self.bot, title, description, discord.Color.gold())


    # 毎日 16:00 JST に実行されるタスク
    @tasks.loop(time=time(hour=16, minute=0, tzinfo=JST))
    async def daily_mute_check(self):
        print("--- 🔔 定時ミュートチェックを開始 ---")

        # Botが参加しているすべてのギルドで実行
        for guild in self.bot.guilds:
            mute_role = guild.default_role # @everyone ロール

            for channel in guild.channels:
                # 対象チャンネル名かつ、テキストまたはフォーラムチャンネルのみ
                if channel.name in MUTE_CHANNEL_NAMES and isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                    if await self._apply_notification_mute_to_channel(channel, mute_role):
                        print(f"✅ MUTE APPLIED: ギルド '{guild.name}' のチャンネル {channel.name} に通知ミュートを適用しました。")

        print("--- ✅ 定時ミュートチェックを完了 ---")

        await send_admin_dm(
            self.bot,
            title="✅ 定時タスク完了",
            description="毎日 16:00 の通知ミュート設定の定時確認が完了しました。",
            color=discord.Color.blue()
        )

    @daily_mute_check.before_loop
    async def before_daily_mute_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(MassMuteCog(bot))
