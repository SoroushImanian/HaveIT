from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from database import save_user_data, get_user_info, load_users_by_status, get_user_counts, ADMIN_IDS

async def admin_menu(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS: return

    counts = get_user_counts()

    text = (
        "📊 **Bot User Statistics**\n\n"
        f"✅ Active Users: **{counts['approved']}** 👤\n"
        f"⏳ Pending Requests: **{counts['pending']}** 👤\n"
        f"❌ Denied Users: **{counts['denied']}** 👤\n"
        f"🚫 Blocked Users: **{counts['blocked']}** 👤\n\n"
        "⚙️ **Management Panel:** Select a category below:"
    )

    kb = [
        [InlineKeyboardButton(f"📂 Active List ({counts['approved']})", callback_data="list_approved")],
        [InlineKeyboardButton(f"⏳ Pending List ({counts['pending']})", callback_data="list_pending")],
        [
            InlineKeyboardButton(f"❌ Denied ({counts['denied']})", callback_data="list_denied"),
            InlineKeyboardButton(f"🚫 Blocked ({counts['blocked']})", callback_data="list_blocked")
        ],
        [InlineKeyboardButton("🔙 Return to Main Menu", callback_data="main_menu")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def show_user_list(update: Update, context: CallbackContext, status):
    query = update.callback_query
    users = load_users_by_status(status)
    
    titles = {
        "approved": "✅ Active Users List (Approved)",
        "denied": "❌ Denied Users List",
        "blocked": "🚫 Blocked Users List",
        "pending": "⏳ Pending Requests List"
    }
    
    header_text = titles.get(status, f"📂 Status: {status}")

    if not users:
        await query.answer("📂 This list is empty!", show_alert=True)
        return

    kb = []
    for user in users:
        name = user.get('first_name', 'Unknown')
        uid = user['id']
        kb.append([InlineKeyboardButton(f"👤 {name} | 🆔 {uid}", callback_data=f"manage_user_{uid}")])
    
    kb.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_home")])
    
    await query.edit_message_text(f"**{header_text}**\n👇 Click on a user to manage:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def manage_single_user(update: Update, context: CallbackContext, target_id):
    user_data = get_user_info(target_id)
    if not user_data:
        await update.callback_query.answer("User not found.", show_alert=True)
        return

    text = (f"👤 **User Profile**\n\n"
            f"🆔 ID: `{user_data['id']}`\n"
            f"👤 Name: {user_data.get('first_name')} {user_data.get('last_name', '')}\n"
            f"🔗 Username: @{user_data.get('username', 'None')}\n"
            f"📝 Bio: {user_data.get('bio', 'N/A')}\n\n"
            "👇 Select an action:")

    kb = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"set_status_approved_{target_id}")],
        [InlineKeyboardButton("❌ Deny", callback_data=f"set_status_denied_{target_id}")],
        [InlineKeyboardButton("🚫 Block", callback_data=f"set_status_blocked_{target_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"admin_home")]
    ]
    
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def change_status(update: Update, context: CallbackContext):
    query = update.callback_query
    admin_who_clicked = query.from_user
    data = query.data
    parts = data.split('_')
    new_status = parts[2]
    target_id = int(parts[3])
    
    user_data = get_user_info(target_id)
    if user_data:
        save_user_data(user_data, new_status)
        
        try:
            if new_status == "approved":
                await context.bot.send_message(target_id, "✅ **Congratulations!**\nYour account has been approved. You can now use /start.")
            elif new_status == "denied":
                await context.bot.send_message(target_id, "❌ **Access Denied.**\nYour request was rejected by the admin.")
            elif new_status == "blocked":
                 await context.bot.send_message(target_id, "🚫 **Access Revoked.**\nYour account has been blocked by the administrator.")
        except: pass

        action_text = ""
        if new_status == "approved": action_text = "✅ Approved"
        elif new_status == "denied": action_text = "❌ Denied"
        elif new_status == "blocked": action_text = "🚫 Blocked"
        
        original_caption = query.message.caption if query.message.caption else query.message.text
        if "➖➖➖➖➖➖➖" in original_caption:
            original_caption = original_caption.split("➖➖➖➖➖➖➖")[0].strip()

        final_text = (f"{original_caption}\n\n"
                      f"➖➖➖➖➖➖➖\n"
                      f"**{action_text} by {admin_who_clicked.first_name}**")

        admin_msgs = user_data.get("admin_msgs", {})
        
        if admin_msgs:
            for admin_id_str, msg_id in admin_msgs.items():
                try:
                    await context.bot.edit_message_caption(
                        chat_id=int(admin_id_str),
                        message_id=int(msg_id),
                        caption=final_text,
                        reply_markup=None,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=int(admin_id_str),
                            message_id=int(msg_id),
                            text=final_text,
                            reply_markup=None,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except: pass
        else:
            try:
                if query.message.caption:
                    await query.edit_message_caption(caption=final_text, reply_markup=None, parse_mode=ParseMode.MARKDOWN)
                else:
                    await query.edit_message_text(text=final_text, reply_markup=None, parse_mode=ParseMode.MARKDOWN)
            except: pass
            
        await admin_menu(update, context)
            
    else:
        await query.answer("User data not found.", show_alert=True)
        await admin_menu(update, context)
