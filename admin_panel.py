from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from database import save_user_data, get_user_info, load_users_by_status, ADMIN_IDS

async def admin_menu(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS: return

    kb = [
        [InlineKeyboardButton("✅ Approved Users", callback_data="list_approved")],
        [InlineKeyboardButton("❌ Denied Users", callback_data="list_denied")],
        [InlineKeyboardButton("🚫 Blocked Users", callback_data="list_blocked")],
        [InlineKeyboardButton("⏳ Pending Requests", callback_data="list_pending")],
        [InlineKeyboardButton("🔙 Return to Main Menu", callback_data="main_menu")]
    ]
    
    text = "👤 **Admin Management Panel**\nSelect a category to manage:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def show_user_list(update: Update, context: CallbackContext, status):
    """Shows a list of users for a specific category."""
    query = update.callback_query
    users = load_users_by_status(status)
    
    if not users:
        await query.answer("List is empty!", show_alert=True)
        return

    kb = []
    for user in users:
        name = user.get('first_name', 'Unknown')
        uid = user['id']
        kb.append([InlineKeyboardButton(f"{name} ({uid})", callback_data=f"manage_user_{uid}")])
    
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="admin_home")])
    
    await query.edit_message_text(f"Users in status: **{status.upper()}**", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def manage_single_user(update: Update, context: CallbackContext, target_id):
    """Shows details for a specific user and allows changing status."""
    user_data = get_user_info(target_id)
    if not user_data:
        await update.callback_query.answer("User data not found.", show_alert=True)
        return

    text = (f"👤 **User Details**\n"
            f"🆔 ID: `{user_data['id']}`\n"
            f"👤 Name: {user_data.get('first_name')} {user_data.get('last_name', '')}\n"
            f"🔗 Username: @{user_data.get('username', 'None')}\n"
            f"📝 Bio: {user_data.get('bio', 'Not set')}")

    kb = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"set_status_approved_{target_id}")],
        [InlineKeyboardButton("❌ Deny", callback_data=f"set_status_denied_{target_id}")],
        [InlineKeyboardButton("🚫 Block", callback_data=f"set_status_blocked_{target_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_home")]
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
                await context.bot.send_message(target_id, "✅ **Access Granted!**\nYour account has been approved. You can now use /start.")
            elif new_status == "denied":
                await context.bot.send_message(target_id, "❌ **Access Denied.**\nYour request was rejected by the admin.")
        except: pass

        action_text = ""
        if new_status == "approved": action_text = "✅ Approved"
        elif new_status == "denied": action_text = "❌ Denied"
        elif new_status == "blocked": action_text = "🚫 Blocked"
        
        original_caption = query.message.caption if query.message.caption else query.message.text
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
            
    else:
        await query.answer("User data not found (Already processed).", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=None)