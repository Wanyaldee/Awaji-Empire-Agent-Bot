import discord
from discord.ext import commands, tasks
import asyncio
import datetime
from config import ADMIN_USER_ID, MUTE_CHANNEL_NAMES
from typing import List

# ----------------------------------------------------
# 権限オブジェクトの定義
# チャンネルの閲覧とメッセージ送信は許可しつつ、通知を徹底的に抑制する設定
# ----------------------------------------------------
MUTE_OVERWRITE = discord.PermissionOverwrite(
    read_messages=True,
    send_messages=True,
    # メンションやウェブフックなど、通知をトリガーする権限を明示的にFalseに設定
    mention_everyone=False,
    manage_webhooks=False,
    # 通知を受け取らない設定を強制するには、この程度で十分
)

class MassMuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_id = ADMIN_USER_ID
        self.target_channel_names: List[str] = MUTE_CHANNEL_NAMES

        self.daily_mute_check.add_exception_type(asyncio.CancelledError)
        self.daily_mute_check.start()

    def cog_unload(self):
        self.daily_mute_check.cancel()

    # ----------------------------------------------------
    # ヘルパー関数群 (DMログ、エラー通知)
    # ----------------------------------------------------
    async def _send_dm_log(self, message: str, is_error: bool = False):
        """DMログを送信する内部ヘルパー"""
        owner = None
        try:
            # オーナーユーザーをDiscord APIから確実に取得
            owner = await self.bot.fetch_user(self.owner_id)
        except Exception as e:
            # ユーザー取得失敗
            print(f"[DM FATAL] Could not fetch owner ID {self.owner_id}: {e}")
            return

        if owner:
            try:
                await owner.send(message)
                if not is_error:
                    print(f"[DM DEBUG] Log sent successfully.")
            except discord.Forbidden:
                print(f"[DM ERROR] Failed to send DM (Forbidden). User {owner.name} may block DMs.")
            except Exception as e:
                print(f"[DM ERROR] Failed to send DM log to owner: {e}")
        else:
            print(f"[DM WARNING] Cannot send DM. Owner object is None (ID: {self.owner_id}).")

    async def _send_error_dm(self, title: str, description: str):
        """エラー発生時に管理者DMに通知するヘルパー"""
        error_message = f"🚨 **【ミュート機能エラー】{title}** 🚨\n{description}"
        await self._send_dm_log(error_message, is_error=True)

    # ----------------------------------------------------
    # 1. コア機能: チャンネル通知の制御ロジック
    # ----------------------------------------------------
    async def execute_mute_logic(self, trigger: str):
        """
        対象チャンネルの通知権限を操作し、DMでログを送信する共通ロジック。
        """

        if not self.bot.guilds:
            await self._send_error_dm("サーバー未接続", "Botが接続しているサーバーが見つかりませんでした。")
            return

        guild = self.bot.guilds[0]
        everyone_role = guild.default_role

        # 🚨 要件: 常に通知オフの権限を適用する
        overwrite_to_apply = MUTE_OVERWRITE
        action_desc = "通知オフ (常時抑制)"

        channels_updated = 0
        error_messages = []

        for channel_name in self.target_channel_names:
            # チャンネル名の検索
            channel = discord.utils.get(guild.text_channels, name=channel_name)

            if channel:
                try:
                    # チャンネルの @everyone ロールの権限を上書き
                    await channel.set_permissions(everyone_role, overwrite=overwrite_to_apply)
                    channels_updated += 1
                except discord.Forbidden:
                    # Botに権限がない場合のエラー処理
                    msg = f"チャンネル #{channel_name} の権限設定に失敗しました。Botに『権限の管理』または『ロールの管理』権限がありません。"
                    print(f"[MUTE ERROR] {msg}")
                    error_messages.append(msg)
                except Exception as e:
                    # その他の予期せぬエラー
                    msg = f"チャンネル #{channel_name} の権限設定中に予期せぬエラーが発生: {e}"
                    print(f"[MUTE ERROR] {msg}")
                    error_messages.append(msg)
            else:
                # チャンネルが見つからない場合
                msg = f"チャンネル '{channel_name}' がサーバーに見つかりませんでした。"
                print(f"[MUTE WARNING] {msg}")
                error_messages.append(msg)

        # ログメッセージの作成
        if error_messages:
            status_summary = "\n- ".join(error_messages)
            log_message = f"⚠️ **通知制御エラーが発生しました** ⚠️\n> サーバー: **{guild.name}**\n> 成功: {channels_updated}/{len(self.target_channel_names)} チャンネル\n> エラー詳細:\n- {status_summary}\n> トリガー: **{trigger}**"
            await self._send_dm_log(log_message, is_error=True)
        else:
            log_message = f"✅ 通知制御を実行しました ({action_desc})。\n> サーバー: **{guild.name}**\n> 対象チャンネル: {channels_updated}/{len(self.target_channel_names)} チャンネル\n> トリガー: **{trigger}**"
            await self._send_dm_log(log_message)


    # ----------------------------------------------------
    # 2. 起動時イベント
    # ----------------------------------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot is ready. Executing initial mute check (Startup)...")
        await self.execute_mute_logic("Startup")

    # ----------------------------------------------------
    # 3. 固定時刻タスク
    # ----------------------------------------------------
    @tasks.loop(time=[
        datetime.time(0, 0, tzinfo=datetime.timezone.utc),   # JST 9:00
        datetime.time(8, 0, tzinfo=datetime.timezone.utc),   # JST 17:00
        datetime.time(16, 0, tzinfo=datetime.timezone.utc)  # JST 翌 1:00
    ])
    async def daily_mute_check(self):
        print("Daily mute check triggered by fixed time.")
        await self.execute_mute_logic("Daily Task")

    @daily_mute_check.before_loop
    async def before_daily_mute_check(self):
        await self.bot.wait_until_ready()
        print("Waiting for Bot to be ready before starting daily mute check.")


async def setup(bot):
    await bot.add_cog(MassMuteCog(bot))
