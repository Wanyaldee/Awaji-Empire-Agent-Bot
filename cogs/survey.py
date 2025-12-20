import discord
from discord import app_commands
from discord.ext import commands
import aiomysql
import os
import json
from dotenv import load_dotenv

load_dotenv()

# --- データベース接続設定 ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASS', ''),
    'db': os.getenv('DB_NAME', 'bot_db'),
    'charset': 'utf8mb4',
    'autocommit': True
}

# --- 1. 回答用ウィザード (対話形式で回答を進めるView) ---
class SurveyWizardView(discord.ui.View):
    def __init__(self, bot, interaction, survey_data, questions):
        super().__init__(timeout=300) # 5分でタイムアウト
        self.bot = bot
        self.origin_interaction = interaction
        self.survey_id = survey_data['id']
        self.survey_title = survey_data['title']
        self.questions = questions
        self.current_index = 0
        self.answers = {} # { "質問文": "回答" } の形で保存

    async def start(self):
        """最初の質問を表示する"""
        await self.send_question()

    async def send_question(self):
        """現在の質問をEmbedとコンポーネントで表示"""
        if self.current_index >= len(self.questions):
            await self.finish_survey()
            return

        q = self.questions[self.current_index]
        
        # 質問データの正規化
        if isinstance(q, str): # 古いデータ対策
            q_data = {'type': 'text', 'question': q}
        else:
            q_data = q

        q_text = q_data.get('question', '質問なし')
        q_type = q_data.get('type', 'text')
        options = q_data.get('options', [])

        # Embed作成
        embed = discord.Embed(
            title=f"📝 Q{self.current_index + 1}: {q_text}",
            description="下の入力欄・選択肢から回答してください。",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"{self.current_index + 1} / {len(self.questions)} 問目")

        # UIコンポーネントの準備 (毎回作り直す)
        self.clear_items()

        # タイプに応じた入力部品
        if q_type == 'text':
            # 記述式: ボタンを押すとModalが出るようにする
            btn = discord.ui.Button(label="✍️ 回答を入力する", style=discord.ButtonStyle.primary)
            
            async def text_callback(interaction: discord.Interaction):
                modal = AnswerModal(self, q_text)
                await interaction.response.send_modal(modal)
            
            btn.callback = text_callback
            self.add_item(btn)

        elif q_type in ['radio', 'checkbox']:
            # 選択式: Select Menuを表示
            # Discordの制限: 最大25個まで
            select_options = [discord.SelectOption(label=opt[:100]) for opt in options[:25]]
            
            select = discord.ui.Select(
                placeholder="選択してください...",
                min_values=1,
                max_values=1 if q_type == 'radio' else len(select_options),
                options=select_options
            )

            async def select_callback(interaction: discord.Interaction):
                # 回答を保存
                selected = ", ".join(select.values)
                self.answers[q_text] = selected
                
                # 次へ
                self.current_index += 1
                await interaction.response.defer() # 読み込み中...にする
                await self.send_question()

            select.callback = select_callback
            self.add_item(select)

        # 画面更新
        if self.origin_interaction.response.is_done():
            await self.origin_interaction.edit_original_response(embed=embed, view=self)
        else:
            await self.origin_interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def finish_survey(self):
        """全問終了時の処理"""
        # DBに保存
        try:
            pool = await aiomysql.create_pool(**DB_CONFIG)
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO survey_responses 
                        (survey_id, user_id, user_name, answers, answered_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """
                    # 回答をJSONにして保存
                    await cursor.execute(sql, (
                        self.survey_id, 
                        str(self.origin_interaction.user.id),
                        self.origin_interaction.user.display_name,
                        json.dumps(self.answers, ensure_ascii=False)
                    ))
            pool.close()
            await pool.wait_closed()
            
            embed = discord.Embed(
                title="✅ 回答ありがとうございました！",
                description=f"アンケート「{self.survey_title}」への回答を送信しました。",
                color=discord.Color.green()
            )
            await self.origin_interaction.edit_original_response(embed=embed, view=None)

        except Exception as e:
            await self.origin_interaction.edit_original_response(content=f"❌ 保存エラーが発生しました: {e}", view=None)


# --- 2. 記述式回答用のモーダル ---
class AnswerModal(discord.ui.Modal):
    def __init__(self, wizard_view, question_text):
        super().__init__(title="回答入力")
        self.wizard_view = wizard_view
        self.question_text = question_text
        
        self.answer_input = discord.ui.TextInput(
            label=question_text[:45], 
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        # 回答を保存
        self.wizard_view.answers[self.question_text] = self.answer_input.value
        
        # 次へ進む
        self.wizard_view.current_index += 1
        await interaction.response.defer() # モーダルを閉じる処理
        await self.wizard_view.send_question()


# --- 3. メインのCog ---
class Survey(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_db_connection(self):
        return await aiomysql.connect(**DB_CONFIG)

    # リスナー: ボタンが押されたとき (custom_id='answer_survey_数字') を検知
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get('custom_id', '')
        
        # 「回答する」ボタンかチェック
        if custom_id.startswith("answer_survey_"):
            try:
                survey_id = int(custom_id.split('_')[-1])
                await self.start_answering(interaction, survey_id)
            except ValueError:
                pass

    async def start_answering(self, interaction: discord.Interaction, survey_id: int):
        """回答ウィザードを開始する"""
        # DBからアンケート情報を取得
        survey = None
        try:
            conn = await self.get_db_connection()
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT * FROM surveys WHERE id = %s", (survey_id,))
                survey = await cursor.fetchone()
            conn.close()
        except Exception as e:
            await interaction.response.send_message(f"❌ DBエラー: {e}", ephemeral=True)
            return

        if not survey:
            await interaction.response.send_message("❌ アンケートが見つかりません。", ephemeral=True)
            return

        if not survey['is_active']:
            await interaction.response.send_message("⛔ 現在このアンケートは回答を受け付けていません。", ephemeral=True)
            return

        # 質問データをパース
        try:
            questions = json.loads(survey['questions'])
        except:
            questions = []

        if not questions:
            await interaction.response.send_message("質問データが空です。", ephemeral=True)
            return

        # ウィザードを開始 (自分だけに表示 = ephemeral=True)
        # 最初のレスポンスとして「読み込み中」を出す
        await interaction.response.send_message("🚀 アンケートを開始します...", ephemeral=True)
        
        # Viewを作成して開始
        view = SurveyWizardView(self.bot, interaction, survey, questions)
        await view.start()

    # --- 既存のコマンド類 ---

    @app_commands.command(name="create_survey", description="アンケート作成用のWebダッシュボードを開きます")
    async def create_survey(self, interaction: discord.Interaction):
        # ★重要: ここをあなたのドメインに変更！
        dashboard_url = "https://agent.awajiempire.net" 
        
        embed = discord.Embed(
            title="🛠️ アンケート作成",
            description=f"以下のリンクからWebダッシュボードにアクセスして作成してください。\n\n[>> ダッシュボードを開く]({dashboard_url})",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="deploy", description="Webで作成したアンケートをここに表示・開始します")
    @app_commands.describe(survey_id="Web画面で確認したアンケートIDを入力")
    async def deploy(self, interaction: discord.Interaction, survey_id: int):
        # 1. DBからデータを取得
        survey = None
        try:
            conn = await self.get_db_connection()
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT * FROM surveys WHERE id = %s", (survey_id,))
                survey = await cursor.fetchone()
            conn.close()
        except Exception as e:
            await interaction.response.send_message(f"❌ DBエラー: {e}", ephemeral=True)
            return

        if not survey:
            await interaction.response.send_message(f"❌ ID: {survey_id} のアンケートが見つかりません。", ephemeral=True)
            return
        
        # 権限チェック
        if str(survey['owner_id']) != str(interaction.user.id):
            await interaction.response.send_message("🚫 あなたが作成したアンケートではありません。", ephemeral=True)
            return

        # 2. JSONパース
        try:
            questions = json.loads(survey['questions'])
        except:
            await interaction.response.send_message("❌ データ形式エラー", ephemeral=True)
            return

        # 3. Embedの作成
        embed = discord.Embed(
            title=f"📋 {survey['title']}",
            description="**下の「回答する」ボタンを押して回答を開始してください。**\n(他の人には見えないフォームが開きます)",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"ID: {survey_id} | 作成者: {interaction.user.display_name}")

        # 質問の概要を表示
        q_summary = ""
        for i, q in enumerate(questions, 1):
            if isinstance(q, str):
                q_text = q
            else:
                q_text = q.get('question', '質問')
            q_summary += f"Q{i}. {q_text}\n"
        
        if q_summary:
            embed.add_field(name="質問内容", value=q_summary[:1000], inline=False)

        # 4. 回答ボタン
        view = discord.ui.View()
        start_btn = discord.ui.Button(
            label="回答する", 
            style=discord.ButtonStyle.success, 
            emoji="📝",
            custom_id=f"answer_survey_{survey_id}" # これをリスナーで拾います
        )
        view.add_item(start_btn)

        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync(self, ctx):
        await self.bot.tree.sync()
        self.bot.tree.clear_commands(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)
        await ctx.send("✅ 同期完了！\n・グローバルコマンドを更新しました。\n・このサーバーに残っていた古い重複コマンドを削除しました。")

async def setup(bot):
    await bot.add_cog(Survey(bot))
