import os
import re
import datetime

# --- 設定 ---
# ドキュメントを自動生成する対象のコグファイル
TARGET_COGS = ["cogs/filter.py", "cogs/mass_mute.py"]
# ARCHITECTURE.mdのパス
ARCH_PATH = "docs/ARCHITECTURE.md"

# 自動生成セクションの開始と終了を識別するためのマーカー
START_MARKER = ""
END_MARKER = ""
# -----------------

def extract_cog_details(file_path):
    """
    指定されたコグファイルから、クラス名と主要メソッド名を抽出する。
    """
    details = []
    
    # ファイルの存在確認 (GitHub Actions環境でのエラー回避のため)
    if not os.path.exists(file_path):
        details.append(f"ファイルが見つかりません: {file_path}")
        return details

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # クラス名 (コグ名) を抽出
    cog_name_match = re.search(r'class\s+(\w+)\s*\(commands\.Cog\):', content)
    if not cog_name_match:
        return details

    cog_name = cog_name_match.group(1)
    # 日本語で機能見出しを生成
    details.append(f"### ⚙️ {cog_name} コグ機能 (`{os.path.basename(file_path)}`)")

    # メソッド名 (主なリスナーやコマンド) を抽出
    method_matches = re.findall(r'(?:async\s+)?def\s+(on_\w+|[^(\s]+_check)\s*\(', content)

    unique_methods = sorted(list(set(method_matches)))

    if unique_methods:
        details.append("\n#### 実行メソッド/タスク:")
        for method in unique_methods:
            # tasks.loopで定義されているタスクを識別
            if "_check" in method or "daily" in method:
                details.append(f"* **タスク**: `{method}` (定時実行)")
            else:
                details.append(f"* **イベント**: `{method}` (Discordイベントフック)")
    
    return details

def update_architecture_markdown(new_content_list):
    """
    ARCHITECTURE.mdの特定のセクションを新しい内容で置換する。
    """

    try:
        with open(ARCH_PATH, 'r', encoding='utf-8') as f:
            full_content = f.read()
    except FileNotFoundError:
        print(f"エラー: {ARCH_PATH} が見つかりません。")
        return

    start_index = full_content.find(START_MARKER)
    end_index = full_content.find(END_MARKER)

    if start_index == -1 or end_index == -1:
        print(f"エラー: ARCHITECTURE.md内に自動生成マーカーが見つかりません。")
        return

    new_section_content = "\n" + "\n".join(new_content_list) + "\n"

    updated_content = (
        full_content[:start_index + len(START_MARKER)] +
        new_section_content +
        full_content[end_index:]
    )

    with open(ARCH_PATH, 'w', encoding='utf-8') as f:
        f.write(updated_content)

    print(f"✅ {ARCH_PATH} の自動生成セクションを更新しました。")


if __name__ == "__main__":
    generated_details = []

    # 実行日時を追記
    now = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M JST")
    generated_details.append(f"**⏰ 最終自動更新日時: {now}**")
    generated_details.append("\n---")
    
    # 各コグの詳細を抽出
    for cog_file in TARGET_COGS:
        generated_details.extend(extract_cog_details(cog_file))

    update_architecture_markdown(generated_details)
