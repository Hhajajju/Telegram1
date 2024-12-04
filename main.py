from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import sqlite3
import time
import os

# Initialize the bot and set up the database connection
application = Application.builder().token('7693242351:AAG0QU6ThaIYvKWbWicC03JDgDKBHhwIX38').build()


# Connect to SQLite database
conn = sqlite3.connect('earncash.db')
cursor = conn.cursor()

# List of admin user IDs (change these IDs to the actual admin IDs)
ADMIN_USER_IDS = [123456789, 987654321]

# Create necessary tables (if they don't exist)
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0,
    last_bonus_claim INTEGER,
    last_ad_watch INTEGER,
    referrals INTEGER DEFAULT 0,
    withdrawal_pending REAL DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT,
    reward REAL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS ads (
    ad_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_text TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS task_submissions (
    user_id INTEGER,
    task_id INTEGER,
    screenshot TEXT,  -- Link to the screenshot or file path
    status TEXT DEFAULT 'pending',  -- Status of the task (pending, approved, rejected)
    PRIMARY KEY(user_id, task_id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS reward_history (
    user_id INTEGER,
    amount REAL,
    reason TEXT,
    timestamp INTEGER
)
''')

conn.commit()

# Command handler for /start
async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    keyboard = [
        [KeyboardButton("🎁 Daily Bonus"), KeyboardButton("▶️ Watch Ads")],
        [KeyboardButton("🎉 Task"), KeyboardButton("👥 Invite")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("☎️ Support"), KeyboardButton("✅ About Us")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    update.message.reply_text(
        "🎉 Welcome to GetCash! 💰\n\n"
        "Thank you for joining! Here’s how you can start earning:\n"
        "👀 Watch Ads – Earn by viewing ads.\n"
        "🤝 Refer Friends – Invite others and earn even more!\n"
        "✅ Complete Tasks – Simple tasks to boost your earnings.\n"
        "💸 Withdraw Anytime – Cash out your earnings whenever you like.\n\n"
        "👉 Join the Group",
        reply_markup=reply_markup
    )

# Balance handler
async def balance(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]
    update.message.reply_text(f"Your balance is: ${balance}")

# Bonus handler (once every 24 hours)
async def claim_bonus(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    current_time = int(time.time())

    cursor.execute("SELECT last_bonus_claim FROM users WHERE user_id=?", (user_id,))
    last_claim = cursor.fetchone()[0]

    if last_claim and current_time - last_claim < 86400:
        update.message.reply_text("You can only claim the bonus once every 24 hours.")
        return

    cursor.execute("UPDATE users SET balance = balance + 0.002, last_bonus_claim = ? WHERE user_id=?", (current_time, user_id))
    conn.commit()
    # Log the bonus claim in the reward history
    cursor.execute("INSERT INTO reward_history (user_id, amount, reason, timestamp) VALUES (?, ?, ?, ?)",
                   (user_id, 0.002, "Daily Bonus", current_time))
    conn.commit()
    update.message.reply_text("You've successfully claimed your $0.002 bonus!")

# Watch Ads (tracking each ad)
async def watch_ads(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    ad_number = int(context.args[0])  # Example: Watch Ads 1 -> args[0] is 1

    cursor.execute("SELECT last_ad_watch FROM users WHERE user_id=?", (user_id,))
    last_ad_time = cursor.fetchone()[0]
    current_time = int(time.time())

    if last_ad_time and current_time - last_ad_time < 7200:  # 2 hours
        update.message.reply_text(f"You can only watch ad {ad_number} once every 2 hours.")
        return

    cursor.execute("UPDATE users SET balance = balance + 0.005, last_ad_watch = ? WHERE user_id=?", (current_time, user_id))
    conn.commit()
    # Log the ad watch in the reward history
    cursor.execute("INSERT INTO reward_history (user_id, amount, reason, timestamp) VALUES (?, ?, ?, ?)",
                   (user_id, 0.005, f"Watched Ad {ad_number}", current_time))
    conn.commit()
    update.message.reply_text(f"You've successfully watched ad {ad_number} and earned $0.005!")

# Claim Task (Simulating Task Completion)
async def claim_task(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    task_description = "Visit our website, submit screenshot if you have completed the task."
    task_link = "https://website.com"
    reward = 0.005

    update.message.reply_text(f"Task: {task_description}\nYou can earn ${reward} if you complete this task.\n\n{task_link}\n\nTo submit your task, send a screenshot.")

# Handle screenshot submission for tasks
async def submit_task(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    if update.message.photo:
        # Assuming the user submits a screenshot
        task_id = context.args[0]  # Get the task ID from args
        cursor.execute("UPDATE users SET balance = balance + 0.005 WHERE user_id=?", (user_id,))
        conn.commit()
        
        # Log the task reward in the reward history
        cursor.execute("INSERT INTO reward_history (user_id, amount, reason, timestamp) VALUES (?, ?, ?, ?)",
                       (user_id, 0.005, f"Task {task_id} Completion", int(time.time())))
        conn.commit()
        
        # Update task status to 'submitted'
        cursor.execute("INSERT OR REPLACE INTO task_submissions (user_id, task_id, status) VALUES (?, ?, ?)", 
                       (user_id, task_id, 'submitted'))
        conn.commit()

        update.message.reply_text("Task submission successful. Admin will review it shortly.")
    else:
        update.message.reply_text("Please send a screenshot of the task completion.")

# Invite handler - Generate referral link and display how many referrals user has
async def invite(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    cursor.execute("SELECT referrals FROM users WHERE user_id=?", (user_id,))
    referrals = cursor.fetchone()[0]

    referral_link = f"t.me/YourBotName?start={user_id}"

    update.message.reply_text(f"Refer and earn $0.05 for each referral.\n\nHere is your link: {referral_link}\n\nYou have invited {referrals} users.")

# Withdraw handler
async def withdraw(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]

    if balance < 3:
        update.message.reply_text(f"Your balance is ${balance}. Minimum withdraw is $3.")
        return

    update.message.reply_text(f"Your balance is ${balance}. Please choose your preferred withdrawal method:\n(TRX button)(TON button)(LTC button)")

# Process Withdrawal
async def process_withdraw(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]

    if balance >= 3:
        # Assuming the user submits address and amount
        cursor.execute("UPDATE users SET withdrawal_pending = ? WHERE user_id=?", (balance, user_id))
        conn.commit()
        # Log the withdrawal request in the reward history
        cursor.execute("INSERT INTO reward_history (user_id, amount, reason, timestamp) VALUES (?, ?, ?, ?)",
                       (user_id, balance, "Withdrawal Request", int(time.time())))
        conn.commit()
        update.message.reply_text("Your withdrawal request has been submitted. It will be processed within 24 hours.")
    else:
        update.message.reply_text("You do not have enough balance to withdraw.")

# Support Command Handler
async def support(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Need help? Contact support@Earncash_0nline.")

# About Us Command Handler
async def about_us(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "EarnCash is a platform where you can earn money by completing simple tasks, watching ads, and referring friends. We aim to provide a seamless and rewarding experience for our users!"
    )
    
# Admin can approve or reject withdrawal requests
async def approve_or_reject_withdrawal(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMIN_USER_IDS:
        update.message.reply_text("You do not have admin privileges.")
        return

    try:
        target_user_id = int(context.args[0])
        action = context.args[1].lower()  # "approve" or "reject"

        cursor.execute("SELECT withdrawal_pending FROM users WHERE user_id=?", (target_user_id,))
        withdrawal_pending = cursor.fetchone()

        if withdrawal_pending:
            amount = withdrawal_pending[0]
            if amount > 0:
                if action == 'approve':
                    cursor.execute("UPDATE users SET balance = balance - ?, withdrawal_pending = 0 WHERE user_id=?", (amount, target_user_id))
                    conn.commit()
                    update.message.reply_text(f"Withdrawal of ${amount} for user {target_user_id} has been approved.")
                    # Notify user about withdrawal approval
                    context.bot.send_message(target_user_id, f"Your withdrawal of ${amount} has been approved.")
                elif action == 'reject':
                    cursor.execute("UPDATE users SET withdrawal_pending = 0 WHERE user_id=?", (target_user_id,))
                    conn.commit()
                    update.message.reply_text(f"Withdrawal of ${amount} for user {target_user_id} has been rejected.")
                    # Notify user about rejection
                    context.bot.send_message(target_user_id, "Your withdrawal request has been rejected.")
                else:
                    update.message.reply_text("Invalid action. Use 'approve' or 'reject'.")
            else:
                update.message.reply_text(f"No pending withdrawal for user {target_user_id}.")
        else:
            update.message.reply_text(f"No pending withdrawal for user {target_user_id}.")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /approve_or_reject_withdrawal <user_id> <approve/reject>")

# Admin can approve or reject task submissions
async def approve_or_reject_task_submission(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMIN_USER_IDS:
        update.message.reply_text("You do not have admin privileges.")
        return

    try:
        target_user_id = int(context.args[0])
        task_id = int(context.args[1])
        action = context.args[2].lower()  # "approve" or "reject"

        cursor.execute("SELECT screenshot FROM task_submissions WHERE user_id=? AND task_id=?", (target_user_id, task_id))
        submission = cursor.fetchone()

        if submission:
            if action == 'approve':
                cursor.execute("UPDATE task_submissions SET status = 'approved' WHERE user_id=? AND task_id=?", (target_user_id, task_id))
                conn.commit()

                # Award reward to user
                cursor.execute("SELECT reward FROM tasks WHERE task_id=?", (task_id,))
                reward = cursor.fetchone()[0]
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (reward, target_user_id))
                conn.commit()

                context.bot.send_message(target_user_id, f"Your task submission has been approved. You have earned ${reward}.")
                update.message.reply_text(f"Task submission for user {target_user_id} has been approved and ${reward} has been credited.")
            elif action == 'reject':
                cursor.execute("UPDATE task_submissions SET status = 'rejected' WHERE user_id=? AND task_id=?", (target_user_id, task_id))
                conn.commit()
                context.bot.send_message(target_user_id, "Your task submission has been rejected.")
                update.message.reply_text(f"Task submission for user {target_user_id} has been rejected.")
            else:
                update.message.reply_text("Invalid action. Use 'approve' or 'reject'.")
        else:
            update.message.reply_text(f"No task submission found for user {target_user_id} and task {task_id}.")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /approve_or_reject_task_submission <user_id> <task_id> <approve/reject>")

# Admin can post a new task
async def post_task(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMIN_USER_IDS:
        update.message.reply_text("You do not have admin privileges.")
        return

    try:
        task_description = ' '.join(context.args[:-1])
        reward = float(context.args[-1])

        cursor.execute("INSERT INTO tasks (description, reward) VALUES (?, ?)", (task_description, reward))
        conn.commit()

        update.message.reply_text(f"New task posted successfully!\nTask: {task_description}\nReward: ${reward}")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /post_task <task_description> <reward>")

# Admin can post an ad
async def post_ad(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMIN_USER_IDS:
        update.message.reply_text("You do not have admin privileges.")
        return

    ad_text = ' '.join(context.args)

    cursor.execute("INSERT INTO ads (ad_text) VALUES (?)", (ad_text,))
    conn.commit()

    update.message.reply_text(f"New ad posted: {ad_text}")

# Show tasks to users
async def show_tasks(update: Update, context: CallbackContext) -> None:
    cursor.execute("SELECT task_id, description, reward FROM tasks")
    tasks = cursor.fetchall()

    if tasks:
        message = "Here are the available tasks:\n"
        for task in tasks:
            message += f"Task ID: {task[0]} – {task[1]} – Reward: ${task[2]}\n"
        update.message.reply_text(message)
    else:
        update.message.reply_text("No tasks available at the moment.")

# Show ads to users
async def show_ads(update: Update, context: CallbackContext) -> None:
    cursor.execute("SELECT ad_id, ad_text FROM ads")
    ads = cursor.fetchall()

    if ads:
        message = "Here are the available ads:\n"
        for ad in ads:
            message += f"Ad ID: {ad[0]} – {ad[1]}\n"
        update.message.reply_text(message)
    else:
        update.message.reply_text("No ads available at the moment.")

# Register handlers
application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('approve_or_reject_withdrawal', approve_or_reject_withdrawal))  # Approve/Reject Withdrawal
# Register valid commands with proper names.
# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CommandHandler("claim_bonus", claim_bonus))
application.add_handler(CommandHandler("watch_ads", watch_ads))
application.add_handler(CommandHandler("claim_task", claim_task))
application.add_handler(MessageHandler(filters.PHOTO, submit_task))  # Handle screenshot submissions
application.add_handler(CommandHandler("invite", invite))
application.add_handler(CommandHandler("withdraw", withdraw))
application.add_handler(CommandHandler("process_withdraw", process_withdraw))
application.add_handler(CommandHandler("support", support))


# Start the bot
application.run_polling()
