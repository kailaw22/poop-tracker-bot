from flask import Flask, request, abort
from dotenv import load_dotenv
load_dotenv()

import os
import json
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage
from datetime import datetime, timedelta
from collections import Counter
import pytz

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CREDENTIAL_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
info = json.loads(CREDENTIAL_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
client = gspread.authorize(creds)
sheet = client.open("大便紀錄").sheet1

try:
    sheet_ids = client.open("大便紀錄").worksheet("推播名單")
except:
    sheet_ids = client.open("大便紀錄").add_worksheet(title="推播名單", rows="1000", cols="2")

def get_source_id(event):
    if event.source.type == "group":
        return event.source.group_id
    elif event.source.type == "room":
        return event.source.room_id
    else:
        return event.source.user_id

@app.route("/", methods=['GET'])
def home():
    return "💩 大便紀錄 Bot 運作中！"

@app.route("/keepalive", methods=["GET"])
def keepalive():
    return "✅ I'm alive!"
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/remind_morning", methods=["GET"])
def remind_morning():
    return send_reminder("早安！記得排便哦～")

@app.route("/remind_night", methods=["GET"])
def remind_night():
    return send_reminder("晚安前也別忘了便便唷！")

def send_reminder(message):
    try:
        rows = sheet_ids.get_all_values()[1:]
        for r in rows:
            to_id, t_type = r
            try:
                if t_type == "user":
                    line_bot_api.push_message(to_id, TextSendMessage(text=message))
                elif t_type == "group":
                    line_bot_api.push_message(to_id, TextSendMessage(text="群組提醒：" + message))
            except Exception as e:
                print(f"推播錯誤 {to_id}: {e}")
        return "✅ 推播完成"
    except Exception as e:
        return f"❌ 推播失敗：{e}"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    user_id = event.source.user_id
    source_type = event.source.type
    source_id = get_source_id(event)

    tz = pytz.timezone('Asia/Taipei')
    now_dt = datetime.now(tz)
    now = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    today = now_dt.strftime("%Y-%m-%d")

    try:
        profile = line_bot_api.get_profile(user_id)
        user_name = profile.display_name
    except:
        user_name = "未知使用者"
        
    ids = sheet_ids.col_values(1)
    if source_id not in ids:
        sheet_ids.append_row([source_id, source_type])

    reply = ""

    private_cmds = ["查詢", "查詢本週", "查詢本月"]
    group_cmds = ["大便", "💩", "排行榜", "週排行", "周排行", "月排行", "兜不住屎", "幫助", "help", "使用說明"]
    all_cmds = private_cmds + group_cmds + ["屎王", "便便抽卡"]

    if source_type in ["group", "room"] and msg not in all_cmds:
        return

    if msg in ["大便", "💩"]:
        try:
            sheet.append_row([user_name, now, msg, source_type, source_id])
            reply = "✅ 已紀錄你的大便！記得多喝水 💧"
        except Exception as e:
            reply = f"⚠️ 寫入失敗：{str(e)}"

    elif msg == "便便抽卡":
        cards = [
            ("N", "平凡的一泡，默默無名。"),
            ("R", "中規中矩，但排得很順。"),
            ("SR", "閃閃發光，形狀完美，值得紀念。"),
            ("SSR", "傳說中的黃金便，據說能治百病！"),
            ("UR", "彩虹皇冠便，宇宙唯一，屎界傳說！")
        ]
        weights = [0.5, 0.25, 0.15, 0.08, 0.02]
        rarity, description = random.choices(cards, weights)[0]
        emoji = {"N": "💩", "R": "🟤", "SR": "✨", "SSR": "🌟", "UR": "👑"}[rarity]
        image_urls = {
            "N": "https://raw.githubusercontent.com/kailaw22/poop-tracker-bot/main/images/poop_n.png",
            "R": "https://raw.githubusercontent.com/kailaw22/poop-tracker-bot/main/images/poop_r.png",
            "SR": "https://raw.githubusercontent.com/kailaw22/poop-tracker-bot/main/images/poop_sr.png",
            "SSR": "https://raw.githubusercontent.com/kailaw22/poop-tracker-bot/main/images/poop_ssr.png",
            "UR": "https://raw.githubusercontent.com/kailaw22/poop-tracker-bot/main/images/poop_ur.png"
        }
        reply_text = f"{emoji} 抽到 {rarity} 級便便卡！\n{description}"
        image_url = image_urls[rarity]
        line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text=reply_text), ImageSendMessage(original_content_url=image_url, preview_image_url=image_url)]
        )
        return

    elif msg == "兜不住屎":
        reply = f"{user_name} 愛吃大便 💩"
    elif msg == "屎王":
        reply = "豪哥是gay"
    elif msg in ["幫助", "help", "使用說明"]:
        reply = (
            "📖 使用說明（需完整輸入指令）：\n\n"
            "【個人聊天功能】\n"
            "💩 大便 / 💩 → 記錄大便\n"
            "📊 查詢 → 今天大幾次\n"
            "📅 查詢本週 → 本週大幾次\n"
            "🗓️ 查詢本月 → 本月大幾次\n"
            "🃏 便便抽卡 → 隨機抽卡，SSR 有彩虹便！\n\n"
            "【群組功能】\n"
            "🏆 排行榜 → 今日群組排行\n"
            "📅 週排行 → 本週群組排行\n"
            "🗓️ 月排行 → 本月群組排行\n\n"
            "【通用彩蛋】\n"
            "🤡 兜不住屎 → {你} 愛吃大便"
        )
    else:
        reply = "⚠️ 指令無法辨識，請精準輸入或輸入「幫助」查看所有功能"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )