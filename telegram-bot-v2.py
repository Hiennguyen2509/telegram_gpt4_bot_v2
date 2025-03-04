import telebot
import requests
import openai
import os

from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# Lấy API Key từ biến môi trường
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print("Loaded API Key: ", OPENAI_API_KEY)

# 🔹 Nhập Token của bot Telegram
TELEGRAM_BOT_TOKEN = "7962172499:AAGt--fa3YcJB_VVbgULYkK6NaH5vSxVPjA"

# Khởi tạo bot Telegram
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Xử lý ảnh từ Telegram"""
    try:
        # Lấy ID của ảnh lớn nhất (chất lượng cao nhất)
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)

        # Lấy URL ảnh từ Telegram
        image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_info.file_path}"

        # Gửi ảnh đến GPT-4o để phân tích và kiểm tra
        analysis_result = analyze_trade_image(image_url)

        # Gửi kết quả về Telegram
        bot.reply_to(message, analysis_result)

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi khi xử lý ảnh:\n\n{str(e)}")

def analyze_trade_image(image_url):
    """Gửi ảnh đến GPT-4o và kiểm tra điều kiện giao dịch"""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = """
Bạn là một chuyên gia tài chính. Tôi sẽ cung cấp một hình ảnh chứa thông tin giao dịch forex. 
Hãy phân tích dữ liệu trong ảnh và kiểm tra xem có đáp ứng các tiêu chí sau không:

1️⃣ **Thời gian mở lệnh của hai tài khoản phải có sai số không quá 10 giây.**  
2️⃣ **Thời gian đóng lệnh của hai tài khoản phải có sai số không quá 10 giây.**  

📌 **Cách kiểm tra:**  
- Nếu **sai số ≤ 10 giây**, giao dịch hợp lệ. **Không được báo lỗi trong trường hợp này.**  
- Nếu **sai số > 10 giây**, giao dịch không hợp lệ và cần báo lỗi.  

🔹 **Cách trả về kết quả:**  
- Nếu giao dịch hợp lệ (**sai số ≤ 10 giây**), **chỉ trả về đúng ký hiệu** `✅`. **Không được giải thích thêm.**  
- Nếu giao dịch không hợp lệ (**sai số > 10 giây**), trả về `❌` kèm theo lý do và số giây sai lệch.  

📢 **Lưu ý quan trọng:**  
❌ **Không báo lỗi nếu sai số nhỏ hơn hoặc bằng 10 giây.** GPT **chỉ báo lỗi nếu sai số lớn hơn 10 giây.**  
✅ **Nếu hợp lệ, trả về đúng `✅` mà không có bất kỳ văn bản nào khác.**
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Bạn là chuyên gia phân tích giao dịch forex."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]}
        ],
        max_tokens=1000
    )

    return response.choices[0].message.content if response.choices else "❌ Không thể phân tích giao dịch."

# Chạy bot Telegram
bot.polling()
