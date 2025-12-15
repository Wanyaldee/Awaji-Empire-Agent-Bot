import discord
from discord.ext import commands, tasks
import asyncio
import datetime
# configファイルから必要な設定値をインポート
# from config import GUILD_ID, MUTE_ROLE_ID

# 🚨 修正点: config.py から ADMIN_USER_ID をインポートする 🚨
from config import ADMIN_USER_ID

class MassMuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 🚨 修正点: configからインポートしたIDを使用 🚨
        self.owner_id = ADMIN_USER_ID
        self.daily_mute_check.add_exception_type(asyncio.CancelledError)
        self.daily_mute_check.start()

    def cog_unload(self):
        self.daily_mute_check.cancel()

    # ----------------------------------------------------
    # 🌟 コア機能の分離とDMログの追加 (ロジック本体は変更なし)
    # ----------------------------------------------------
    async def execute_mute_logic(self, trigger: str):
        """
        通知ミュートを実行し、DMでログを送信する共通ロジック。
        :param trigger: 実行をトリガーしたイベント名 ("Startup" or "Daily Task")
        """

        # --- ここに実際のミュートON/OFFのロジックを記述 ---
        # ----------------------------------------------------

        # DMログメッセージの作成
        log_message = f"✅ 通知ミュートの状態を再設定しました。\nトリガー: **{trigger}**"

        # DMログの送信 (self.owner_id には config.ADMIN_USER_ID の値が入っている)
        owner = self.bot.get_user(self.owner_id)
        if owner:
            try:
                await owner.send(log_message)
                print(f"DM log sent to owner. Trigger: {trigger}")
            except Exception as e:
                print(f"Failed to send DM log to owner: {e}")
        else:
            print(f"Warning: Owner with ID {self.owner_id} not found.")

        print(f"Mute check logic executed successfully. Trigger: {trigger}")
        pass # 仮の実装

    # ----------------------------------------------------
    # 🌟 起動時イベントのフック (on_ready)
    # ----------------------------------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot is ready. Executing initial mute check...")
        await self.execute_mute_logic("Startup")

    # ----------------------------------------------------
    # 🌟 定時タスク (daily_mute_check)
    # ----------------------------------------------------
    @tasks.loop(time=[
    datetime.time(0, 0, tzinfo=datetime.timezone.utc),   # 0:00 UTC (JST 9:00)
    datetime.time(8, 0, tzinfo=datetime.timezone.utc),   # 8:00 UTC (JST 17:00)
    datetime.time(16, 0, tzinfo=datetime.timezone.utc)  # 16:00 UTC (JST 1:00 a.m.)
    ])
    async def daily_mute_check(self):
        print("Daily mute check triggered.")
        await self.execute_mute_logic("Daily Task")

    @daily_mute_check.before_loop
    async def before_daily_mute_check(self):
        await self.bot.wait_until_ready()
        print("Waiting for Bot to be ready before starting daily mute check.")

# Botが起動時にこのコグをロードするために必要なsetup関数
async def setup(bot):
    await bot.add_cog(MassMuteCog(bot))
