import discord
from discord.ext import commands
import asyncio
# 🚨 修正点: configから DISCORD_BOT_TOKEN のインポートを削除 🚨
from config import ADMIN_USER_ID

# コグ（拡張機能）のリスト
COGS = [
    "cogs.filter",
    "cogs.mass_mute"
]

# Botのインスタンスを作成
intents = discord.Intents.default()
intents.members = True 
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)

async def load_cogs():
    """定義されたコグをロードする"""
    for cog_name in COGS:
        try:
            await bot.load_extension(cog_name)
            print(f"LOADED: {cog_name} をロードしました。")
        except Exception as e:
            print(f"ERROR: {cog_name} のロードに失敗しました。")
            print(f"Traceback: {e}")

@bot.event
async def on_ready():
    """BotがDiscordに接続を完了したときに実行される"""
    print('-------------------------------------')
    print('Bot Name: {0.user.name}'.format(bot))
    print('Bot ID: {0.user.id}'.format(bot))
    print('-------------------------------------')
    
    # 起動完了DMを管理者へ送信
    owner = None
    try:
        owner_id_int = int(ADMIN_USER_ID)
        owner = await bot.fetch_user(owner_id_int) 
    except ValueError:
        print(f"Error: ADMIN_USER_ID '{ADMIN_USER_ID}' is not a valid integer string.")
    except discord.NotFound:
        print(f"Error: Owner user with ID {ADMIN_USER_ID} not found.")
    except Exception as e:
        print(f"Error fetching owner user in on_ready: {e}")

    if owner:
        try:
            embed = discord.Embed(
                title="Bot起動完了",
                description=f"Bot **{bot.user.name}** が正常に起動しました。",
                color=0x4caf50 
            )
            await owner.send(embed=embed)
            print("Startup DM sent to owner.")
        except Exception as e:
            print(f"Failed to send startup DM to owner: {e}")
    else:
        print("Warning: Owner user not found or ID is invalid. Could not send startup DM.")
    
    await load_cogs()

def get_token_from_file(filename="token.txt"):
    """token.txtファイルからトークンを読み込む"""
    try:
        with open(filename, 'r') as f:
            # ファイルの最初の行から空白を除去してトークンを取得
            token = f.read().strip()
            return token
    except FileNotFoundError:
        print(f"Error: Token file '{filename}' not found.")
        return None
    except Exception as e:
        print(f"Error reading token file: {e}")
        return None

if __name__ == '__main__':
    bot_token = get_token_from_file()
    
    if bot_token:
        try:
            # bot.runはブロッキング関数
            bot.run(bot_token)
        except discord.LoginFailure:
            print("Error: Invalid token in token.txt")
        except Exception as e:
            print(f"An unexpected error occurred during bot execution: {e}")
    else:
        print("Bot execution aborted due to missing or invalid token.")
