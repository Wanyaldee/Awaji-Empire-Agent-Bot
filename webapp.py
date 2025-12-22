import os
import json
import logging
from typing import Optional, Dict, Any, List

import requests
import aiomysql
from quart import Quart, render_template, request, redirect, url_for, session, flash, Response
from quart_cors import cors
from dotenv import load_dotenv

# --- 1. 初期設定と構成 ---

# .env を読み込む
load_dotenv()

class Config:
    """アプリケーション設定を一元管理するクラス"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_insecure_key')
    
    # Discord OAuth2 Settings
    CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
    CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
    REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI')
    TARGET_GUILD_ID = os.getenv('DISCORD_GUILD_ID') # 淡路帝国サーバーID
    
    # Database Settings
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASS', ''),
        'db': os.getenv('DB_NAME', 'bot_db'),
        'charset': 'utf8mb4',
        'autocommit': True
    }

    @classmethod
    def check_required_vars(cls) -> List[str]:
        """必須環境変数が揃っているか確認"""
        missing = []
        if not cls.CLIENT_ID: missing.append("DISCORD_CLIENT_ID")
        if not cls.CLIENT_SECRET: missing.append("DISCORD_CLIENT_SECRET")
        if not cls.REDIRECT_URI: missing.append("DISCORD_REDIRECT_URI")
        return missing

# アプリケーション初期化
app = Quart(__name__, static_folder='static', static_url_path='/static')
app = cors(app, allow_origin="*")
app.secret_key = Config.SECRET_KEY

# グローバルなDBプール
db_pool: Optional[aiomysql.Pool] = None

# --- 2. ライフサイクルイベント (起動・終了時) ---

@app.before_serving
async def startup():
    """サーバー起動時にDB接続プールを作成"""
    global db_pool
    try:
        db_pool = await aiomysql.create_pool(**Config.DB_CONFIG)
        app.logger.info("✅ Database connection pool created.")
        
        # 設定チェック
        missing = Config.check_required_vars()
        if missing:
            app.logger.error(f"❌ Missing environment variables: {', '.join(missing)}")
    except Exception as e:
        app.logger.critical(f"❌ Failed to connect to database: {e}")

@app.after_serving
async def shutdown():
    """サーバー終了時にDB接続をクローズ"""
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        app.logger.info("🛑 Database connection pool closed.")

# --- 3. ヘルパー関数 ---

async def log_operation(user: Dict[str, Any], command: str, detail: str):
    """操作ログをDBに記録する"""
    if not db_pool: return
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO operation_logs (user_id, user_name, command, detail) VALUES (%s, %s, %s, %s)",
                    (str(user['id']), user['name'], command, detail)
                )
    except Exception as e:
        app.logger.error(f"Failed to log operation: {e}")

# --- 4. 認証ルート (Auth) ---

@app.route('/login')
async def login():
    """Discord認証を開始する"""
    if not Config.CLIENT_ID or not Config.REDIRECT_URI:
        return "Server Configuration Error: Missing Client ID or Redirect URI", 500

    # scopeに 'guilds' を含めて、サーバー所属チェックを行えるようにする
    scope = "identify guilds"
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize?client_id={Config.CLIENT_ID}"
        f"&redirect_uri={Config.REDIRECT_URI}&response_type=code&scope={scope}"
    )
    return await render_template('login.html', auth_url=discord_auth_url)

@app.route('/callback')
async def callback():
    """Discordからのコールバックを処理し、入国審査を行う"""
    code = request.args.get('code')
    if not code:
        return "Error: No authentication code provided.", 400

    # 1. Access Token の取得
    token_url = 'https://discord.com/api/oauth2/token'
    payload = {
        'client_id': Config.CLIENT_ID,
        'client_secret': Config.CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': Config.REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        r = requests.post(token_url, data=payload, headers=headers)
        if r.status_code != 200:
            return f"<h3>Authentication Failed</h3><p>Discord Error: {r.text}</p>", 400
        
        token_data = r.json()
        access_token = token_data.get('access_token')
        auth_header = {'Authorization': f'Bearer {access_token}'}

        # 2. 【入国審査】 サーバー所属チェック
        if Config.TARGET_GUILD_ID:
            r_guilds = requests.get('https://discord.com/api/users/@me/guilds', headers=auth_header)
            if r_guilds.status_code == 200:
                user_guilds = r_guilds.json()
                guild_ids = [g['id'] for g in user_guilds]

                # 淡路帝国サーバーIDが含まれていなければ拒否
                if str(Config.TARGET_GUILD_ID) not in guild_ids:
                    # 天狗仕様の Access Denied ページを表示
                    return await render_template('access_denied.html'), 403
            else:
                return "Failed to verify server membership.", 400

        # 3. ユーザー情報の取得
        r_user = requests.get('https://discord.com/api/users/@me', headers=auth_header)
        if r_user.status_code != 200:
            return "Failed to fetch user info.", 400
        
        user_data = r_user.json()

        # 4. セッションに保存
        session['discord_user'] = {
            'id': user_data['id'],
            'name': user_data['username'],
            'avatar_url': f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data['avatar']}.png"
        }
        
        return redirect(url_for('index'))

    except Exception as e:
        app.logger.error(f"Callback Error: {e}")
        return f"Internal Server Error: {str(e)}", 500

@app.route('/logout')
async def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 5. ダッシュボード機能ルート ---

@app.route('/')
async def index():
    user = session.get('discord_user')
    if not user: return redirect(url_for('login'))
    
    if not db_pool: return "DB Error", 500

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 自分のアンケートを取得
            await cur.execute("SELECT * FROM surveys WHERE owner_id = %s ORDER BY created_at DESC", (user['id'],))
            surveys = await cur.fetchall()
            
            # 最近の操作ログを取得
            await cur.execute("SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 30")
            logs = await cur.fetchall()

    return await render_template('dashboard.html', user=user, surveys=surveys, logs=logs)

@app.route('/create_new', methods=['POST'])
async def create_new():
    user = session.get('discord_user')
    if not user: return redirect(url_for('login'))

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            sql = "INSERT INTO surveys (owner_id, title, questions, is_active, created_at) VALUES (%s, '無題のアンケート', '[]', FALSE, NOW())"
            await cur.execute(sql, (user['id'],))
            new_id = cur.lastrowid
            await log_operation(user, "CREATE", f"ID:{new_id} を新規作成")

    return redirect(url_for('edit_survey', survey_id=new_id))

@app.route('/edit/<int:survey_id>')
async def edit_survey(survey_id):
    user = session.get('discord_user')
    if not user: return redirect(url_for('login'))

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM surveys WHERE id=%s", (survey_id,))
            survey = await cur.fetchone()

    # 所有者チェック
    if not survey or str(survey['owner_id']) != str(user['id']):
        return "Forbidden: あなたのアンケートではありません", 403

    try:
        questions = json.loads(survey['questions'])
    except:
        questions = []

    return await render_template('edit.html', user=user, survey=survey, questions=questions)

@app.route('/save_survey', methods=['POST'])
async def save_survey():
    user = session.get('discord_user')
    if not user: return redirect(url_for('login'))

    form = await request.form
    sid = form.get('survey_id')
    title = form.get('title')
    q_json = form.get('questions_json')

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 所有権確認
            await cur.execute("SELECT owner_id FROM surveys WHERE id=%s", (sid,))
            row = await cur.fetchone()
            if not row or str(row[0]) != str(user['id']): return "Forbidden", 403

            await cur.execute("UPDATE surveys SET title=%s, questions=%s WHERE id=%s", (title, q_json, sid))
            await log_operation(user, "UPDATE", f"ID:{sid} を更新")

    await flash("保存しました", "success")
    return redirect(url_for('index'))

@app.route('/toggle_status/<int:survey_id>', methods=['POST'])
async def toggle_status(survey_id):
    user = session.get('discord_user')
    if not user: return redirect(url_for('login'))

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT owner_id, is_active FROM surveys WHERE id=%s", (survey_id,))
            row = await cur.fetchone()
            if row and str(row['owner_id']) == str(user['id']):
                new_status = not row['is_active']
                await cur.execute("UPDATE surveys SET is_active=%s WHERE id=%s", (new_status, survey_id))
                await log_operation(user, "TOGGLE", f"ID:{survey_id} ステータス変更 -> {new_status}")

    return redirect(url_for('index'))

@app.route('/delete_survey/<int:survey_id>', methods=['POST'])
async def delete_survey(survey_id):
    user = session.get('discord_user')
    if not user: return redirect(url_for('login'))

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT owner_id FROM surveys WHERE id=%s", (survey_id,))
            row = await cur.fetchone()
            if row and str(row['owner_id']) == str(user['id']):
                await cur.execute("DELETE FROM surveys WHERE id=%s", (survey_id,))
                await log_operation(user, "DELETE", f"ID:{survey_id} を削除")
                await flash("削除しました", "warning")

    return redirect(url_for('index'))

# --- メイン実行ブロック ---
if __name__ == '__main__':
    # ローカルでの開発/デバッグ実行用
    app.run(host='0.0.0.0', port=5000)
