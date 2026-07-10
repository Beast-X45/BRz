import discord
import os
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# =======================================================
# 🌐 Render用のダミーWebサーバー設定
# =======================================================
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    # ログが画面に大量に出るのを防ぐ（非表示にする）ための設定
    def log_message(self, format, *args):
        return

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Botが動く前に、バックグラウンドでWebサーバーを起動
threading.Thread(target=run_dummy_server, daemon=True).start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)

user_msg_times = {}

@client.event
async def on_ready():
    print("【ログインしました】")
    print(f"Bot名: {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # -------------------------------------------------------
    # 👑 手動タイムアウトコマンド（!to 分 @ユーザー）
    # -------------------------------------------------------
    if message.content.startswith("!to "):
        # 実行したユーザーが「管理者」という名前のロールを持っているかチェック
        # (大文字・小文字も区別されるので、実際のロール名に合わせてください)
        has_admin_role = any(role.name == "管理者" for role in message.author.roles)
        
        # 💡 もし「サーバーの管理権限」を持つ人全員に使わせたい場合は、上記の代わりに以下を使います：
        # has_admin_role = message.author.guild_permissions.administrator

        if not has_admin_role:
            await message.channel.send("❌ このコマンドは管理権限を持つユーザーのみ使用できます。")
            return

        # コマンドの文字をバラバラに分解する (例: ['!to', '25', '<@ユーザーID>'])
        args = message.content.split()
        
        # 引数の数が足りない、またはメンションがない場合
        if len(args) < 3 or not message.mentions:
            await message.channel.send("❌ 形式が正しくありません。")
            return

        try:
            # 2番目の文字（分）を数字に変換
            minutes = int(args[1])
            # メンションされた最初のユーザーを取得
            target_user = message.mentions[0]
            
            # タイムアウト時間を設定
            duration = timedelta(minutes=minutes)
            await target_user.timeout(duration, reason=f"{message.author.name} によるコマンド実行")
            
            await message.channel.send(f"⏳ {target_user.mention} さんを {minutes} 分間タイムアウトしました。")
            return # コマンド処理が終わったらここで終了（自動返信などは動かさない）

        except ValueError:
            await message.channel.send("❌ 時間の指定は半角の数字で入力してください。")
            return
        except discord.Forbidden:
            await message.channel.send("❌ 権限が足りないため、そのユーザーをタイムアウトできません。Botのロール順位を確認してください。")
            return
        except Exception as e:
            await message.channel.send(f"❌ エラーが発生しました: {e}")
            return
        
    # -------------------------------------------------------
    # 🛑 スパム対策（5秒以内に3回発言で1分タイムアウト）
    # -------------------------------------------------------
    user_id = message.author.id
    now = datetime.now()

    # 初めて発言したユーザーならリストを作る
    if user_id not in user_msg_times:
        user_msg_times[user_id] = []

    # 今回の発言時間を記録
    user_msg_times[user_id].append(now)

    # 5秒以上前の古い記録は削除して整理する
    user_msg_times[user_id] = [t for t in user_msg_times[user_id] if now - t < timedelta(seconds=5)]

    # 5秒以内の発言が3回以上になった場合
    if len(user_msg_times[user_id]) >= 4:
        try:
            # 1分間のタイムアウト時間を設定
            duration = timedelta(minutes=1)
            await message.author.timeout(duration, reason="5秒間に4回以上の連投（スパム対策）")
            
            # 警告メッセージをチャンネルに送信
            await message.channel.send(f"⚠️ {message.author.mention} を連投のため1分間タイムアウトしました。")
            
            # 記録をリセット
            user_msg_times[user_id] = []
            return # タイムアウトさせたので、下の自動返信処理はスキップする
            
        except discord.Forbidden:
            # Botより権限が高い人（サーバーオーナーなど）にはタイムアウトが効かないためエラーを回避
            print(f"権限不足のため、{message.author.name} をタイムアウトできませんでした。")
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            
            
    if message.content.startswith("!m "):
        args = message.content.split()
        
        # 数字が入力されていない場合
        if len(args) < 2:
            await message.channel.send("❌ 計算する数字をスペース区切りで入力してください。例: `!m 10 20 33`")
            return

        try:
            # 入力された文字をすべて数字（浮動小数点数 float）に変換
            # 💡 整数だけにする場合は int にしますが、floatにしておくと小数の計算もできるようになります
            numbers = [float(n) for n in args[1:]]
            
            # 前から順番に計算する
            # 最初の数を初期値にする
            total_sum = numbers[0]
            total_sub = numbers[0]
            total_mul = numbers[0]

            # 2番目以降の数字を順番にループ処理
            for num in numbers[1:]:
                total_sum += num  # 和
                total_sub -= num  # 差
                total_mul *= num  # 積

            # 結果をきれいに表示するためのフォーマットを作成
            # float型の結果が「.0」で終わる場合は整数表記にする工夫
            def format_num(val):
                return int(val) if val.is_integer() else val

            result_text = f"和：{format_num(total_sum)}\n差：{format_num(total_sub)}\n積：{format_num(total_mul)}"

            # 数字がちょうど2つの場合のみ、商（割り算）も追加
            if len(numbers) == 2:
                if numbers[1] == 0:
                    result_text += "\n商：0で割ることはできません"
                else:
                    total_div = numbers[0] / numbers[1]
                    result_text += f"\n商：{format_num(total_div)}"

            # コードブロック（```）で囲って送信
            await message.channel.send(f"```\n{result_text}\n```")
            return

        except ValueError:
            await message.channel.send("❌ 数字は半角で入力してください。")
            return
        except Exception as e:
            await message.channel.send(f"❌ エラーが発生しました: {e}")
            return
        
        
    if message.content.startswith("!unix "):
        args = message.content.split()
        
        # 年〜秒までで6つの数字が必要（!unix を含めると引数は合計7つ必要）
        if len(args) < 7:
            await message.channel.send("❌ 形式が正しくありません。使用例: `!unix 2026 01 01 15 00 00`")
            return

        try:
            # 入力された文字をそれぞれ整数に変換
            year = int(args[1])
            month = int(args[2])
            day = int(args[3])
            hour = int(args[4])
            minute = int(args[5])
            second = int(args[6])

            # datetimeオブジェクトを作成（日本の時間として扱う）
            dt = datetime(year, month, day, hour, minute, second, tzinfo=jst)
            
            # UNIX時間に変換（整数にするために int() で囲む）
            unix_time = int(dt.timestamp())

            # Discordの装飾フォーマットを作成
            # 例: <t:1767247200> - <t:1767247200:R>
            response_format = f"<t:{unix_time}> - <t:{unix_time}:R>"
            
            # さらに、コピペしたい時のために、あえてコードブロックでも文字列を添えてあげると親切です
            reply_msg = f"{response_format}\n\nコピペ用：\n`{response_format}`"

            await message.channel.send(reply_msg)
            return

        except ValueError:
            await message.channel.send("❌ 正しい日時を半角数字で入力してください。（例: 月に13などを入れるとエラーになります）")
            return
        except Exception as e:
            await message.channel.send(f"❌ エラーが発生しました: {e}")
            return
        
    end_reply_patterns = [
        (["ぼ"], "るきち"),
        (["る",], "きち"),
        (["き"], "ち"),
        # 💡 ここに同じように追加していけます（必ず1文字を指定してください）
    ]
    # -------------------------------------------------------

    # メッセージが空でなければ、最後の1文字をチェック
    if message.content:
        last_char = message.content[-1] # メッセージの最後の1文字を取得
        for chars, reply_message in end_reply_patterns:
            if last_char in chars:
                await message.channel.send(reply_message)
                return # マッチしたらここで処理終了（下の全体一致は動かさない）

    # =======================================================
    # ーーー ここを書き換える（返信パターン辞書） ーーー
    # 書き方： ([ "反応させたいワード1", "ワード2" ], "Botの返信メッセージ")
    # =======================================================
    reply_patterns = [
        (["うお", "どわー", "きちー", "けけっ","必死","冗談ですやん"], "うおw"),
        (["ぼる", "ちきん"], "ぼるきちいぃぃ"),
        (["ちくまる様", "chikumaru様"], "chikumaru様🙏\nアーメン"),
        (["Carbuncle様","カーバンクル様"], "Carbuncle様🙏\nアーメン"),
        (["にょ"],"にょ、にょ、にょまれ〜い🐮🖐️"),
        (["まかう","んー","ん〜"],"んん〜まかｧｧウｯｯ!!!!🤏😎"),
        # 💡 さらにパターンを増やしたい場合は、この下にカンマ（,）区切りで同じように追加していけます
    ]
    # =======================================================

    # 受信したメッセージにキーワードが含まれているか上から順番にチェック
    for keywords, reply_message in reply_patterns:
        if any(keyword in message.content for keyword in keywords):
            await message.channel.send(reply_message)
            break # 1つマッチしたらその時点で処理を終了（重複送信防止）

# Renderの環境変数からTokenを読み込んで起動
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
client.run(TOKEN)
