# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
import os
import json
import datetime
import asyncio
from threading import Thread
from flask import Flask

# ---------------------------
# GLOBAL CONFIGURATION
# ---------------------------
V2_APPS_LIST = ["bilibili", "hotstar", "vpn"] 
COOLDOWN_HOURS = 168 
TEMP_ROLE_DURATION_HOURS = 3 
TEMP_ROLE_DURATION_SECONDS = TEMP_ROLE_DURATION_HOURS * 3600

# Ticket operational hours (2:00 PM IST to 11:59 PM IST)
IST_OFFSET = datetime.timedelta(hours=5, minutes=30)
TICKET_START_HOUR_IST = 14  
TICKET_END_HOUR_IST = 24    

TICKET_CREATION_STATUS = True 
V1_REQUIRED_KEYWORDS = ["RASH", "TECH", "SUBSCRIBED"] 
BYPASS_HOURS_ACTIVE = False 

# New Category Map for the Dropdown 
APP_CATEGORIES = {
    "Streaming & Entertainment": ["spotify", "youtube", "hotstar", "bilibili"],
    "Productivity & Tools": ["kinemaster", "truecaller", "castle"],
    "Security & VPN": ["vpn"],
}

# ---------------------------
# Environment Variables (CRITICAL IDs)
# ---------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
try:
    GUILD_ID = int(os.getenv("GUILD_ID"))
    TICKET_LOG_CHANNEL_ID = int(os.getenv("TICKET_LOG_CHANNEL_ID"))
    VERIFICATION_CHANNEL_ID = int(os.getenv("VERIFICATION_CHANNEL_ID"))
    
    TICKET_PANEL_CHANNEL_ID = os.getenv("TICKET_PANEL_CHANNEL_ID")
    if TICKET_PANEL_CHANNEL_ID:
        TICKET_PANEL_CHANNEL_ID = int(TICKET_PANEL_CHANNEL_ID)

    ADMIN_PANEL_CHANNEL_ID = os.getenv("ADMIN_PANEL_CHANNEL_ID")
    if ADMIN_PANEL_CHANNEL_ID:
        ADMIN_PANEL_CHANNEL_ID = int(ADMIN_PANEL_CHANNEL_ID)

    INSTRUCTIONS_CHANNEL_ID = os.getenv("INSTRUCTIONS_CHANNEL_ID")
    if INSTRUCTIONS_CHANNEL_ID:
        INSTRUCTIONS_CHANNEL_ID = int(INSTRUCTIONS_CHANNEL_ID)
        
    ACTIVATION_CATEGORY_ID = int(os.getenv("ACTIVATION_CATEGORY_ID")) 
    TEMP_ROLE_ID = int(os.getenv("TEMP_ROLE_ID"))
    FEEDBACK_CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID"))
    
except (TypeError, ValueError) as e:
    raise ValueError(f"Missing or invalid required environment variable ID: {e}. Check all IDs are set correctly as plain numbers.")

YOUTUBE_CHANNEL_URL = os.getenv("YOUTUBE_CHANNEL_URL")
if not YOUTUBE_CHANNEL_URL or not TOKEN:
    raise ValueError("DISCORD_TOKEN and YOUTUBE_CHANNEL_URL environment variables are required.")


# ---------------------------
# Load / Save Apps (JSON Database)
# ---------------------------
def load_apps():
    try:
        with open("apps.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        default_apps = {
            "spotify": "https://link-target.net/1438550/4r4pWdwOV2gK",
            "youtube": "https://example.com/youtube-download",
            "kinemaster": "https://link-center.net/1438550/dP4XtgqcsuU1",
            "hotstar": "https://final-link.com/hotstar-premium",
            "vpn": "https://final-link.com/vpn-premium", 
            "truecaller": "https://link-target.net/1438550/kvu1lPW7ZsKu",
            "bilibili": "https://final-link.com/bilibili-premium", 
            "castle": "https://final-link.com/castle-premium",
        }
        print("Warning: apps.json not found. Creating file with default data.")
        with open("apps.json", "w") as f:
            json.dump(default_apps, f, indent=4)
        return default_apps

def save_apps(apps):
    try:
        with open("apps.json", "w") as f:
            json.dump(apps, f, indent=4)
        print("DEBUG: Successfully saved apps.json.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to write to apps.json. Check hosting permissions: {e}")


# ---------------------------
# Load / Save V2 Links (New Data Source)
# ---------------------------
def load_v2_links():
    try:
        with open("v2_links.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: v2_links.json not found. Creating file with default data.")
        v2_site_url = "https://verification2-djde.onrender.com"
        default_v2 = {
            "bilibili": v2_site_url, 
            "hotstar": v2_site_url, 
            "vpn": v2_site_url, 
        }
        with open("v2_links.json", "w") as f:
            json.dump(default_v2, f, indent=4)
        return default_v2

v2_links = load_v2_links()
# ---------------------------

# ---------------------------
# GLOBAL HELPER: Utility Functions
# ---------------------------
def get_app_emoji(app_key: str) -> str:
    app_key = app_key.lower()
    emoji_map = {
        "bilibili": "🅱️", "spotify": "🎶", "youtube": "📺", "kinemaster": "✍️", 
        "hotstar": "⭐", "truecaller": "📞", "castle": "🏰", "netflix": "🎬",
        "hulu": "🍿", "vpn": "🛡️", "prime": "👑", "editor": "✏️",
        "music": "🎵", "streaming": "📡", "photo": "📸", "file": "📁",
    }
    if app_key in emoji_map: return emoji_map[app_key]
    for keyword, emoji in emoji_map.items():
        if keyword in app_key: return emoji
    return "✨"

def is_ticket_time_allowed() -> bool:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_ist = now_utc + IST_OFFSET
    current_hour_ist = now_ist.hour
    if TICKET_START_HOUR_IST <= current_hour_ist < TICKET_END_HOUR_IST:
        return True
    return False

# OCR FUNCTION (Placeholder)
async def check_v1_ocr(image_url: str) -> bool:
    return False 


# ---------------------------
# Flask Keepalive Server
# ---------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ---------------------------
# Bot Setup
# ---------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

cooldowns = {} 

# ---------------------------
# Helper Function for Transcripts
# ---------------------------
async def create_transcript(channel: discord.abc.GuildChannel) -> tuple[list[str], list[discord.Message]]:
    messages = [msg async for msg in channel.history(limit=None)]
    messages.reverse() 

    transcript_chunks = []
    current = ""

    for msg in messages:
        line = f"[{msg.created_at.replace(tzinfo=datetime.timezone.utc):%Y-%m-%d %H:%M:%S}] {msg.author.display_name} ({msg.author.id}): {msg.content}\n"
        for a in msg.attachments:
            line += f"📎 ATTACHMENT: {a.url}\n"

        if len(current) + len(line) > 4000:
            transcript_chunks.append(current)
            current = ""

        current += line + "\n"

    if current:
        transcript_chunks.append(current)
        
    return transcript_chunks, messages


# ---------------------------
# CORE HELPER: Cooldown Lock Release
# ---------------------------
async def release_cooldown_lock(member: discord.Member):
    cooldown_end = cooldowns.get(member.id)
    if not cooldown_end: return
        
    wait_time = (cooldown_end - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    
    if wait_time > 0: await asyncio.sleep(wait_time)
        
    if member.id in cooldowns and cooldowns[member.id] <= datetime.datetime.now(datetime.timezone.utc):
        del cooldowns[member.id]
        
        activation_category = bot.get_channel(ACTIVATION_CATEGORY_ID)
        if activation_category and isinstance(activation_category, discord.CategoryChannel):
            await activation_category.set_permissions(member, read_messages=True, view_channel=True)
            try:
                await member.send("✅ Your 168-hour access cooldown has expired. You can now create a new ticket.")
            except discord.Forbidden:
                pass

# ---------------------------
# CORE HELPER: Role Removal
# ---------------------------
async def remove_temp_role(member: discord.Member, role: discord.Role):
    await asyncio.sleep(TEMP_ROLE_DURATION_SECONDS)
    try:
        if role and role in member.roles: await member.remove_roles(role)
    except Exception as e:
        print(f"Error removing temp role from {member.display_name}: {e}")


# ---------------------------
# CORE TICKET CLOSURE LOGIC
# ---------------------------
async def perform_ticket_closure(channel: discord.abc.GuildChannel, closer: discord.User, apply_cooldown: bool = False):
    
    log_channel = bot.get_channel(TICKET_LOG_CHANNEL_ID)
    messages = [msg async for msg in channel.history(limit=1, oldest_first=True)]
    ticket_opener = messages[0].author if messages and messages[0].author != bot.user else closer
    member = channel.guild.get_member(ticket_opener.id)
    
    transcript_parts, all_messages = await create_transcript(channel)

    # --- Logging Metadata ---
    open_time = messages[0].created_at if messages else datetime.datetime.now(datetime.timezone.utc)
    close_time = datetime.datetime.now(datetime.timezone.utc)
    duration = close_time - open_time
    duration_str = str(duration).split('.')[0] 

    metadata_embed = discord.Embed(
        title=f"📜 TICKET TRANSCRIPT LOG — {channel.name}", description=f"Transcript for the ticket **{channel.name}** attached.", color=discord.Color.red()
    )
    metadata_embed.add_field(name="Ticket Opener", value=ticket_opener.mention, inline=True)
    metadata_embed.add_field(name="Ticket Closer", value=closer.mention, inline=True)
    metadata_embed.add_field(name="Ticket Duration", value=duration_str, inline=False)
    await log_channel.send(embed=metadata_embed)

    for i, part in enumerate(transcript_parts):
        embed = discord.Embed(title=f"📄 Transcript Data — Part {i+1}", description=part, color=discord.Color.blurple())
        await log_channel.send(embed=embed)
    
    # ⚡ NEW FEATURE: Apply Cooldown, Role, and Category Lock ⚡
    if apply_cooldown and member:
        now = datetime.datetime.now(datetime.timezone.utc)
        cooldowns[member.id] = now + datetime.timedelta(hours=COOLDOWN_HOURS)
        
        temp_role = channel.guild.get_role(TEMP_ROLE_ID)
        if temp_role: await member.add_roles(temp_role)
        
        activation_category = bot.get_channel(ACTIVATION_CATEGORY_ID)
        if activation_category and isinstance(activation_category, discord.CategoryChannel):
            await activation_category.set_permissions(member, read_messages=False, view_channel=False)

        log_message = f"✅ User {member.mention} processed: Cooldown set for {COOLDOWN_HOURS}h, Temp Role '{temp_role.name if temp_role else 'N/A'}' applied for {TEMP_ROLE_DURATION_HOURS}h."
        await log_channel.send(log_message)
            
        bot.loop.create_task(release_cooldown_lock(member))
        if temp_role: bot.loop.create_task(remove_temp_role(member, temp_role))


    # Delete Channel/Archive Thread
    if isinstance(channel, discord.Thread):
         await channel.edit(archived=True, locked=True)
         await log_channel.send(f"✅ Ticket thread **{channel.name}** archived/locked.")
    else:
        await channel.delete()
        await log_channel.send(f"✅ Ticket channel **{channel.name}** deleted.")


# ---------------------------
# CORE TICKET LINK DELIVERY LOGIC 
# ---------------------------
async def deliver_and_close(channel: discord.abc.Messageable, user: discord.Member, app_key: str):
    
    apps = load_apps()
    app_link = apps.get(app_key)
    app_name_display = app_key.title()

    if not app_link:
        return await channel.send("❌ Error: Final link not found. Please contact an admin.")
    
    # --- STYLIZED DM MESSAGE CONTENT ---
    guild = bot.get_guild(GUILD_ID)
    feedback_channel = guild.get_channel(FEEDBACK_CHANNEL_ID) if guild else None
    support_channel_mention = "#support" 
    feedback_mention = feedback_channel.mention if feedback_channel else "#feedback-channel"
    temp_role_name = guild.get_role(TEMP_ROLE_ID).name if guild and guild.get_role(TEMP_ROLE_ID) else "Limited Access"

    dm_message = (
        "──────✮<a:Star:1315046783990239325>✮──────\n"
        f"### 🎉 Enjoy your **{app_name_display}** Premium Access! <:Hug:1315198669439504465>\n"
        f"### Don't forget to leave a quick review in {feedback_mention}\n"
        "──────✮<a:Star:1315046783990239325>✮──────\n"
        "### Thank you, and have a wonderful day ahead! <:Hii:1315042464893112410><a:Spark:1315201119068229692>\n"
        "──────✮<a:Star:1315046783990239325>✮──────\n"
        f"## P.S. You will receive a temporary **{TEMP_ROLE_DURATION_HOURS}-hour {temp_role_name}** role, which will be removed automatically. You can request another app once the **{COOLDOWN_HOURS}-hour cooldown** is removed.\n"
        f"If you encounter any problems, please visit {support_channel_mention} for help."
    )
    
    embed = discord.Embed(
        title="✅ Verification Approved! Access Granted!",
        description=f"Congratulations, {user.mention}! Your verification for **{app_name_display}** is complete.\n\n"
                    f"➡️ **[CLICK HERE FOR YOUR PREMIUM APP LINK]({app_link})** ⬅️\n\n",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    await channel.send(embed=embed)
    
    try:
        await user.send(dm_message) 
        await user.send(embed=embed) 
    except discord.Forbidden:
        pass 

    # Final closure prompt
    await channel.send(
        embed=discord.Embed(
            title="🎉 Service Completed — Time to Close!",
            description="Please close the ticket using the button below. This action will apply your cooldown and category lock.",
            color=discord.Color.green(),
        ),
        view=CloseTicketView(user) 
    )

# ---------------------------
# CORE HELPER: Thread Auto-Archival
# ---------------------------
async def archive_thread_after_delay(thread: discord.Thread):
    await asyncio.sleep(600) 
    if not thread.archived:
        await thread.send(
            embed=discord.Embed(
                description="⏳ This ticket thread has been automatically archived due to 10 minutes of inactivity. Access denied.",
                color=discord.Color.orange()
            )
        )
        try:
            await perform_ticket_closure(thread, bot.user, apply_cooldown=False) 
        except discord.Forbidden:
            print(f"Warning: Failed to auto-archive thread {thread.name}. Missing permissions.")


# ---------------------------
# CORE TICKET CREATION LOGIC (Centralized)
# ---------------------------
async def create_ticket_from_selection(interaction: discord.Interaction, app_key: str):
    """Handles creating the thread after the user selects a specific app."""
    global TICKET_CREATION_STATUS, BYPASS_HOURS_ACTIVE
    user = interaction.user
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # --- 1. STATUS CHECKS (Should pass if button/dropdown was visible, but check cooldown) ---
    is_time_allowed = is_ticket_time_allowed() or BYPASS_HOURS_ACTIVE
    if not TICKET_CREATION_STATUS or not is_time_allowed:
        # Should not happen if the dropdown was enabled, but safety check.
        reason = "System is closed."
        closed_embed = discord.Embed(title="Ticket System Offline 💥", description=reason, color=discord.Color.red())
        return await interaction.followup.send(embed=closed_embed, ephemeral=True)
    
    # 2. Check Cooldown/Category Lock 
    activation_category = bot.get_channel(ACTIVATION_CATEGORY_ID)
    if activation_category and isinstance(activation_category, discord.CategoryChannel):
        permissions = activation_category.permissions_for(user)
        if not permissions.view_channel:
            cooldown_end = cooldowns.get(user.id)
            time_left_str = str(cooldown_end - now).split('.')[0] if cooldown_end and cooldown_end > now else "N/A"
            closed_embed_cooldown = discord.Embed(
                title="⏳ Access Restricted - Cooldown Active", description=f"Remaining time: **`{time_left_str}`**.", color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=closed_embed_cooldown, ephemeral=True)
    
    if user.id in cooldowns and cooldowns[user.id] > now:
        remaining = cooldowns[user.id] - now
        time_left_str = str(remaining).split('.')[0] 
        closed_embed_cooldown = discord.Embed(title="⏳ Cooldown Active - Please Wait", description=f"Next ticket in: **`{time_left_str}`**", color=discord.Color.orange())
        return await interaction.followup.send(embed=closed_embed_cooldown, ephemeral=True)
    
    # 3. Check for existing active thread (FIXED: Use interaction.channel.guild)
    thread_name_prefix = f"ticket-{user.id}"
    
    # Iterate through all threads in the channel's guild
    existing_thread = discord.utils.get(
        interaction.channel.guild.threads, # Use GUILD threads, NOT channel threads
        name=thread_name_prefix,
        archived=False
    )
    
    if existing_thread:
         return await interaction.followup.send(
            embed=discord.Embed(title="⚠️ Existing Ticket Found", description=f"You already have an active ticket thread: {existing_thread.mention}", color=discord.Color.orange()),
            ephemeral=True
        )

    # 4. Create Thread
    try:
        # Use the channel where the dropdown was clicked to create the thread
        thread = await interaction.channel.create_thread(
            name=thread_name_prefix, type=discord.ChannelType.public_thread, auto_archive_duration=60 
        )
    except discord.Forbidden as e:
        print(f"ERROR: Bot lacks permission to create thread in channel {interaction.channel.name}: {e}")
        return await interaction.followup.send("❌ Error: I lack permissions to create a thread.", ephemeral=True)
    
    bot.loop.create_task(archive_thread_after_delay(thread))
    
    # 5. Send Instructions (Welcome Message)
    app_name_display = app_key.title()
    app_emoji = get_app_emoji(app_key)
    is_v2_app = app_key in V2_APPS_LIST
    
    if is_v2_app:
        v2_link = v2_links.get(app_key)
        embed = discord.Embed(title=f"{app_emoji} 2-STEP VERIFICATION REQUIRED: {app_name_display} 🔒", description=f"You have selected **{app_name_display}**.", color=discord.Color.from_rgb(255, 165, 0))
        embed.add_field(name="➡️ STEP 1: INITIAL SUBSCRIPTION PROOF (V1)", value=f"1. Subscribe: **[Click Here]({YOUTUBE_CHANNEL_URL})**\n2. Post **screenshot** and type **`RASH TECH`**.", inline=False)
        embed.add_field(name="➡️ STEP 2: FINAL KEY CHECK (V2)", value=f"After Step 1 approval, go to: **[Click Here]({v2_link})** and post screenshot with code.", inline=False)
    else:
        embed = discord.Embed(title=f"{app_emoji} 1-STEP VERIFICATION REQUIRED: {app_name_display}", description=f"You have selected **{app_name_display}**.", color=discord.Color.blue())
        embed.add_field(name="➡️ STEP 1: INITIAL SUBSCRIPTION PROOF (V1)", value=f"1. Subscribe: **[Click Here]({YOUTUBE_CHANNEL_URL})**\n2. Post **screenshot** and type **`RASH TECH`**.", inline=False)
    
    await thread.send(f"Welcome {user.mention}! Your selected app is **{app_name_display}**.", embed=embed)

    await interaction.followup.send(
        f"✅ Ticket thread created successfully for **{app_key.title()}**! Head over to {thread.mention} to continue.",
        ephemeral=True
    )
    

# ---------------------------
# VIEW CLASSES
# ---------------------------

# =============================
# TICKET CLOSURE VIEW
# =============================
class CloseTicketView(View):
    """View used for the final closure button in a ticket channel/thread."""
    def __init__(self, target_user: discord.Member = None):
        super().__init__(timeout=None) 
        self.target_user = target_user

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.red,
        emoji="🔒",
        custom_id="persistent_close_ticket_button" 
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_channel = interaction.channel
        
        if not target_channel.name.startswith("ticket-"):
             return await interaction.response.send_message(
                "❌ This is not a ticket channel or thread.", ephemeral=True
            )

        await interaction.response.send_message("Closing ticket and applying cooldown... ⏳", ephemeral=False)
        await perform_ticket_closure(target_channel, interaction.user, apply_cooldown=True)
        
# =============================
# CATEGORY SELECT VIEW (The main ticket panel view)
# =============================
class CategoryDropdown(Select):
    def __init__(self, categories):
        # Determine if the dropdown should be disabled
        is_system_open = is_ticket_time_allowed() or BYPASS_HOURS_ACTIVE
        
        options = []
        for category_name in categories.keys():
            options.append(
                discord.SelectOption(
                    label=category_name, 
                    value=category_name.replace(" ", "_").lower(),
                    description=f"Select an app from the {category_name} suite.",
                    emoji="🏷️"
                )
            )
        
        super().__init__(
            placeholder="🛒 Tap here to select your desired App Category...", 
            min_values=1, 
            max_values=1, 
            options=options,
            custom_id="category_select_dropdown",
            disabled=not is_system_open # DISABLE IF SYSTEM IS CLOSED
        )
        self.categories = categories
        self.is_open = is_system_open

    async def callback(self, interaction: discord.Interaction):
        if not self.is_open:
            return await interaction.response.send_message(
                f"❌ The ticket system is currently closed. It opens daily from {TICKET_START_HOUR_IST}:00 to {TICKET_END_HOUR_IST - 1}:59 IST.",
                ephemeral=True
            )
            
        await interaction.response.defer(ephemeral=True) 
        
        category_key = self.values[0]
        category_name = category_key.replace("_", " ").title()
        app_list = self.categories.get(category_name) 
        
        if not app_list:
            return await interaction.followup.send("❌ Error: App list for this category is empty or missing.", ephemeral=True)
            
        app_select_view = AppSelect(interaction.user, allowed_apps=app_list, parent_channel=interaction.channel)

        embed = discord.Embed(
            title=f"📦 {category_name} Selected",
            description="Please select the specific premium app you want access to from the list below.",
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed, view=app_select_view, ephemeral=True)


class CategorySelectView(View):
    def __init__(self):
        super().__init__(timeout=None) 
        self.add_item(CategoryDropdown(APP_CATEGORIES))


# =============================
# APP SELECT VIEW 
# =============================
class AppDropdown(Select):
    def __init__(self, options, user):
        super().__init__(
            placeholder="🛒 Tap here to select your desired Premium App...", 
            min_values=1, 
            max_values=1, 
            options=options,
            custom_id="app_select_dropdown"
        )
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        # Acknowledge immediately
        await interaction.response.defer() 
        
        app_key = self.values[0]
        app_name_display = app_key.title()
        
        # 1. Edit the message to show selection locked (used by interaction.message)
        await interaction.message.edit(
            content=f"**✅ Selection Locked: {app_name_display}**\n\nStarting ticket process...",
            embed=None,
            view=None
        )

        # 2. Trigger centralized ticket creation logic
        # Pass the channel where the interaction happened (TICKET_PANEL_CHANNEL)
        try:
            await create_ticket_from_selection(interaction, app_key)
        except Exception as e:
            print(f"Error during ticket creation (AppDropdown): {e}")
            await interaction.followup.send(f"❌ Failed to start ticket thread. Error: {e}", ephemeral=True)


class AppSelect(View):
    def __init__(self, user, allowed_apps=None, parent_channel=None):
        super().__init__(timeout=1800)
        self.parent_channel = parent_channel
        
        current_apps = load_apps()
        options = []
        apps_to_show = {k: v for k, v in current_apps.items() if allowed_apps is None or k in allowed_apps}
        
        for app_key in apps_to_show.keys():
            app_name_display = app_key.title()
            emoji = get_app_emoji(app_key)
            
            options.append(
                discord.SelectOption(
                    label=f"{app_name_display} — Instant Access", 
                    value=app_key,
                    description=f"Secure your link for {app_name_display} Premium features.",
                    emoji=emoji
                )
            )
        
        if options:
            self.add_item(AppDropdown(options, user))
        else:
            self.add_item(
                discord.ui.Button(label="No Apps Available in this Category", style=discord.ButtonStyle.grey, disabled=True)
            )


# =============================
# ADMIN STATUS & BYPASS PANEL
# =============================
class AdminStatusView(View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=300) 
        self.owner_id = owner_id
        
        if not is_ticket_time_allowed():
            self.add_item(self._create_bypass_button())

    def _create_bypass_button(self):
        global BYPASS_HOURS_ACTIVE
        
        button_style = discord.ButtonStyle.green if BYPASS_HOURS_ACTIVE else discord.ButtonStyle.red
        button_label = "Deactivate Bypass 🛑" if BYPASS_HOURS_ACTIVE else "Activate Bypass ✅"
        
        return discord.ui.Button(label=button_label, style=button_style, custom_id=f"admin_toggle_bypass")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
             await interaction.response.send_message("❌ You are not authorized to use the admin controls.", ephemeral=True)
             return False
        return True
        
    async def on_item_interaction(self, interaction: discord.Interaction, item: discord.ui.Item):
        if item.custom_id == "admin_toggle_bypass":
            await interaction.response.defer(ephemeral=True)
            await self._handle_bypass_toggle(interaction)

    @discord.ui.button(label="TOGGLE GLOBAL TICKET STATUS", style=discord.ButtonStyle.secondary, custom_id="admin_toggle_global_status")
    async def toggle_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global TICKET_CREATION_STATUS
        await interaction.response.defer()
        TICKET_CREATION_STATUS = not TICKET_CREATION_STATUS
        embed = self._create_status_embed()
        new_view = AdminStatusView(self.owner_id)
        await interaction.edit_original_response(embed=embed, view=new_view)
        
    @discord.ui.button(label="Refresh Panel", style=discord.ButtonStyle.blurple, custom_id="admin_refresh_status_panel")
    async def refresh_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = self._create_status_embed()
        new_view = AdminStatusView(self.owner_id)
        await interaction.edit_original_response(embed=embed, view=new_view)
    
    def _create_status_embed(self) -> discord.Embed:
        global BYPASS_HOURS_ACTIVE
        status_text = "ENABLED ✅" if TICKET_CREATION_STATUS else "DISABLED ❌"
        bypass_text = "ACTIVE (Ignoring Clock) 🟢" if BYPASS_HOURS_ACTIVE else "INACTIVE 🔴"
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_ist = now_utc + IST_OFFSET
        embed = discord.Embed(title="⚡ ADMIN STATUS PANEL (Testing Mode) ⚡", description=f"Current Time (IST): **{now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}**", color=discord.Color.blue())
        embed.add_field(name="Global Status", value=status_text, inline=True)
        embed.add_field(name="Hours Bypass", value=bypass_text, inline=True)
        embed.add_field(name="Operational Hours", value=f"{TICKET_START_HOUR_IST}:00 to {TICKET_END_HOUR_IST - 1}:59 IST", inline=False)
        if not is_ticket_time_allowed(): embed.set_footer(text="Bypass button available as time is outside normal operational hours.")
        return embed

    async def _handle_bypass_toggle(self, interaction: discord.Interaction):
        global BYPASS_HOURS_ACTIVE
        BYPASS_HOURS_ACTIVE = not BYPASS_HOURS_ACTIVE
        embed = self._create_status_embed()
        new_view = AdminStatusView(self.owner_id)
        await interaction.message.edit(embed=embed, view=new_view)
        await interaction.followup.send(f"Bypass toggled to: {'ACTIVE' if BYPASS_HOURS_ACTIVE else 'INACTIVE'}", ephemeral=True)


# =============================
# VERIFICATION ACTION VIEW
# =============================
class VerificationView(View):
    """View for Admins to Approve/Deny V1 (Subscription) Proof."""
    def __init__(self, ticket_channel: discord.abc.Messageable, user: discord.Member, app_key: str, screenshot_url: str):
        super().__init__(timeout=3600) 
        self.ticket_channel = ticket_channel
        self.user = user
        self.app_key = app_key
        self.screenshot_url = screenshot_url
        self.is_v2_app = app_key in V2_APPS_LIST

    @discord.ui.button(label="✅ Approve V1 Proof", style=discord.ButtonStyle.green, custom_id="verify_v1_approve")
    async def approve_v1_proof(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ You do not have permission to verify proofs.", ephemeral=True)

        await interaction.response.defer()
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.followup.send(f"✅ Approved by {interaction.user.mention}!", ephemeral=False)

        app_name_display = self.app_key.title()
        if self.is_v2_app:
            v2_link = v2_links.get(self.app_key, "Link not found.")
            embed_v2 = discord.Embed(title=f"✅ Step 1 Verified! Proceed to Final Step for {app_name_display}", description=f"➡️ **YOUR NEXT STEP (V2 Final Verification):**\n1. Go to: **[Click Here]({v2_link})**\n2. Post screenshot with code.", color=discord.Color.yellow())
            await self.ticket_channel.send(self.user.mention, embed=embed_v2)
        else:
            await deliver_and_close(self.ticket_channel, self.user, self.app_key)
            
        await self.ticket_channel.send(f"**— Verification Log —**\nV1 Proof Approved for **{app_name_display}** by {interaction.user.mention}.")

    @discord.ui.button(label="❌ Deny Proof", style=discord.ButtonStyle.grey, custom_id="verify_v1_deny")
    async def deny_v1_proof(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ You do not have permission to deny proofs.", ephemeral=True)
        
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        
        await self.ticket_channel.send(embed=discord.Embed(title="❌ Verification Proof Denied", description=f"Your submission for **{self.app_key.title()}** was denied by {interaction.user.mention}.", color=discord.Color.red()))
        await interaction.response.send_message(f"❌ Denied proof for {self.user.mention}.", ephemeral=True)
# =============================
# SLASH COMMANDS (ADMIN GROUP)
# =============================

@bot.tree.command(name="add_app", description="➕ Add a new premium app to the database")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def add_app(interaction: discord.Interaction, app_name: str, app_link: str):
    await interaction.response.defer(ephemeral=True)
    app_key = app_name.lower()
    current_apps = load_apps()
    current_apps[app_key] = app_link
    save_apps(current_apps)
    embed = discord.Embed(title="✅ App Successfully Added to Database", description=f"**{app_name.title()}** is now available.", color=discord.Color.green())
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="remove_app", description="➖ Remove an app from the database")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def remove_app(interaction: discord.Interaction, app_name: str):
    await interaction.response.defer(ephemeral=True)
    app_key = app_name.lower()
    current_apps = load_apps()
    if app_key not in current_apps:
        return await interaction.followup.send(embed=discord.Embed(title="❌ App Not Found", description=f"App **{app_name.title()}** not found.", color=discord.Color.red()), ephemeral=True)
    del current_apps[app_key]
    save_apps(current_apps)
    await interaction.followup.send(embed=discord.Embed(title="🗑️ App Permanently Removed", description=f"**{app_name.title()}** removed.", color=discord.Color.red()), ephemeral=True)

@bot.tree.command(name="view_apps", description="📋 View all applications and their links in the database")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def view_apps(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    current_apps = load_apps()
    if not current_apps: return await interaction.followup.send(embed=discord.Embed(title="⚠️ No Apps Found", description="`apps.json` is empty.", color=discord.Color.orange()), ephemeral=True)
    app_list_str = "\n".join(f"**{app_key.title()}**: [Link]({link})" for app_key, link in current_apps.items())
    embed = discord.Embed(title="📋 Current Premium Apps List", description=app_list_str, color=discord.Color.green())
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="remove_cooldown", description="🧹 Remove a user's ticket cooldown")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def remove_cooldown(interaction: discord.Interaction, user: discord.Member):
    global cooldowns
    await interaction.response.defer(ephemeral=True)
    cooldown_cleared = user.id in cooldowns
    if cooldown_cleared: del cooldowns[user.id]

    activation_category = bot.get_channel(ACTIVATION_CATEGORY_ID)
    if activation_category and isinstance(activation_category, discord.CategoryChannel): await activation_category.set_permissions(user, read_messages=True, view_channel=True)

    temp_role = interaction.guild.get_role(TEMP_ROLE_ID)
    role_cleared = temp_role and temp_role in user.roles
    if role_cleared: await user.remove_roles(temp_role)
        
    if cooldown_cleared or role_cleared:
        embed = discord.Embed(title="✅ Restriction Removed", description=f"Cooldown and category lock for {user.mention} cleared. 🔓", color=discord.Color.green())
    else:
        embed = discord.Embed(title="ℹ️ No Active Restriction Found", description=f"User {user.mention} has no active restriction.", color=discord.Color.blue())
    
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="force_close", description="🔒 Force close a specific ticket channel/thread (or current one)")
@app_commands.default_permissions(manage_channels=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(target="Optional: Specify a ticket channel/thread to close.")
async def force_close(interaction: discord.Interaction, target: discord.abc.GuildChannel = None): 
    target_channel = target or interaction.channel
    if not target_channel.name.startswith("ticket-"):
        return await interaction.response.send_message("❌ Not a ticket channel/thread.", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)
    await interaction.edit_original_response(content=f"Preparing to force close {target_channel.mention}...")
    await perform_ticket_closure(target_channel, interaction.user, apply_cooldown=False) 
    try:
        await interaction.followup.send(f"✅ Force close successful! {target_channel.name} is archived/deleted.", ephemeral=True)
    except:
        pass

@bot.tree.command(name="send_app", description="📤 Send a premium app link to a user's ticket (manual send)")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def send_app(interaction: discord.Interaction, app_name: str, user: discord.Member):
    app_key = app_name.lower() 
    apps = load_apps()
    if app_key not in apps: return await interaction.response.send_message(f"❌ App **{app_name.title()}** not found.", ephemeral=True)
    
    ticket_channel = discord.utils.get(interaction.guild.threads + interaction.guild.text_channels, name=f"ticket-{user.id}")
    if not ticket_channel or (isinstance(ticket_channel, discord.Thread) and ticket_channel.archived):
        return await interaction.response.send_message(f"❌ User has no open ticket named ticket-{user.id}.", ephemeral=True)

    await deliver_and_close(ticket_channel, user, app_key)
    await interaction.response.send_message("Link sent to the ticket and closure requested!", ephemeral=True)

@bot.tree.command(name="verify_v2_final", description="✅ Manually approve V2 proof and send the final link for 2-step apps.")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(app_name="The app key (e.g., bilibili, hotstar).", user="The user who opened the ticket.")
async def verify_v2_final(interaction: discord.Interaction, app_name: str, user: discord.Member):
    app_key = app_name.lower()
    if app_key not in V2_APPS_LIST:
        return await interaction.response.send_message(f"❌ App **{app_name.title()}** is not a 2-step app.", ephemeral=True)
    
    ticket_channel = discord.utils.get(interaction.guild.threads + interaction.guild.text_channels, name=f"ticket-{user.id}")
    if not ticket_channel or (isinstance(ticket_channel, discord.Thread) and ticket_channel.archived):
        return await interaction.response.send_message(f"❌ User has no open ticket named ticket-{user.id}.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True, thinking=True)
    await deliver_and_close(ticket_channel, user, app_key)
    await interaction.followup.send(f"✅ Final link for **{app_name.title()}** sent. Process complete!", ephemeral=True)

@bot.tree.command(name="view_tickets", description="📊 View number of currently open tickets/threads")
@app_commands.default_permissions(manage_channels=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_channels=True)
async def view_tickets(interaction: discord.Interaction):
    open_tickets = [c for c in interaction.guild.threads + interaction.guild.text_channels if c.name.startswith("ticket-") and not (isinstance(c, discord.Thread) and c.archived)]
    embed = discord.Embed(title="🎟️ Open Ticket Overview", description=f"Currently open tickets/threads: **{len(open_tickets)}**", color=discord.Color.blurple())
    if open_tickets:
        ticket_mentions = "\n".join(f"📌 {c.mention}" for c in open_tickets[:20])
        if len(open_tickets) > 20: ticket_mentions += f"\n...and {len(open_tickets) - 20} more."
        embed.add_field(name="Active Ticket Channels/Threads", value=ticket_mentions, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="refresh_panel", description="🔄 Deletes and resends the ticket creation panel.")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def refresh_panel(interaction: discord.Interaction):
    if not TICKET_PANEL_CHANNEL_ID: return await interaction.response.send_message("❌ Error: TICKET_PANEL_CHANNEL_ID is not configured.", ephemeral=True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    await setup_ticket_panel(force_resend=True)
    await interaction.followup.send("✅ Ticket panel refreshed and sent with the latest app list.", ephemeral=True)

@bot.tree.command(name="status", description="Owner: View ticket system status and toggle hours bypass.")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def status_command(interaction: discord.Interaction):
    app_info = await interaction.client.application_info()
    owner_id = app_info.owner.id
    if interaction.user.id != owner_id:
        return await interaction.response.send_message("❌ This command is reserved for the bot owner.", ephemeral=True)
    view_instance = AdminStatusView(owner_id)
    embed = view_instance._create_status_embed()
    await interaction.response.send_message(embed=embed, view=view_instance, ephemeral=True)


# =============================
# SLASH COMMANDS (USER/GENERAL GROUP)
# =============================

@bot.tree.command(name="ticket", description="🎟️ Create a support ticket thread")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket(interaction: discord.Interaction):
    # This command is now only for debugging, as the main flow uses dropdowns.
    # It routes through the core logic, but skips the app selection phase.
    await interaction.response.send_message("Please use the dropdown menu in the ticket panel channel to select an app.", ephemeral=True)


# =============================
# ON MESSAGE — SCREENSHOT + APP DETECTION
# =============================
@bot.event
async def on_message(message):
    if message.guild is None: return
    is_ticket = message.channel.name.startswith("ticket-")
    if message.author.bot or not is_ticket: return

    content_upper = message.content.upper()
    content_lower = message.content.lower()
    apps = load_apps()
    matched_app_key = next((key for key in apps if key in content_lower), None)
    has_attachment = bool(message.attachments)
    
    if matched_app_key and has_attachment:
        app_key = matched_app_key
        app_name_display = app_key.title()
        screenshot = message.attachments[0].url
        ver_channel = bot.get_channel(VERIFICATION_CHANNEL_ID)
        is_v2_app = app_key in V2_APPS_LIST
        ticket_destination = message.channel 

        # --- CHECK 1: V2 Final Screenshot Submission ---
        v2_key_word = f"{app_name_display.upper()} KEY" 
        is_v2_verified = v2_key_word in content_upper
        
        if is_v2_app and is_v2_verified:
            embed = discord.Embed(title=f"🎉 V2 Proof Received for {app_name_display}!", description=f"Final proof confirmed. Admin action required.", color=discord.Color.green())
            embed.set_image(url=screenshot)
            await ver_channel.send(embed=embed)
            await message.channel.send(embed=discord.Embed(title="✅ Upload Successful! Final Step Proof Received.", description="Proof sent to Admin. ⏳", color=discord.Color.blue()))
            return

        # --- CHECK 2: V1 Subscription Proof Submission ---
        is_rash_tech_verified = "RASH TECH" in content_upper
        if is_rash_tech_verified:
            embed = discord.Embed(title="📸 Verification Proof Received!", description=f"User {message.author.mention} submitted proof for **{app_name_display}**.", color=discord.Color.yellow())
            embed.set_image(url=screenshot)
            await ver_channel.send(embed=embed, view=VerificationView(ticket_destination, message.author, app_key, screenshot))
            await message.channel.send(embed=discord.Embed(title="✅ Upload Successful! 🎉", description="Please wait patiently while the **Owner/Admin** verifies your screenshot. ⏳", color=discord.Color.blue()))
            return
        
        # --- CHECK 3: Failed Keyword Check ---
        else:
            required_keywords = ["RASH TECH"]
            if is_v2_app: required_keywords.append(f"{app_name_display.upper()} KEY")
            required_keyword_str = ' or '.join(f"**`{kw}`**" for kw in required_keywords)
            embed = discord.Embed(title="⚠️ Security Check Failed: Keyword Missing", description=f"You must include the required security keyword ({required_keyword_str}) in your message.", color=discord.Color.red())
            return await message.channel.send(embed=embed)

    elif matched_app_key and not has_attachment:
         await message.channel.send(embed=discord.Embed(title="📷 Screenshot Required", description=f"You mentioned **{app_name_display}**. Please upload the screenshot along with the keyword.", color=discord.Color.orange()))
    
    await bot.process_commands(message)
    # ---------------------------
# STARTUP FUNCTIONS
# ---------------------------

async def setup_ticket_panel(force_resend=False):
    if not TICKET_PANEL_CHANNEL_ID: return

    channel = bot.get_channel(TICKET_PANEL_CHANNEL_ID)
    if not channel:
        print(f"ERROR: Could not find ticket panel channel with ID {TICKET_PANEL_CHANNEL_ID}")
        return

    # Check if the system is closed for the prompt
    is_open = is_ticket_time_allowed() or BYPASS_HOURS_ACTIVE
    
    panel_embed = discord.Embed(
        title="__Self-Serve Activation__",
        description=f"You can use this panel to activate automatically.\n\n"
                    f"✨ **System Status:** **{'OPEN ✅' if is_open else 'CLOSED ❌'}**\n"
                    f"**Premium Apps & Modded Tools (Spotify, Bilibili, VPN, etc.)**\n"
                    f"\u200b", 
        color=discord.Color.from_rgb(255, 100, 150)
    )
    
    panel_embed.add_field(
        name="\u200b", 
        value=f"* The system is active only during announced hours.\n"
              f"* **Time: {TICKET_START_HOUR_IST}:00 – {TICKET_END_HOUR_IST - 1}:59 IST**.\n"
              f"* If the status is **CLOSED**, the menu is disabled and will open in operational hours.",
        inline=False
    )
    
    panel_embed.add_field(
        name="<:guide:1315037431174529109> Before You Start", 
        value=f"* Read the <#{INSTRUCTIONS_CHANNEL_ID}> guide.\n"
              f"* Cooldown: **{COOLDOWN_HOURS} hours** between successful access requests.",
        inline=False
    )
    
    panel_embed.set_footer(text="Done reading? Select a category from the dropdown below to start. Check #support for help.")


    try:
        panel_message_found = False
        async for message in channel.history(limit=5):
            if message.author == bot.user and message.components:
                if message.components[0].children[0].custom_id == "category_select_dropdown":
                    if force_resend:
                        await message.delete()
                        break
                    else:
                        # If found and not forced, just edit the existing message to update status
                        await message.edit(embed=panel_embed, view=CategorySelectView())
                        print("Updated existing ticket panel.")
                        return
        
        # Send new message if not found or if forced to resend
        await channel.send(embed=panel_embed, view=CategorySelectView())
        print("Sent new persistent ticket panel.")

    except discord.Forbidden:
        print("ERROR: Missing permissions to read or send messages in the ticket panel channel.")
    except Exception as e:
        print(f"An unexpected error occurred during panel setup: {e}")


# =============================
# ON READY
# =============================
@bot.event
async def on_ready():
    app_info = await bot.application_info()
    bot.owner_id = app_info.owner.id
    
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

    bot.add_view(CloseTicketView())
    bot.add_view(CategorySelectView()) 
    
    await setup_ticket_panel()

    print(f"🟢 Bot logged in successfully as {bot.user}")


# =============================
# RUN BOT (Protected Initialization)
# =============================
if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(TOKEN)
