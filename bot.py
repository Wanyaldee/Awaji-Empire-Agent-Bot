# /discord_bot/bot.py

import discord
from discord.ext import commands
import traceback
import sys
import os

# config.pyから設定をインポート
from config import ADMIN_USER_ID

# ----------------------------------------------------
# DM送信関数: メインファイルに集約
# ----------------------------------------------------
async def send_admin_dm(bot, title, description, color):
    """管理者ユーザーにDMでログを送信する関数"""
    try:
        # fetch_userでユーザーオブジェクトを取得
        admin_user = await bot.fetch_user(ADMIN_USER_ID)
        if admin_user:
            embed = discord.Embed(title=title, description=description, color=color)
            await admin_user.send(embed=embed)
    except Exception as e:
        # DM送信自体が失敗した場合、コンソールにエラー出力
        print(f"DM送信中にエラーが発生しました: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

# ----------------------------------------------------
# Botの設定と起動
# ----------------------------------------------------

class AwajiEmpireAgentBot(commands.Bot):
    def __init__(self):
        # 必要なインテントを設定 (on_message, on_member_join, on_guild_channel_createなどに必須)
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )

    async def on_ready(self):
        print('-------------------------------------')
        print(f'Bot Name: {self.user.name}')
        print(f'Bot ID:   {self.user.id}')
        print('-------------------------------------')

        # コグのロード
        await self.load_cogs()

        # 管理者DMに起動を通知
        await send_admin_dm(
            self,
            title="Bot 起動完了",
            description=f"Bot **{self.user.name}** が正常に起動しました。",
            color=discord.Color.blue()
        )

    async def load_cogs(self):
        cogs_dir = 'cogs'
        for filename in os.listdir(cogs_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                cog_name = f'{cogs_dir}.{filename[:-3]}'
                try:
                    await self.load_extension(cog_name)
                    print(f'LOADED: {cog_name} をロードしました。')
                except Exception as e:
                    print(f'ERROR: {cog_name} のロードに失敗しました。', file=sys.stderr)
                    print(f'{e}', file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)

# メイン実行ブロック
if __name__ == "__main__":
    try:
        # トークンの読み込み
        with open('token.txt', 'r') as f:
            TOKEN = f.read().strip()

        bot = AwajiEmpireAgentBot()
        bot.run(TOKEN)
    except FileNotFoundError:
        print("[FATAL ERROR] 'token.txt' が見つかりません。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL ERROR] Botの実行中に予期せぬエラーが発生しました: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
