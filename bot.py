import discord
from discord.ext import commands
import asyncio
from config import ADMIN_USER_ID

# コグ（拡張機能）のリスト
COGS = [
    "cogs.filter",
    "cogs.mass_mute"
]

class MyBot(commands.Bot):
    def __init__(self):
        # インテンツの設定
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True 
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        """
        Bot起動時に一度だけ実行される初期化処理。
        コグのロードをここで行うことで、再接続時の二重ロードエラーを防止します。
        """
        for cog_name in COGS:
            try:
                await self.load_extension(cog_name)
                print(f"LOADED: {cog_name} をロードしました。")
            except Exception as e:
                print(f"ERROR: {cog_name} のロードに失敗しました。")
                print(f"Traceback: {e}")

# Botインスタンスの作成
bot = MyBot()

def get_token_from_file(filename="token.txt"):
    """token.txtファイルからトークンを読み込む"""
    try:
        with open(filename, 'r') as f:
            token = f.read().strip()
            return token
    except FileNotFoundError:
        print(f"Error: Token file '{filename}' not found.")
        return None
    except Exception as e:
        print(f"Error reading token file: {e}")
        return None

@bot.event
async def on_ready():
    """
    BotがDiscordに接続・再接続したときに実行される。
    ※コグのロード処理は setup_hook に移動したため、ここからは削除されています。
    """
    print('-------------------------------------')
    print('Bot Name: {0.user.name}'.format(bot))
    print('Bot ID: {0.user.id}'.format(bot))
    print('-------------------------------------')
    
    # --- 1. 起動/再接続DMを管理者へ送信 ---
    owner = None
    try:
        owner_id_int = int(ADMIN_USER_ID)
        owner = await bot.fetch_user(owner_id_int) 
    except Exception as e:
        print(f"Error fetching owner user: {e}")

    if owner:
        try:
            status = "再起動/再接続" if bot.is_ready() else "起動完了"
            embed = discord.Embed(
                title=f"Bot {status}",
                description=f"Bot **{bot.user.name}** がオンラインになりました。",
                color=0x4caf50 
            )
            await owner.send(embed=embed)
        except Exception as e:
            print(f"Failed to send status DM to owner: {e}")
    
    # --- 2. mass_mute の実行 (接続のたびに最新の状態に保つため) ---
    if 'cogs.mass_mute' in bot.extensions:
        mass_mute_cog = bot.get_cog("MassMuteCog")
        if mass_mute_cog:
            # 非同期で実行
            asyncio.create_task(mass_mute_cog.execute_mute_logic("Startup/Reconnected"))


if __name__ == '__main__':
    bot_token = get_token_from_file()
    
    if bot_token:
        try:
            bot.run(bot_token)
        except discord.LoginFailure:
            print("Error: Invalid token in token.txt")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    else:
        print("Bot execution aborted due to missing or invalid token.")
