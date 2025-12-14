import discord
from discord.ext import commands
from google import genai
from dotenv import load_dotenv
import os
from datetime import datetime

# --- 1. Configuration and Initialization ---

# تحميل المتغيرات من ملف .env (التوكنات والمفاتيح فقط)
load_dotenv()

# استدعاء مفاتيح الوصول من البيئة
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# الأرقام التعريفية (IDs) مدمجة هنا لضمان التشغيل السليم وعدم الخطأ في ملف .env
# الأرقام المستخدمة سابقاً
TICKET_CHANNEL_ID = 1239971597146783744
ACTIONS_CHANNEL_ID = 1239621280542490726
WARNING_1_ROLE_ID = 1447160434724438056
WARNING_2_ROLE_ID = 1447160478991126599
WARNING_3_ROLE_ID = 1447160521286746225
BLACKLIST_ROLE_ID = 1447160592803692677


# تهيئة البوت ونموذج Gemini
# استخدام Intents.all() لضمان استقبال جميع أنواع الرسائل
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# تهيئة نموذج جوجل
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"❌ Error initializing Gemini Client: {e}")
        client = None
else:
    print("❌ Critical Error: GEMINI_API_KEY not found in the environment.")
    client = None


# --- 2. Gemini System Prompt for Accounting/Support (Arabic) ---

SYSTEM_PROMPT_ACCOUNTING = f"""
أنت بوت الدعم الفني والمحاسبة الآلي لخادم **OSLO RP**. مهمتك هي تقييم الشكاوى والاستفسارات وحلها بصرامة وفقاً للقوانين المرفقة.

**تعليمات العمل الإلزامية:**
1.  **الاستفسارات والدعم الفني:** أجب بوضوح وهدوء، وقدم حلولاً خطوة بخطوة.
2.  **الشكاوى والمحاسبة:** حلل الشكوى بدقة وحدد القانون المخالف ونوع العقوبة (مثلاً: بلاك ليست يومين، تحذير أول).
3.  **صيغة الإخراج (Action Keyword):** يجب أن ينتهي الرد بكلمة مفتاحية واحدة من التالي:
    -   للتحذير الأول: `[ACTION: WARN_1]`
    -   للتحذير الثاني: `[ACTION: WARN_2]`
    -   للتحذير الثالث: `[ACTION: WARN_3]`
    -   للبلاك ليست (يجب ذكر المدة في الرسالة): `[ACTION: BLACKLIST]`
    -   لحل مشكلة أو رد عادي (لا عقوبة): `[ACTION: NONE]`
    -   لطلب أدلة إضافية: `[ACTION: WAIT]`

**قائمة القوانين والعقوبات لخادم OSLO RP (القوانين المتفق عليها):**
* القانون 1 (التخريب بعد انتهاء القيم/خروج الهوست): العقوبة: **بلاك ليست 10 أيام** -> `[ACTION: BLACKLIST]`
* القانون 2 (الإزعاج والتحدث في افري ون/الموجه العامة): العقوبة: **بلاك ليست يومين** -> `[ACTION: BLACKLIST]`
* القانون 3 (عدم الخوف على الحياة): العقوبة: **بلاك ليست 10 أيام** -> `[ACTION: BLACKLIST]`
* القانون 4 (التحدث في everyone من بعيد أو دون قريب): العقوبة: **بلاك ليست 10 أيام** -> `[ACTION: BLACKLIST]`
* القانون 5 (تغيير اللبس وهو مسقط): العقوبة: **بلاك ليست يومين** -> `[ACTION: BLACKLIST]`
* القانون 7 (الجمس الأسود - المطاردة/الإزعاج): العقوبة: **باند نهائي** (تعامل كـ **بلاك ليست دائمة**) -> `[ACTION: BLACKLIST]`
* القانون 10 (التحرك بعد انقلاب السيارة/VDM): عقوبة (VDM) هي **تحذير أول** -> `[ACTION: WARN_1]`، وعقوبة التحرك بعد الانقلاب **بلاك ليست 7 أيام** -> `[ACTION: BLACKLIST]`
* القانون 12 (RDM القتل العشوائي/الغش/الستريم سنايب): عقوبته **باند نهائي** (تعامل كـ **بلاك ليست دائمة**) -> `[ACTION: BLACKLIST]`
* القوانين الأخرى (دعم/توضيح/تنبيه): -> `[ACTION: NONE]`
"""

# --- 3. AI Helper Functions ---

async def get_ai_response(prompt: str, system_instruction: str):
    """Sends message to Gemini model and retrieves response."""
    if not client:
        return "عفواً، فشل الاتصال بنظام Gemini. يرجى مراجعة مفتاح API في ملف .env."
        
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                {"role": "user", "parts": [{"text": prompt}]},
            ],
            system_instruction=system_instruction
        )
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {e}")
        # رسالة الخطأ الداخلي التي ظهرت سابقاً:
        return "عفواً، واجهت خطأ داخلي في نظام الذكاء الاصطناعي."

async def apply_role_action(message: discord.Message, member: discord.Member, role_id: int, action_type: str, color: discord.Color, final_reply: str):
    role_to_apply = message.guild.get_role(role_id)
    actions_channel = bot.get_channel(ACTIONS_CHANNEL_ID)
    warning_roles_ids = [WARNING_1_ROLE_ID, WARNING_2_ROLE_ID, WARNING_3_ROLE_ID]
    
    if role_to_apply:
        roles_to_remove = [r for r in member.roles if r.id in warning_roles_ids or r.id == BLACKLIST_ROLE_ID]
        try:
            if role_to_apply in roles_to_remove:
                 roles_to_remove.remove(role_to_apply) 
            
            # التأكد من عدم محاولة سحب رتبة البوت نفسه
            if message.guild.me.top_role in roles_to_remove:
                 roles_to_remove.remove(message.guild.me.top_role)

            await member.remove_roles(*roles_to_remove, reason="Automated role removal before applying new action.")
        except discord.Forbidden:
            # رسالة خطأ إذا كانت رتبة البوت غير كافية
            await message.channel.send("❌ BOT Permission Error: Cannot manage roles. Check BOT hierarchy.")
            return

        await member.add_roles(role_to_apply, reason=f"Auto decision: {action_type} - {final_reply}")
        await message.channel.send(f"✅ Role granted to {member.mention}: **{role_to_apply.name}**.")
        
        if actions_channel:
            embed = discord.Embed(
                title=f"🚨 Automated {action_type} 🚨",
                description=f"**👤 Member:** {member.mention}\n**⚖️ Decision:** {final_reply}",
                color=color
            )
            embed.set_footer(text=f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await actions_channel.send(f"⚠️ New Action! {member.mention}", embed=embed)
    else:
        await message.channel.send(f"❌ Role Application Failed: Check hardcoded IDs.")

# --- 4. Discord Events ---

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user} is online and ready.')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # استخدام category_id للتحقق من قناة التكت
    is_ticket_channel = message.channel.category_id == TICKET_CHANNEL_ID if message.channel.category_id else False

    if is_ticket_channel:
        # Accounting Logic (Inside Ticket Channels)
        
        # التأكد من أن الرسائل تُقرأ حتى يعمل تحليل الـ AI
        messages_history = [f"{msg.author.name}: {msg.content}" async for msg in message.channel.history(limit=10)]
        messages_history.reverse()
        prompt = f"Ticket history:\n---\n{'\n'.join(messages_history)}\n---\nBased on rules, what is the decision and required action? Reply directed to the punished member."

        ai_response = await get_ai_response(prompt, SYSTEM_PROMPT_ACCOUNTING)

        action_keyword = "NONE"
        final_reply = ai_response
        
        # محاولة استخراج كلمة الإجراء حتى لو لم يكن التنسيق مثالياً
        if "[ACTION:" in ai_response:
            try:
                start_index = ai_response.rfind('[ACTION:')
                end_index = ai_response.find(']', start_index)
                action_keyword = ai_response[start_index + len('[ACTION:'):end_index].strip()
                final_reply = ai_response[:start_index].strip()
            except:
                pass

        await message.channel.send(f"**🤖 AI Support Reply:**\n{final_reply}")

        # نختار مؤلف الرسالة الأخيرة كعضو مستهدف
        member_to_punish = message.author 
        
        if action_keyword == "WARN_1":
            await apply_role_action(message, member_to_punish, WARNING_1_ROLE_ID, "WARN_1", discord.Color.green(), final_reply)
        elif action_keyword == "WARN_2":
            await apply_role_action(message, member_to_punish, WARNING_2_ROLE_ID, "WARN_2", discord.Color.gold(), final_reply)
        elif action_keyword == "WARN_3":
            await apply_role_action(message, member_to_punish, WARNING_3_ROLE_ID, "WARN_3", discord.Color.orange(), final_reply)
        elif action_keyword == "BLACKLIST":
            await apply_role_action(message, member_to_punish, BLACKLIST_ROLE_ID, "BLACKLIST", discord.Color.red(), final_reply)
        elif action_keyword == "WAIT":
            await message.channel.send("⏳ يرجى تزويدنا بأدلة أو معلومات إضافية لاستكمال عملية المحاسبة.")
            
    elif bot.user.mentioned_in(message):
        # General Chat/Conversation Logic (الرد على الإشارة)
        
        text_to_ai = message.content.replace(bot.user.mention, '').strip()

        chat_prompt = f"You are a friendly and helpful bot. Reply naturally and engagingly.\n\nQuestion: {text_to_ai}"
        
        ai_response = await get_ai_response(chat_prompt, "You are a friendly, digital companion ready to provide help and information.")

        await message.channel.send(f"👋 {message.author.mention} {ai_response}")

    await bot.process_commands(message)

# --- 5. Run Bot ---

print("⚠️ Bot is starting...")
if DISCORD_TOKEN:
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Failed to run bot. Check Discord Token and connection. Error: {e}")
