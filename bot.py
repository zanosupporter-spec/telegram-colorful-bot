import os
import json
from datetime import datetime
from typing import Dict

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

load_dotenv()

# -------------------------
# CONFIG
# -------------------------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@yourchannel")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_FILE = "users_data.json"

# -------------------------
# DATABASE HELPERS
# -------------------------
def load_users_db() -> Dict:
    """Load users database from JSON file"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}


def save_users_db(data: Dict):
    """Save users database to JSON file"""
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_user_data(user_id: int) -> Dict:
    """Get user data or create new"""
    db = load_users_db()
    user_id_str = str(user_id)

    if user_id_str not in db:
        db[user_id_str] = {
            "user_id": user_id,
            "balance": 0.0,
            "bonus_earned": 0.0,
            "total_referrals": 0,
            "referral_earnings": 0.0,
            "tasks_completed": 0,
            "wallet_address": None,
            "withdrawal_history": [],
            "created_at": datetime.now().isoformat(),
            "referrer_id": None,
        }
        save_users_db(db)

    return db[user_id_str]


def update_user_data(user_id: int, data: Dict):
    """Update user data"""
    db = load_users_db()
    db[str(user_id)] = data
    save_users_db(db)


def add_referral(referrer_id: int, referred_user_id: int):
    """Add referral and credit earnings"""
    referrer_data = get_user_data(referrer_id)
    referred_data = get_user_data(referred_user_id)

    referrer_data["total_referrals"] += 1
    referrer_data["referral_earnings"] += 0.50  # $0.50 per referral
    referrer_data["balance"] += 0.50

    referred_data["referrer_id"] = referrer_id
    referred_data["bonus_earned"] += 1.00  # $1.00 bonus for joining via referral

    update_user_data(referrer_id, referrer_data)
    update_user_data(referred_user_id, referred_data)


# -------------------------
# MENU LAYOUTS
# -------------------------
MAIN_MENU = [
    [
        InlineKeyboardButton("💰 Bonus", callback_data="bonus"),
        InlineKeyboardButton("👥 Refer", callback_data="refer"),
    ],
    [
        InlineKeyboardButton("✅ Tasks", callback_data="tasks"),
        InlineKeyboardButton("💳 Set Wallet", callback_data="set_wallet"),
    ],
    [
        InlineKeyboardButton("💸 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("📊 Stats", callback_data="stats"),
    ],
]

BACK_BUTTON = [[InlineKeyboardButton("⬅️ Back", callback_data="home")]]

TASKS_LIST = [
    {"id": "task_1", "name": "Follow Twitter", "reward": 0.50},
    {"id": "task_2", "name": "Subscribe YouTube", "reward": 0.75},
    {"id": "task_3", "name": "Join Discord", "reward": 0.60},
    {"id": "task_4", "name": "Like on Instagram", "reward": 0.40},
    {"id": "task_5", "name": "Share with Friends", "reward": 1.00},
]

# -------------------------
# HELPERS
# -------------------------
async def is_user_in_channel(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        status = member.status
        return status in ["member", "administrator", "creator"]
    except Exception:
        return False


async def show_home_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    if not await is_user_in_channel(context, user.id):
        await update.message.reply_text(
            f"👋 Welcome, {user.first_name}!\n\n"
            f"To unlock the menu, you must join our channel first:\n"
            f"{CHANNEL_USERNAME}\n\n"
            f"After joining, press <b>Check Again</b> below.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📣 Join Channel",
                            url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
                        )
                    ],
                    [InlineKeyboardButton("✅ Check Again", callback_data="check_join")],
                ]
            ),
        )
        return

    user_data = get_user_data(user.id)
    await update.message.reply_text(
        f"✨ <b>Welcome to Premium Bot, {user.first_name}</b> ✨\n\n"
        f"💰 Your Balance: <b>${user_data['balance']:.2f}</b>\n"
        f"📈 Total Earned: <b>${user_data['bonus_earned'] + user_data['referral_earnings']:.2f}</b>\n\n"
        f"Choose an option below:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(MAIN_MENU),
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    # Check if referred
    args = context.args
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        user_data = get_user_data(user.id)
        if not user_data.get("referrer_id"):
            add_referral(referrer_id, user.id)

    await show_home_menu(update, context)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    user = query.from_user
    if not user:
        return

    data = query.data
    user_data = get_user_data(user.id)

    if data == "check_join":
        if await is_user_in_channel(context, user.id):
            if user_data["bonus_earned"] == 0:
                user_data["balance"] += 2.00
                user_data["bonus_earned"] += 2.00
                update_user_data(user.id, user_data)

            await query.edit_message_text(
                "✅ Great! You joined the channel.\n\n"
                "💰 Welcome Bonus: <b>$2.00</b> added!\n\n"
                "Here is the main menu:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(MAIN_MENU),
            )
        else:
            await query.edit_message_text(
                "⚠️ You still haven't joined the channel yet.\n\n"
                "Please join: " + CHANNEL_USERNAME + "\n\n"
                "Then click the button below.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "📣 Join Channel",
                                url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
                            )
                        ],
                        [InlineKeyboardButton("✅ Check Again", callback_data="check_join")],
                    ]
                ),
            )
        return

    if data == "home":
        if await is_user_in_channel(context, user.id):
            user_data = get_user_data(user.id)
            await query.edit_message_text(
                f"✨ <b>Main Menu</b> ✨\n\n"
                f"💰 Balance: <b>${user_data['balance']:.2f}</b>\n"
                f"📈 Total: <b>${user_data['bonus_earned'] + user_data['referral_earnings']:.2f}</b>\n\n"
                f"Choose an option:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(MAIN_MENU),
            )
        else:
            await query.edit_message_text(
                "❌ You need to join the channel first.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "📣 Join Channel",
                                url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
                            )
                        ],
                        [InlineKeyboardButton("✅ Check Again", callback_data="check_join")],
                    ]
                ),
            )
        return

    if data == "bonus":
        await query.edit_message_text(
            f"💰 <b>Bonus Rewards</b>\n\n"
            f"✅ Welcome Bonus: $2.00 (Claimed)\n"
            f"👥 Daily Check-in: $0.10/day\n"
            f"🎯 Referral Bonus: $1.00 per referral\n"
            f"⭐ Task Bonus: Up to $5.00\n\n"
            f"<b>Your Bonus Earned: ${user_data['bonus_earned']:.2f}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📅 Daily Bonus",
                            callback_data="daily_bonus",
                        )
                    ],
                ]
                + BACK_BUTTON
            ),
        )
        return

    if data == "daily_bonus":
        user_data = get_user_data(user.id)
        last_bonus = context.user_data.get(f"last_bonus_{user.id}")

        if last_bonus == datetime.now().date():
            await query.answer("❌ Already claimed today!", show_alert=True)
            return

        user_data["balance"] += 0.10
        user_data["bonus_earned"] += 0.10
        update_user_data(user.id, user_data)
        context.user_data[f"last_bonus_{user.id}"] = datetime.now().date()

        await query.edit_message_text(
            f"✅ <b>Daily Bonus Claimed!</b>\n\n"
            f"💰 +$0.10\n"
            f"<b>New Balance: ${user_data['balance']:.2f}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(BACK_BUTTON),
        )
        return

    if data == "refer":
        referral_link = f"https://t.me/{context.bot.username}?start={user.id}"
        await query.edit_message_text(
            f"👥 <b>Refer Friends & Earn</b>\n\n"
            f"Earn <b>$0.50</b> for each friend who joins via your link!\n\n"
            f"<b>Your Referral Link:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"👥 <b>Total Referrals:</b> {user_data['total_referrals']}\n"
            f"💵 <b>Referral Earnings:</b> ${user_data['referral_earnings']:.2f}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📋 Copy Link", callback_data="copy_refer_link"
                        )
                    ],
                ]
                + BACK_BUTTON
            ),
        )
        return

    if data == "copy_refer_link":
        referral_link = f"https://t.me/{context.bot.username}?start={user.id}"
        await query.answer(f"Link copied: {referral_link}", show_alert=True)
        return

    if data == "tasks":
        task_buttons = []
        for task in TASKS_LIST:
            task_buttons.append(
                [
                    InlineKeyboardButton(
                        f"✅ {task['name']} (${task['reward']})",
                        callback_data=task["id"],
                    )
                ]
            )
        task_buttons.extend(BACK_BUTTON)

        await query.edit_message_text(
            f"✅ <b>Available Tasks</b>\n\n"
            f"Complete tasks to earn money!\n\n"
            f"📊 <b>Tasks Completed:</b> {user_data['tasks_completed']}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(task_buttons),
        )
        return

    for task in TASKS_LIST:
        if data == task["id"]:
            if task["id"] in context.user_data.get(f"completed_tasks_{user.id}", []):
                await query.answer("❌ Task already completed!", show_alert=True)
                return

            user_data["balance"] += task["reward"]
            user_data["tasks_completed"] += 1

            if f"completed_tasks_{user.id}" not in context.user_data:
                context.user_data[f"completed_tasks_{user.id}"] = []

            context.user_data[f"completed_tasks_{user.id}"].append(task["id"])
            update_user_data(user.id, user_data)

            await query.edit_message_text(
                f"✅ <b>Task Completed!</b>\n\n"
                f"💰 +${task['reward']:.2f}\n"
                f"<b>New Balance: ${user_data['balance']:.2f}</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(BACK_BUTTON),
            )
            return

    if data == "set_wallet":
        await query.edit_message_text(
            f"💳 <b>Set Wallet Address</b>\n\n"
            f"Current Wallet: <b>{user_data['wallet_address'] or 'Not Set'}</b>\n\n"
            f"Send your wallet address in the next message.\n\n"
            f"<i>Supported: Bitcoin, Ethereum, TRX, etc.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(BACK_BUTTON),
        )
        context.user_data["waiting_for_wallet"] = True
        return

    if data == "withdraw":
        if not user_data["wallet_address"]:
            await query.answer(
                "❌ Please set your wallet address first!", show_alert=True
            )
            return

        if user_data["balance"] < 1.0:
            await query.edit_message_text(
                f"❌ <b>Insufficient Balance</b>\n\n"
                f"Minimum withdrawal: <b>$1.00</b>\n"
                f"Your balance: <b>${user_data['balance']:.2f}</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(BACK_BUTTON),
            )
            return

        await query.edit_message_text(
            f"💸 <b>Withdraw Funds</b>\n\n"
            f"💰 Available Balance: <b>${user_data['balance']:.2f}</b>\n"
            f"📍 Wallet: <code>{user_data['wallet_address']}</code>\n\n"
            f"Choose withdrawal amount:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("$1.00", callback_data="withdraw_1")],
                    [InlineKeyboardButton("$5.00", callback_data="withdraw_5")],
                    [InlineKeyboardButton("$10.00", callback_data="withdraw_10")],
                    [InlineKeyboardButton("Withdraw All", callback_data="withdraw_all")],
                ]
                + BACK_BUTTON
            ),
        )
        return

    if data.startswith("withdraw_"):
        if not user_data["wallet_address"]:
            await query.answer("❌ Wallet not set!", show_alert=True)
            return

        if data == "withdraw_1":
            amount = 1.0
        elif data == "withdraw_5":
            amount = 5.0
        elif data == "withdraw_10":
            amount = 10.0
        elif data == "withdraw_all":
            amount = user_data["balance"]
        else:
            return

        if user_data["balance"] < amount:
            await query.answer("❌ Insufficient balance!", show_alert=True)
            return

        user_data["balance"] -= amount
        withdrawal_record = {
            "amount": amount,
            "wallet": user_data["wallet_address"],
            "date": datetime.now().isoformat(),
            "status": "pending",
        }
        user_data["withdrawal_history"].append(withdrawal_record)
        update_user_data(user.id, user_data)

        await query.edit_message_text(
            f"✅ <b>Withdrawal Initiated</b>\n\n"
            f"💸 Amount: <b>${amount:.2f}</b>\n"
            f"📍 Wallet: <code>{user_data['wallet_address']}</code>\n"
            f"⏳ Status: <b>Pending</b>\n\n"
            f"You will receive your funds within 24-48 hours.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(BACK_BUTTON),
        )
        return

    if data == "stats":
        total_earned = user_data["bonus_earned"] + user_data["referral_earnings"]
        total_withdrawn = sum(w["amount"] for w in user_data["withdrawal_history"])

        await query.edit_message_text(
            f"📊 <b>Your Statistics</b>\n\n"
            f"💰 <b>Current Balance:</b> ${user_data['balance']:.2f}\n"
            f"💵 <b>Total Earned:</b> ${total_earned:.2f}\n"
            f"✅ <b>Bonus Earned:</b> ${user_data['bonus_earned']:.2f}\n"
            f"👥 <b>Referral Earnings:</b> ${user_data['referral_earnings']:.2f}\n"
            f"📈 <b>Total Referrals:</b> {user_data['total_referrals']}\n"
            f"✔️ <b>Tasks Completed:</b> {user_data['tasks_completed']}\n"
            f"💸 <b>Total Withdrawn:</b> ${total_withdrawn:.2f}\n"
            f"📅 <b>Member Since:</b> {user_data['created_at'][:10]}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(BACK_BUTTON),
        )
        return


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    if context.user_data.get("waiting_for_wallet"):
        wallet_address = update.message.text.strip()

        if len(wallet_address) < 20:
            await update.message.reply_text(
                "❌ Invalid wallet address. Please try again.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        user_data = get_user_data(user.id)
        user_data["wallet_address"] = wallet_address
        update_user_data(user.id, user_data)

        context.user_data["waiting_for_wallet"] = False

        await update.message.reply_text(
            f"✅ <b>Wallet Address Saved!</b>\n\n"
            f"📍 {wallet_address}\n\n"
            f"You can now withdraw your earnings!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(MAIN_MENU),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Bot Commands</b>\n\n"
        "/start - Open main menu\n"
        "/help - Show this message\n"
        "/stats - View your stats\n\n"
        "Use the buttons to navigate.",
        parse_mode="HTML",
    )


def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )

    print("🤖 Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
