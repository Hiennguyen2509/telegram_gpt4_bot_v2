import os
import telebot
import requests
import openai
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# Lấy API từ biến môi trường
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = "Tài Khoản Giao Dịch"

# Nhập Token bot Telegram trực tiếp (không đưa vào biến môi trường nếu bạn muốn)
TELEGRAM_BOT_TOKEN = "8092143080:AAFm2YQ6qJvmAmuvlq1VG6SV_-MYMnzsC0E"

# Kiểm tra các biến môi trường đã được load chưa
if not all([OPENAI_API_KEY, AIRTABLE_API_KEY, BASE_ID]):
    raise ValueError("❌ Thiếu biến môi trường! Hãy kiểm tra file .env hoặc cấu hình trên Railway.")

# Khởi tạo bot Telegram
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

@bot.message_handler(content_types=['photo'])
def handle_photo_with_caption(message):
    """Xử lý ảnh và văn bản kèm theo"""
    try:
        if not message.caption:
            bot.reply_to(message, "❌ Bạn cần nhập văn bản theo cấu trúc:\n`ID tài khoản - Balance`\nVí dụ: `TK003 - 98687.78`")
            return

        text = message.caption.strip()
        if " - " not in text:
            bot.reply_to(message, "❌ Sai định dạng. Hãy gửi theo mẫu:\n`ID tài khoản - Balance`\nVí dụ: `TK003 - 98687.78`")
            return

        account_id, balance_str = text.split(" - ")
        account_id, balance_str = account_id.strip(), balance_str.strip()

        if not balance_str.replace(".", "").isdigit():
            bot.reply_to(message, "❌ Số dư không hợp lệ. Hãy kiểm tra lại tin nhắn.")
            return

        balance = float(balance_str)

        # Nhận file ảnh từ Telegram
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_info.file_path}"

        # Gửi ảnh đến GPT-4o để trích xuất dữ liệu
        gpt_result = analyze_balance_image(image_url)

        if not gpt_result or "Balance:" not in gpt_result or "Account ID:" not in gpt_result:
            bot.reply_to(message, "❌ Không thể xác minh dữ liệu từ ảnh. Hãy thử lại với ảnh rõ hơn.")
            return

        # Trích xuất dữ liệu từ kết quả OCR
        lines = gpt_result.split(", ")
        gpt_balance = float(lines[0].split(": ")[1].replace(",", ""))
        gpt_account_id = lines[1].split(": ")[1].strip()

        if gpt_account_id != account_id or gpt_balance != balance:
            bot.reply_to(message, f"❌ Dữ liệu không khớp!\n📌 **Tin nhắn:** {account_id} - {balance}\n📷 **Ảnh OCR:** {gpt_account_id} - {gpt_balance}")
            return

        # Cập nhật Airtable
        success, error_message = update_airtable(account_id, balance)

        if success:
            bot.reply_to(message, f"✅ Đã xác minh & cập nhật số dư {balance} cho tài khoản {account_id} vào Airtable.")
        else:
            bot.reply_to(message, f"❌ Lỗi cập nhật Airtable: {error_message}")

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi xử lý dữ liệu: {str(e)}")

def analyze_balance_image(image_url):
    """Gửi ảnh đến GPT-4o và trích xuất Balance + ID tài khoản"""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = """
Bạn là chuyên gia tài chính. Tôi sẽ gửi một ảnh chụp màn hình tài khoản giao dịch forex.  
Hãy trích xuất **Balance (số dư tài khoản)** và **Account ID (ID tài khoản)** từ ảnh này.  

### 📌 Yêu cầu:
1️⃣ **Chỉ trích xuất số dư (Balance) và ID tài khoản, không lấy các thông tin khác.**  
2️⃣ **Loại bỏ mọi ký tự đặc biệt hoặc thông tin dư thừa.**  
3️⃣ **Nếu không tìm thấy dữ liệu, hãy trả về `"Lỗi: Không tìm thấy thông tin."`**  
4️⃣ **Trả về theo định dạng chuẩn sau:**
   - `Balance: <số dư>, Account ID: <ID tài khoản>`  
   - **Ví dụ đúng:**  
     - `Balance: 98687.78, Account ID: TK003`  
     - `Balance: 102500.50, Account ID: FTMO789012`  
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Bạn là chuyên gia phân tích tài khoản giao dịch forex."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]},
        ],
        max_tokens=1000
    )

    return response.choices[0].message.content if response.choices else None

def update_airtable(account_id, balance):
    """Cập nhật số dư tài khoản lên Airtable"""

    # Bước 1: Tìm Record ID của Account_ID
    search_url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}?filterByFormula={{Account_ID}}='{account_id}'"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}

    search_response = requests.get(search_url, headers=headers)
    
    if search_response.status_code != 200:
        return False, f"Lỗi tìm kiếm Account_ID: {search_response.text}"

    records = search_response.json().get("records", [])
    
    if not records:
        return False, f"Không tìm thấy tài khoản {account_id} trên Airtable."

    record_id = records[0]["id"]

    # Bước 2: Cập nhật Balance của Account_ID đó
    update_url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}/{record_id}"
    balance = float(balance)  # Đảm bảo gửi số thực

    data = {
        "fields": {
            "Balance": balance
        }
    }

    try:
        update_response = requests.patch(update_url, json=data, headers=headers)
        if update_response.status_code == 200:
            return True, None  # Thành công
        else:
            return False, update_response.json().get("error", {}).get("message", "Lỗi không xác định từ Airtable")

    except requests.exceptions.RequestException as e:
        return False, str(e)  # Lỗi kết nối

# Chạy bot Telegram
bot.polling()
