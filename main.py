import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import requests
from bs4 import BeautifulSoup
import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
app = Flask(__name__)
def stock_name(StockName):
    # 設置 index constant，數字代表我們要的資料在 list 的位置
    TARGET_TABLE_INDEX = 1
    STOCK_NO_INDEX = 2
    STOCK_NAME_INDEX = 3
    STOCK_INDUSTRY_INDEX = 6
    # JSON settings
    TITLE = "stock"
    JSON_INDENT = 4

    # 送出 HTTP Request
    url = "https://isin.twse.com.tw/isin/class_main.jsp"
    res = requests.get(url, params={
        "market": "1",
        "issuetype": "1",
        "Page": "1",
        "chklike": "Y"
    })

    # 處理編碼，使用預設 utf-8 的話 res.text 的內容會有亂碼
    res.encoding = "Big5"
    res_html = res.text

    # Parse
    soup = BeautifulSoup(res_html, "lxml")

    # 因為這個 HTML 裡面有兩張 table
    # 所以我們 find_all("table") 回傳的 list 的 length 會是 2
    # 而我們要的資料在第二張
    tr_list = soup.find_all("table")[TARGET_TABLE_INDEX].find_all("tr")

    # tr_list 的第一個是 item 是欄位名稱
    # 我們這邊用不到所以 pop 掉
    tr_list.pop(0)

    # 開始處理資料
    result = []
    for tr in tr_list:

        td_list = tr.find_all("td")

        # 股票代碼
        stock_no_val = td_list[STOCK_NO_INDEX].text

        # 股票名稱
        stock_name_val = td_list[STOCK_NAME_INDEX].text

        # 股票產業類別
        stock_industry_val = td_list[STOCK_INDUSTRY_INDEX].text

        # 整理成 dict 存起來
        result.append({
            stock_name_val: stock_no_val,
            # "stockNo": stock_no_val,
            # "stockName": stock_name_val,
            #"stockIndustry": stock_industry_val
        })


    # 將 dict 輸出成檔案
    # stock_list_dict = {TITLE: result}
    # with open("stock_info_list.json", "w", encoding="utf-8") as f:
    #     f.write(
    #         json.dumps(stock_list_dict,
    #                    indent=JSON_INDENT,
    #                    ensure_ascii=False)
    #     )
 
    for dic in result:
        if StockName in dic:
            return f"{dic[StockName]}"
    return f"{StockName}"


# 必須放上你的 Channel Access Token
line_bot_api = LineBotApi("6wO4SvysOQ5aJf85m3KQmiiUvCSECpfm3j6ITHy8wrM2PFls/yw/XLUr5i9Q2hx+dhISbBx8pZZtk4qw2kw5DxWP/V+KbcfwzxT/EqVDx92pVYpkeuCb84X1fJwl91jgzc0XlBmYaZD1qNdWcm0J4AdB04t89/1O/w1cDnyilFU=")
# 必須放上你的 Channel Secret
handler = WebhookHandler("9c72128fe7a523fa478bc27f38775410")
# 必須放上你的 User ID
line_bot_api.push_message("U8c21e4252efbbfc270eca39d1c001bf1", TextSendMessage(text="歡迎來到 NTU PYGCP!"))

firebase_admin.initialize_app()
db = firestore.client()

# 定義教學訊息内容
help_txt = """
NTU PYGCP Line 股市聊天機器人
---------------------------
使用教學：

指令 台股代號
------------
例：查詢 2330

便會回傳臺積電的交易價格(僅限昨日)

目前支援的指令有：

1. 查詢  搜尋該股票當日的價格
2. 教學  顯示教學 
"""

# 輸入股票代號，回傳該股票的收盤價
def tw_stock_crawler(sid):
    res = requests.get("https://stock.wearn.com/cdata.asp?kind=%s"%sid)
    # 設定目標網頁的編碼
    res.encoding = "big5"
    # 用 html 格式解碼 爬下來的檔案
    html = BeautifulSoup(res.text, "html.parser")
    table = html.findAll("table")[0]
    trs = table.findAll("tr")
    tds = [tr.findAll("td") for tr in trs]
    # 找尋 table 裡第三個 tr 標籤內所有的 td 標籤
    today = tds[2]
    data = [float(td.text.replace("\xa0", "").replace(",", "")) for td in today[1:]]
    # 回傳一個字典
    return {
        "open": float(data[0]),
        "high": float(data[1]),
        "low": float(data[2]),
        "close": float(data[3]),
        "volume": float(data[4])
    }

def createReplyMessge(sid):
    doc = db.collection(f"{sid}_daily_data").document(f"{time.strftime('%Y%m%d')}").get()
    if doc.to_dict() == None:
        data =  tw_stock_crawler(sid)
    else:
        data = doc.to_dict()

    replyCheckMessage = ("NTU PYGCP BOT\n\n"
                         f"股票代號：{sid}\n"
                         f"開盤價：{data['open']} 元\n"
                         f"最高價：{data['high']} 元\n"
                         f"最低價：{data['low']} 元\n"
                         f"收盤價：{data['close']} 元\n"
                         f"成交量：{data['volume']}\n"
                         "！僅限收盤後的資料，若尚未收盤則是昨日資料！\n"
                         )

    return replyCheckMessage

# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    print(body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/", methods=["GET"])
def index():
    return "Hello World!"                         
                         
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 若使用者輸入“查詢”，呼叫 createReplyMessge()
    if "查詢" in event.message.text or "check" in event.message.text: 
        sid = event.message.text.split()[1]
        sid = stock_name(sid)
        if sid.isdigit():
            line_bot_api.reply_message(
                event.reply_token,
                TextMessage(text=createReplyMessge(sid), type="text")
                )
        else:
            line_bot_api.reply_message(
            event.reply_token,
            TextMessage(text="輸入錯誤")
            )
#若使用者輸入“help” 或 “教學”，顯示教學訊息
    elif "help" in event.message.text or "教學" in event.message.text:
        line_bot_api.reply_message(
            event.reply_token,
            TextMessage(text=help_txt, type="text")
        )
          
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)