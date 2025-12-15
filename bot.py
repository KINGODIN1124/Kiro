# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
import os
import json
import datetime
import asyncio
from flask import Flask
from threading import Thread

# ---------------------------
# GLOBAL CONFIGURATION
# ---------------------------
V2_APPS_LIST = ["bilibili", "hotstar", "vpn"] 
COOLDOWN_HOURS = 168 # 7 days (Your requested cooldown)
TEMP_ROLE_DURATION_HOURS = 3 # Duration for the temporary role
TEMP_ROLE_DURATION_SECONDS = TEMP_ROLE_DURATION_HOURS * 3600

# Ticket operational hours (2:00 PM IST to 11:59 PM IST)
IST_OFFSET = datetime.timedelta(hours=5, minutes=30)
TICKET_START_HOUR_IST = 14  # 2:00 PM IST
TICKET_END_HOUR_IST = 24    # 11:59 PM IST (exclusive of midnight)

TICKET_CREATION_STATUS = True 
V1_REQUIRED_KEYWORDS = ["RASH", "TECH", "SUBSCRIBED"] 
BYPASS_HOURS_ACTIVE = False # Global flag for admin bypass

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
        
    # NEW REQUIRED IDs for the cooldown/role feature
    ACTIVATION_CATEGORY_ID = int(os.getenv("ACTIVATION_CATEGORY_ID")) 
    TEMP_ROLE_ID = int(os.getenv("TEMP_ROLE_ID"))
    FEEDBACK_CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID"))
    
except (TypeError, ValueError) as e:
    raise ValueError(f"Missing or invalid required environment variable ID: {e}. Check all IDs (GUILD_ID, TEMP_ROLE_ID, etc.) are set correctly as plain numbers.")

YOUTUBE_CHANNEL_URL = os.getenv("YOUTUBE_CHANNEL_URL")
if not YOUTUBE_CHANNEL_URL or not TOKEN:
    raise ValueError("DISCORD_TOKEN and YOUTUBE_CHANNEL_URL environment variables are required.")


# ---------------------------
# Load / Save Apps (JSON Database)
# ---------------------------
def load_apps():
    """Loads the app list (final links) from apps.json."""
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
    """Saves the app list to apps.json."""
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
    """Loads the V2 website links for the second verification step."""
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
    """Assigns an appropriate emoji based on the app key (lowercase)."""
    
    app_key = app_key.lower()
    
    emoji_map = {
        "bilibili": "🅱️", 
        "spotify": "🎶", 
        "youtube": "📺", 
        "kinemaster": "✍️", 
        "hotstar": "⭐",
        "truecaller": "📞", 
        "castle": "🏰",
        "netflix": "🎬",
        "hulu": "🍿",
        "vpn": "🛡️",
        "prime": "👑",
        "editor": "✏️",
        "music": "🎵",
        "streaming": "📡",
        "photo": "📸",
        "file": "📁",
    }
    
    if app_key in emoji_map:
        return emoji_map[app_key]
    
    for keyword, emoji in emoji_map.items():
        if keyword in app_key:
            return emoji

    return "✨"

def is_ticket_time_allowed() -> bool:
    """Checks if the current time is between 2:00 PM and 11:59 PM IST."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_ist = now_utc + IST_OFFSET
    current_hour_ist = now_ist.hour
    
    if TICKET_START_HOUR_IST <= current_hour_ist < TICKET_END_HOUR_IST:
        return True
    
    return False

# OCR FUNCTION (Placeholder for Google Cloud Vision API)
async def check_v1_ocr(image_url: str) -> bool:
    """
    NOTE: This is a placeholder. 
    You must implement the actual Google Vision API logic here.
    """
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
    """Fetches channel/thread history, splits into chunks, and returns messages list."""
    
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
    """Waits for the cooldown to expire and restores category view permissions."""
    
    cooldown_end = cooldowns.get(member.id)
    if not cooldown_end:
        return
        
    wait_time = (cooldown_end - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    
    if wait_time > 0:
        await asyncio.sleep(wait_time)
        
    # Ensure cooldown is truly over before clearing
    if member.id in cooldowns and cooldowns[member.id] <= datetime.datetime.now(datetime.timezone.utc):
        del cooldowns[member.id]
        
        activation_category = bot.get_channel(ACTIVATION_CATEGORY_ID)
        if activation_category and isinstance(activation_category, discord.CategoryChannel):
            await activation_category.set_permissions(
                member, 
                read_messages=True, 
                view_channel=True
            )
            # Notify user that cooldown is over (optional)
            try:
                await member.send("✅ Your 168-hour access cooldown has expired. You can now create a new ticket.")
            except discord.Forbidden:
                pass


# ---------------------------
# CORE HELPER: Role Removal
# ---------------------------
async def remove_temp_role(member: discord.Member, role: discord.Role):
    """Removes the temporary role after the defined duration."""
    await asyncio.sleep(TEMP_ROLE_DURATION_SECONDS)
    try:
        if role and role in member.roles:
            await member.remove_roles(role)
    except Exception as e:
        print(f"Error removing temp role from {member.display_name}: {e}")


# ---------------------------
# CORE TICKET CLOSURE LOGIC (UPDATED with Role/Cooldown)
# ---------------------------
async def perform_ticket_closure(channel: discord.abc.GuildChannel, closer: discord.User, apply_cooldown: bool = False):
    """Performs logging and final deletion/archiving of the channel/thread, with cooldown/role application."""
    
    log_channel = bot.get_channel(TICKET_LOG_CHANNEL_ID)
    
    # Determine the user who opened the ticket (often the first message author)
    messages = [msg async for msg in channel.history(limit=1, oldest_first=True)]
    ticket_opener = messages[0].author if messages and messages[0].author != bot.user else closer
    member = channel.guild.get_member(ticket_opener.id)
    
    transcript_parts, all_messages = await create_transcript(channel)

    # Get Ticket Metadata
    open_time = messages[0].created_at if messages else datetime.datetime.now(datetime.timezone.utc)
    close_time = datetime.datetime.now(datetime.timezone.utc)
    duration = close_time - open_time
    duration_str = str(duration).split('.')[0] 

    # Log Metadata (Single Embed)
    metadata_embed = discord.Embed(
        title=f"📜 TICKET TRANSCRIPT LOG — {channel.name}",
        description=f"Transcript for the ticket **{'thread' if isinstance(channel, discord.Thread) else 'channel'}** **{channel.name}** is attached below.",
        color=discord.Color.red()
    )
    metadata_embed.add_field(name="Ticket Opener", value=ticket_opener.mention, inline=True)
    metadata_embed.add_field(name="Ticket Closer", value=closer.mention, inline=True)
    metadata_embed.add_field(name="\u200b", value="\u200b", inline=True)
    
    metadata_embed.add_field(name="Time Opened", value=f"{open_time.strftime('%Y-%m-%d %H:%M:%S UTC')}", inline=False)
    metadata_embed.add_field(name="Time Closed", value=f"{close_time.strftime('%Y-%m-%d %H:%M:%S UTC')}", inline=False)
    metadata_embed.add_field(name="Ticket Duration", value=duration_str, inline=False)

    await log_channel.send(embed=metadata_embed)

    # Log Transcript Parts
    for i, part in enumerate(transcript_parts):
        embed = discord.Embed(
            title=f"📄 Transcript Data — Part {i+1}",
            description=part,
            color=discord.Color.blurple()
        )
        await log_channel.send(embed=embed)
    
    # ⚡ NEW FEATURE: Apply Cooldown, Role, and Category Lock ⚡
    if apply_cooldown and member:
        now = datetime.datetime.now(datetime.timezone.utc)
        cooldowns[member.id] = now + datetime.timedelta(hours=COOLDOWN_HOURS)
        
        # 1. Apply Temporary Role
        temp_role = channel.guild.get_role(TEMP_ROLE_ID)
        if temp_role:
            await member.add_roles(temp_role)
        
        # 2. Lock User out of Activation Category (Apply permission DENY)
        activation_category = bot.get_channel(ACTIVATION_CATEGORY_ID)
        if activation_category and isinstance(activation_category, discord.CategoryChannel):
            await activation_category.set_permissions(
                member, 
                read_messages=False, 
                view_channel=False
            )

        # 3. Send log and set cooldown/role release tasks
        log_message = f"✅ User {member.mention} processed: Cooldown set for {COOLDOWN_HOURS}h, Temp Role '{temp_role.name if temp_role else 'N/A'}' applied for {TEMP_ROLE_DURATION_HOURS}h."
        await log_channel.send(log_message)
            
        # Task to re-enable category access after cooldown (168 hours)
        bot.loop.create_task(release_cooldown_lock(member))

        # Task to remove temporary role (3 hours)
        if temp_role:
             bot.loop.create_task(remove_temp_role(member, temp_role))


    # Delete Channel/Archive Thread (CRITICAL STEP)
    if isinstance(channel, discord.Thread):
         await channel.edit(archived=True, locked=True)
         await log_channel.send(f"✅ Ticket thread **{channel.name}** archived/locked.")
    else:
        await channel.delete()
        await log_channel.send(f"✅ Ticket channel **{channel.name}** deleted.")


# ---------------------------
# CORE TICKET LINK DELIVERY LOGIC (Shared)
# ---------------------------
async def deliver_and_close(channel: discord.abc.Messageable, user: discord.Member, app_key: str):
    """Delivers the final app link and initiates the ticket closure prompt."""
    
    apps = load_apps()
    app_link = apps.get(app_key)
    app_name_display = app_key.title()

    if not app_link:
        return await channel.send("❌ Error: Final link not found. Please contact an admin.")
    
    # --- STYLIZED DM MESSAGE CONTENT ---
    
    # Get required channel objects for mentions
    guild = bot.get_guild(GUILD_ID)
    feedback_channel = guild.get_channel(FEEDBACK_CHANNEL_ID) if guild else None
    
    # Assuming a general support channel is needed
    support_channel_mention = "#support" 
    if feedback_channel:
        # Using the feedback channel for general review/support link if no dedicated support channel ID is provided
        feedback_mention = feedback_channel.mention 
    else:
        feedback_mention = "#feedback-channel"
        
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
    
    # Embed for the App Link
    embed = discord.Embed(
        title="✅ Verification Approved! Access Granted!",
        description=f"Congratulations, {user.mention}! Your verification for **{app_name_display}** is complete.\n\n"
                    f"➡️ **[CLICK HERE FOR YOUR PREMIUM APP LINK]({app_link})** ⬅️\n\n",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    await channel.send(embed=embed)
    
    try:
        # Send stylized DM and link embed
        await user.send(dm_message) 
        await user.send(embed=embed) 
    except discord.Forbidden:
        pass # Ignore if DMs are closed

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
    """Archives the thread after a 10-minute delay."""
    
    # Wait for 10 minutes (600 seconds)
    await asyncio.sleep(600) 

    # Check if the thread is still active and not already closed by an action
    if not thread.archived:
        await thread.send(
            embed=discord.Embed(
                description="⏳ This ticket thread has been automatically archived due to 10 minutes of inactivity. Access denied.",
                color=discord.Color.orange()
            )
        )
        try:
            # For inactivity, we do NOT apply cooldown/role
            await perform_ticket_closure(thread, bot.user, apply_cooldown=False) 
        except discord.Forbidden:
            print(f"Warning: Failed to auto-archive thread {thread.name}. Missing permissions.")


# ---------------------------
# CORE TICKET LOGIC (Shared by /ticket and Button) - NOW CREATES A THREAD
# ---------------------------
async def create_new_ticket(interaction: discord.Interaction):
    """Handles the shared logic of checking status, cooldown, creating a THREAD, and sending welcome message."""
    global TICKET_CREATION_STATUS, BYPASS_HOURS_ACTIVE
    user = interaction.user
    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Check Global Status and Operational Hours
    is_time_allowed = is_ticket_time_allowed() or BYPASS_HOURS_ACTIVE
    
    if not TICKET_CREATION_STATUS or not is_time_allowed:
        
        reason = "System is currently closed for maintenance."
        if not TICKET_CREATION_STATUS:
             reason = "System is currently closed for maintenance."
        elif not is_ticket_time_allowed():
             reason = f"System is outside of operational hours (Daily: {TICKET_START_HOUR_IST}:00 to {TICKET_END_HOUR_IST - 1}:59 IST)."
        
        closed_embed = discord.Embed(
            title="Ticket System Offline 💥",
            description=reason,
            color=discord.Color.red()
        )
        
        # 🛑 FIX 1: Use interaction.followup.send() since deferral is handled by the calling function
        return await interaction.followup.send(
            embed=closed_embed, 
            ephemeral=True
        )

    # 2. Check Cooldown/Category Lock (Primary check)
    activation_category = bot.get_channel(ACTIVATION_CATEGORY_ID)
    if activation_category and isinstance(activation_category, discord.CategoryChannel):
        permissions = activation_category.permissions_for(user)
        if not permissions.view_channel:
            cooldown_end = cooldowns.get(user.id)
            time_left_str = str(cooldown_end - now).split('.')[0] if cooldown_end and cooldown_end > now else "N/A"
            
            closed_embed_cooldown = discord.Embed(
                title="⏳ Access Restricted - Cooldown Active",
                description=f"You recently received access and are currently under a security cooldown.\n"
                            f"Remaining time: **`{time_left_str}`**.\n"
                            f"Please wait until the restriction is automatically removed.",
                color=discord.Color.orange()
            )
            
            # 🛑 FIX 2: Use interaction.followup.send()
            return await interaction.followup.send(
                embed=closed_embed_cooldown,
                ephemeral=True
            )
    
    # 3. Check Cooldown (Backup for users not in the category list)
    if user.id in cooldowns and cooldowns[user.id] > now:
        remaining = cooldowns[user.id] - now
        time_left_str = str(remaining).split('.')[0] 
        
        closed_embed_cooldown = discord.Embed(
            title="⏳ Cooldown Active - Please Wait",
            description=f"You recently opened a ticket. You can open your next ticket in:\n"
                        f"**`{time_left_str}`**",
            color=discord.Color.orange()
        )
        
        # 🛑 FIX 3: Use interaction.followup.send()
        return await interaction.followup.send(
            embed=closed_embed_cooldown,
            ephemeral=True
        )
    
    # All checks passed, proceed with thread creation (deferral done in calling function)
    
    # Check if the user already has an active thread/ticket
    thread_name_prefix = f"ticket-{user.id}"
    
    active_threads = [t for t in interaction.channel.threads if not t.archived]
    existing_thread = discord.utils.get(active_threads, name=thread_name_prefix)
    
    if existing_thread:
        # 🛑 FIX 4: Use interaction.followup.send()
         return await interaction.followup.send(
            embed=discord.Embed(
                title="⚠️ Existing Ticket Found",
                description=f"You already have an active ticket thread: {existing_thread.mention}",
                color=discord.Color.orange()
            ),
            ephemeral=True
        )

    # 4. Create Thread
    try:
        thread = await interaction.channel.create_thread(
            name=thread_name_prefix,
            type=discord.ChannelType.public_thread,
            auto_archive_duration=60 
        )
    except discord.Forbidden as e:
        print(f"ERROR: Bot lacks permission to create thread in channel {interaction.channel.name}: {e}")
        # 🛑 FIX 5: Use interaction.followup.send()
        return await interaction.followup.send(
            "❌ Error: I lack necessary permissions to create a ticket thread in this channel. (Check 'Create Public Threads').", 
            ephemeral=True
        )
    
    # Set the 10-minute auto-archival timer
    bot.loop.create_task(archive_thread_after_delay(thread))
    
    channel = thread 

    # --- ENHANCED STYLISH WELCOME MESSAGE ---
    embed = discord.Embed(
        title="🌟 Welcome to the Premium Access Ticket Center! 🚀",
        description=f"Hello {user.mention}! Thank free for choosing our services. We are here to provide you with quick access to premium content. \n\n"
                    "**Please read the information below before proceeding.**",
        color=discord.Color.from_rgb(50, 200, 255)
    )

    if INSTRUCTIONS_CHANNEL_ID:
        embed.add_field(
            name="🔴 IMPORTANT: READ BEFORE PROCEEDING",
            value=f"Before selecting an app, you **MUST** go to {bot.get_channel(INSTRUCTIONS_CHANNEL_ID).mention} and follow the initial setup steps. Failure to comply will result in denial.",
            inline=False
        )
    
    embed.add_field(
        name="1️⃣ Server Benefits & Guarantee",
        value="We specialize in providing verified links to the best premium apps. All our links are regularly checked and guaranteed to work upon successful verification.",
        inline=False
    )
    
    two_step_message = "Depending on the app selected, you will either receive your link immediately after verification OR be directed to a short second security step."
    
    embed.add_field(
        name="2️⃣ How to Get Your App Link (1 or 2 Steps)",
        value=f"1. **Select the app** you want from the dropdown menu below.\n"
              f"2. Follow the verification steps (subscribing/screenshotting).\n"
              f"3. **Complete the final step** (1-step apps receive link now, 2-step apps require a short final security check).\n"
              f"**{two_step_message}**",
        inline=False
    )
    
    embed.add_field(
        name="3️⃣ Rules & Support",
        value="* **Be Polite:** Respect the staff members.\n"
              "* **No Spamming:** Only submit the required screenshot.\n"
              "* **Patience:** Verification takes time. Do not ping admins excessively.",
        inline=False
    )
    
    embed.set_footer(text="Your satisfaction is our priority! Select an app below to get started.")
    # --- END ENHANCED WELCOME MESSAGE ---


    await channel.send(f"Welcome {user.mention}! Please select an application below.", embed=embed, view=AppSelect(interaction.user))

    # 🛑 FIX 6: Use interaction.followup.send() for final successful response
    await interaction.followup.send(
        f"✅ Ticket thread created successfully! Head over to {thread.mention} to continue.",
        ephemeral=True
    )


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
        # Acknowledge interaction immediately (always defer inside callbacks)
        await interaction.response.defer() 
        
        app_key = self.values[0]
        app_name_display = app_key.title()
        app_emoji = get_app_emoji(app_key)
        
        is_v2_app = app_key in V2_APPS_LIST
        
        # --- LOCK THE SELECTION ---
        await interaction.message.edit(
            content=f"**✅ Selection Locked: {app_name_display}**\n\nSee the specific instructions below.",
            embed=None,
            view=None
        )
        # --------------------------

        # --- CONDITIONAL INSTRUCTION LOGIC ---
        if is_v2_app:
            v2_link = v2_links.get(app_key)
            
            if not v2_link:
                 embed_error = discord.Embed(
                    title="❌ Setup Error: V2 Link Missing",
                    description=f"Admin: V2 link for {app_name_display} is not configured in v2_links.json.", 
                    color=discord.Color.red()
                 )
                 return await interaction.followup.send(embed=embed_error, ephemeral=False)

            # V2 App: Detailed, specific instructions (V1 + V2 explained upfront)
            embed = discord.Embed(
                title=f"{app_emoji} 2-STEP VERIFICATION REQUIRED: {app_name_display} 🔒",
                description=f"You have selected **{app_name_display}**. This app requires two security steps. Please complete **Step 1** now.",
                color=discord.Color.from_rgb(255, 165, 0) # Orange/Gold
            )
            
            embed.add_field(
                name="➡️ STEP 1: INITIAL SUBSCRIPTION PROOF (V1)",
                value=f"1. Subscribe to our channel: **[Click Here]({YOUTUBE_CHANNEL_URL})**\n"
                      f"2. Take a clear **screenshot** of your subscription.\n"
                      f"3. **Post the screenshot** and type **`RASH TECH`** in the message.",
                inline=False
            )
            
            embed.add_field(
                name="➡️ STEP 2: FINAL KEY CHECK (V2)",
                value=f"This step is required **AFTER** Admin approves your Step 1 proof.\n"
                      f"1. Go to the final verification site: **[Click Here]({v2_link})**\n"
                      f"2. Download the file, find the secret code (e.g., **`{app_name_display} KEY`**).\n"
                      f"3. **Resubmit the screenshot** of the open file and type the exact code: **`{app_name_display} KEY: <code_here>`**.",
                inline=False
            )
        
        else:
            # Standard App: Brief, simple instructions (V1 only)
            embed = discord.Embed(
                title=f"{app_emoji} 1-STEP VERIFICATION REQUIRED: {app_name_display}",
                description=f"You have selected **{app_name_display}**. Please complete the single verification step below to receive your link.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="➡️ STEP 1: INITIAL SUBSCRIPTION PROOF (V1)",
                value=f"1. Subscribe to our channel: **[Click Here]({YOUTUBE_CHANNEL_URL})**\n"
                      f"2. Take a clear **screenshot** of your subscription.\n"
                      f"3. **Post the screenshot** and type **`RASH TECH`**. The bot will send your final link upon approval.",
                inline=False
            )
            
        await interaction.followup.send(embed=embed, ephemeral=False)


class AppSelect(View):
    def __init__(self, user):
        super().__init__(timeout=1800)
        
        current_apps = load_apps()
        
        options = []
        for app_key in current_apps.keys():
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
                discord.ui.Button(label="No Apps Available Yet", style=discord.ButtonStyle.grey, disabled=True)
            )

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
                "❌ This is not a ticket channel or thread.",
                ephemeral=True
            )

        # Acknowledge immediately
        await interaction.response.send_message(
            "Closing ticket and applying cooldown... ⏳", 
            ephemeral=False
        )
        
        # Pass apply_cooldown=True to trigger the full shutdown/cooldown logic
        # Use interaction.user as closer
        await perform_ticket_closure(target_channel, interaction.user, apply_cooldown=True)
        
# =============================
# CREATE TICKET BUTTON VIEW
# =============================
class TicketPanelButton(View):
    def __init__(self):
        super().__init__(timeout=None) 

    @discord.ui.button(
        label="Create New Ticket",
        style=discord.ButtonStyle.blurple,
        emoji="📩",
        custom_id="persistent_create_ticket_button" 
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 🛑 FIX 7: Acknowledge the interaction immediately with defer()
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            await create_new_ticket(interaction)
        except Exception as e:
            print(f"CRITICAL ERROR in Ticket Creation Button: {e}")
            # 🛑 FIX 8: Send the error as a FOLLOWUP message
            try:
                await interaction.followup.send(
                    "❌ An unexpected error occurred while processing your ticket request. Please notify an administrator.", 
                    ephemeral=True
                )
            except discord.Forbidden:
                 pass # Ignore if we can't send the followup


# =============================
# ADMIN STATUS & BYPASS PANEL
# =============================

class AdminStatusView(View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=300) # 5 minutes timeout
        self.owner_id = owner_id
        
        # Check if the bypass button should be included initially
        if not is_ticket_time_allowed():
            self.add_item(self._create_bypass_button())

    def _create_bypass_button(self):
        global BYPASS_HOURS_ACTIVE
        
        button_style = discord.ButtonStyle.green if BYPASS_HOURS_ACTIVE else discord.ButtonStyle.red
        button_label = "Deactivate Bypass 🛑" if BYPASS_HOURS_ACTIVE else "Activate Bypass ✅"
        
        return discord.ui.Button(
            label=button_label,
            style=button_style,
            custom_id=f"admin_toggle_bypass"
        )

    # ---------------------------
    # INTERACTION CALLBACKS
    # ---------------------------

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the owner (you) to use these controls
        if interaction.user.id != self.owner_id:
             await interaction.response.send_message("❌ You are not authorized to use the admin controls.", ephemeral=True)
             return False
        return True

    @discord.ui.button(label="TOGGLE GLOBAL TICKET STATUS", style=discord.ButtonStyle.secondary, custom_id="admin_toggle_global_status")
    async def toggle_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global TICKET_CREATION_STATUS
        TICKET_CREATION_STATUS = not TICKET_CREATION_STATUS
        
        embed = self._create_status_embed()
        
        # We need to recreate the view to correctly update the bypass button if time changes
        new_view = AdminStatusView(self.owner_id)
        
        await interaction.response.edit_message(embed=embed, view=new_view)
        
    @discord.ui.button(label="Refresh Panel", style=discord.ButtonStyle.blurple, custom_id="admin_refresh_status_panel")
    async def refresh_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self._create_status_embed()
        new_view = AdminStatusView(self.owner_id)
        await interaction.response.edit_message(embed=embed, view=new_view)

    async def on_button_interaction(self, interaction: discord.Interaction):
        if interaction.custom_id == "admin_toggle_bypass":
            await self._handle_bypass_toggle(interaction)
        # Note: toggle_status_button is handled by its decorator


    # ---------------------------
    # HELPER METHODS
    # ---------------------------
    
    def _create_status_embed(self) -> discord.Embed:
        status_text = "ENABLED ✅" if TICKET_CREATION_STATUS else "DISABLED ❌"
        bypass_text = "ACTIVE (Ignoring Clock) 🟢" if BYPASS_HOURS_ACTIVE else "INACTIVE 🔴"
        
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_ist = now_utc + IST_OFFSET
        
        embed = discord.Embed(
            title="⚡ ADMIN STATUS PANEL (Testing Mode) ⚡",
            description=f"Current Time (IST): **{now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Global Status", value=status_text, inline=True)
        embed.add_field(name="Hours Bypass", value=bypass_text, inline=True)
        embed.add_field(name="Operational Hours", value=f"{TICKET_START_HOUR_IST}:00 to {TICKET_END_HOUR_IST - 1}:59 IST", inline=False)
        
        if not is_ticket_time_allowed():
            embed.set_footer(text="Bypass button available as time is outside normal operational hours.")
            
        return embed

    async def _handle_bypass_toggle(self, interaction: discord.Interaction):
        global BYPASS_HOURS_ACTIVE
        
        BYPASS_HOURS_ACTIVE = not BYPASS_HOURS_ACTIVE
        
        embed = self._create_status_embed()
        # Recreate view to reflect the new state (the button label changes)
        new_view = AdminStatusView(self.owner_id)
        
        await interaction.response.edit_message(embed=embed, view=new_view)


# =============================
# VERIFICATION ACTION VIEW
# =============================
class VerificationView(View):
    """View for Admins to Approve/Deny V1 (Subscription) Proof."""
    def __init__(self, ticket_channel: discord.abc.Messageable, user: discord.Member, app_key: str, screenshot_url: str):
        super().__init__(timeout=3600) # 1 hour timeout
        self.ticket_channel = ticket_channel
        self.user = user
        self.app_key = app_key
        self.screenshot_url = screenshot_url
        self.is_v2_app = app_key in V2_APPS_LIST

    @discord.ui.button(
        label="✅ Approve V1 Proof",
        style=discord.ButtonStyle.green,
        custom_id="verify_v1_approve"
    )
    async def approve_v1_proof(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only allow users with manage_guild permission to approve
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ You do not have permission to verify proofs.", ephemeral=True)

        await interaction.response.defer()

        # Disable all buttons to prevent double-action
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        
        # Log the action in the verification channel
        await interaction.followup.send(f"✅ Approved by {interaction.user.mention}!", ephemeral=False)

        app_name_display = self.app_key.title()

        if self.is_v2_app:
            # 2-Step App: Instruct user to proceed to V2
            v2_link = v2_links.get(self.app_key, "Link not found.")
            
            embed_v2 = discord.Embed(
                title=f"✅ Step 1 Verified! Proceed to Final Step for {app_name_display}",
                description=f"Congratulations, {self.user.mention}! Your subscription proof has been verified by an admin (**{interaction.user.display_name}**).\n\n"
                            f"➡️ **YOUR NEXT STEP (V2 Final Verification):**\n"
                            f"1. Go to this final verification site: **[Click Here]({v2_link})**\n"
                            f"2. Download the file, find the secret code.\n"
                            f"3. Post the **screenshot of the file/code** in this chat and type the code (e.g., `{app_name_display.upper()} KEY: <code_here>`).",
                color=discord.Color.yellow()
            )
            await self.ticket_channel.send(self.user.mention, embed=embed_v2)

        else:
            # 1-Step App: Deliver the link and close
            await deliver_and_close(self.ticket_channel, self.user, self.app_key)
            
        await self.ticket_channel.send(
             f"**— Verification Log —**\n"
             f"V1 Proof Approved for **{app_name_display}** by {interaction.user.mention}."
        )


    @discord.ui.button(
        label="❌ Deny Proof",
        style=discord.ButtonStyle.grey,
        custom_id="verify_v1_deny"
    )
    async def deny_v1_proof(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ You do not have permission to deny proofs.", ephemeral=True)
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        
        # Notify user in the ticket
        await self.ticket_channel.send(
            embed=discord.Embed(
                title="❌ Verification Proof Denied",
                description=f"Your submission for **{self.app_key.title()}** was denied by {interaction.user.mention}. Please resubmit a clearer, valid screenshot with the required keyword.",
                color=discord.Color.red()
            )
        )
        await interaction.response.send_message(f"❌ Denied proof for {self.user.mention}.", ephemeral=True)

# =============================
# SLASH COMMANDS (ADMIN GROUP)
# =============================

# --- /add_app ---
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
    
    embed = discord.Embed(
        title="✅ App Successfully Added to Database",
        description=f"The application **{app_name.title()}** is now available for users to select.\n\n"
                    f"🔗 **Direct Link:** [Click Here]({app_link})",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


# --- /remove_app ---
@bot.tree.command(name="remove_app", description="➖ Remove an app from the database")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def remove_app(interaction: discord.Interaction, app_name: str):
    
    await interaction.response.defer(ephemeral=True)
    
    app_key = app_name.lower()
    
    current_apps = load_apps()
    
    if app_key not in current_apps:
        embed = discord.Embed(
            title="❌ App Not Found",
            description=f"App **{app_name.title()}** not found in the list.",
            color=discord.Color.red()
        )
        return await interaction.followup.send(embed=embed, ephemeral=True)
        
    del current_apps[app_key]
    save_apps(current_apps)
    
    embed = discord.Embed(
        title="🗑️ App Permanently Removed",
        description=f"The application **{app_name.title()}** has been successfully removed from the database and will no longer appear in the ticket dropdown.",
        color=discord.Color.red()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

# --- /view_apps ---
@bot.tree.command(name="view_apps", description="📋 View all applications and their links in the database")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def view_apps(interaction: discord.Interaction):
    
    await interaction.response.defer(ephemeral=True)
    
    current_apps = load_apps()
    
    if not current_apps:
        embed = discord.Embed(
            title="⚠️ No Apps Found",
            description="The `apps.json` file is empty. Use `/add_app` to populate the list.",
            color=discord.Color.orange()
        )
        return await interaction.followup.send(embed=embed, ephemeral=True)

    app_list_str = ""
    for app_key, link in current_apps.items():
        app_list_str += f"**{app_key.title()}**: [Link]({link})\n"

    embed = discord.Embed(
        title="📋 Current Premium Apps List",
        description="Below are all applications currently available in the ticket selection:",
        color=discord.Color.green()
    )
    embed.add_field(name="App Name & Link", value=app_list_str, inline=False)
    
    await interaction.followup.send(embed=embed, ephemeral=True)


# --- /remove_cooldown ---
@bot.tree.command(name="remove_cooldown", description="🧹 Remove a user's ticket cooldown")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def remove_cooldown(interaction: discord.Interaction, user: discord.Member):

    global cooldowns
    await interaction.response.defer(ephemeral=True)

    # Manual clear of cooldown data
    if user.id in cooldowns:
        del cooldowns[user.id]
        cooldown_cleared = True
    else:
        cooldown_cleared = False

    # Manual clear of category lock
    activation_category = bot.get_channel(ACTIVATION_CATEGORY_ID)
    if activation_category and isinstance(activation_category, discord.CategoryChannel):
        await activation_category.set_permissions(
            user, 
            read_messages=True, 
            view_channel=True
        )

    # Manual clear of temporary role
    temp_role = interaction.guild.get_role(TEMP_ROLE_ID)
    if temp_role and temp_role in user.roles:
        await user.remove_roles(temp_role)
        role_cleared = True
    else:
        role_cleared = False
        
    if cooldown_cleared or role_cleared:
        embed = discord.Embed(
            title="✅ Restriction Removed",
            description=f"The cooldown and category lock for {user.mention} have been manually cleared. They can create a new ticket immediately. 🔓",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="ℹ️ No Active Restriction Found",
            description=f"User {user.mention} currently has no active ticket cooldown or temporary role/lock.",
            color=discord.Color.blue()
        )
    
    await interaction.followup.send(embed=embed, ephemeral=True)


# --- /force_close ---
@bot.tree.command(name="force_close", description="🔒 Force close a specific ticket channel/thread (or current one)")
@app_commands.default_permissions(manage_channels=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(target="Optional: Specify a ticket channel/thread to close.")
async def force_close(interaction: discord.Interaction, target: discord.abc.GuildChannel = None): 

    target_channel = target or interaction.channel

    is_ticket = target_channel.name.startswith("ticket-")
    
    if not is_ticket:
        return await interaction.response.send_message(
            "❌ This command must be used inside a ticket thread/channel, or you must specify a valid ticket name.",
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True, thinking=True)
    
    await interaction.edit_original_response(content=f"Preparing to force close {target_channel.mention}...")

    # For force close, we do NOT apply the cooldown/role logic
    await perform_ticket_closure(target_channel, interaction.user, apply_cooldown=False) 
    
    try:
        await interaction.followup.send(f"✅ Force close successful! {target_channel.name} is archived/deleted.", ephemeral=True)
    except:
        pass


# --- /send_app --- 
@bot.tree.command(name="send_app", description="📤 Send a premium app link to a user's ticket (legacy/manual send)")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def send_app(interaction: discord.Interaction, app_name: str, user: discord.Member):

    app_key = app_name.lower() 
    app_name_display = app_key.title()

    apps = load_apps()

    if app_key not in apps:
        return await interaction.response.send_message(f"❌ App **{app_name_display}** not found in database.", ephemeral=True)

    link = apps[app_key]

    # Search for an active thread/channel belonging to the user
    ticket_channel = discord.utils.get(
        interaction.guild.threads + interaction.guild.text_channels,
        name=f"ticket-{user.id}"
    )

    if not ticket_channel or (isinstance(ticket_channel, discord.Thread) and ticket_channel.archived):
        return await interaction.response.send_message(
            f"❌ User has no open ticket named ticket-{user.id}.",
            ephemeral=True
        )

    # Deliver the link and prompt for closure (this will prompt the user to click the button)
    await deliver_and_close(ticket_channel, user, app_key)

    await interaction.response.send_message("Link sent to the ticket and closure requested!", ephemeral=True)


# --- /verify_v2_final ---
@bot.tree.command(name="verify_v2_final", description="✅ Manually approve V2 proof and send the final link for 2-step apps.")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(app_name="The app key (e.g., bilibili, hotstar).", user="The user who opened the ticket.")
async def verify_v2_final(interaction: discord.Interaction, app_name: str, user: discord.Member):

    app_key = app_name.lower()
    app_name_display = app_key.title()

    if app_key not in V2_APPS_LIST:
        return await interaction.response.send_message(
            f"❌ App **{app_name_display}** is a 1-step app or not configured for V2. Use `/send_app` if manual link delivery is needed.",
            ephemeral=True
        )

    # Search for an active thread/channel belonging to the user
    ticket_channel = discord.utils.get(
        interaction.guild.threads + interaction.guild.text_channels,
        name=f"ticket-{user.id}"
    )

    if not ticket_channel or (isinstance(ticket_channel, discord.Thread) and ticket_channel.archived):
        return await interaction.response.send_message(
            f"❌ User has no open ticket named ticket-{user.id}.",
            ephemeral=True
        )
    
    await interaction.response.defer(ephemeral=True, thinking=True)

    # Deliver the link and prompt for closure (this will prompt the user to click the button)
    await deliver_and_close(ticket_channel, user, app_key)

    await interaction.followup.send(f"✅ Final link for **{app_name_display}** sent to {user.mention} in {ticket_channel.mention}. Process complete!", ephemeral=True)


# --- /view_tickets ---
@bot.tree.command(name="view_tickets", description="📊 View number of currently open tickets/threads")
@app_commands.default_permissions(manage_channels=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_channels=True)
async def view_tickets(interaction: discord.Interaction):

    # Check both active threads and text channels
    open_tickets = [
        c for c in interaction.guild.threads + interaction.guild.text_channels
        if c.name.startswith("ticket-") and not (isinstance(c, discord.Thread) and c.archived)
    ]

    embed = discord.Embed(
        title="🎟️ Open Ticket Overview",
        description=f"Currently open tickets/threads: **{len(open_tickets)}**",
        color=discord.Color.blurple()
    )

    if open_tickets:
        ticket_mentions = "\n".join(f"📌 {c.mention}" for c in open_tickets[:20])
        if len(open_tickets) > 20:
             ticket_mentions += f"\n...and {len(open_tickets) - 20} more."
             
        embed.add_field(
            name="Active Ticket Channels/Threads",
            value=ticket_mentions,
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- /refresh_panel ---
@bot.tree.command(name="refresh_panel", description="🔄 Deletes and resends the ticket creation panel.")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_guild=True)
async def refresh_panel(interaction: discord.Interaction):
    
    if not TICKET_PANEL_CHANNEL_ID:
        return await interaction.response.send_message("❌ Error: TICKET_PANEL_CHANNEL_ID is not configured.", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)
    
    await setup_ticket_panel(force_resend=True)
    
    await interaction.followup.send("✅ Ticket panel refreshed and sent with the latest app list.", ephemeral=True)


# =============================
# SLASH COMMANDS (ADMIN STATUS)
# =============================

@bot.tree.command(name="status", description="Owner: View ticket system status and toggle hours bypass.")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def status_command(interaction: discord.Interaction):
    # CRITICAL: Only allow the bot owner to use this
    app_info = await interaction.client.application_info()
    owner_id = app_info.owner.id
    
    if interaction.user.id != owner_id:
        return await interaction.response.send_message("❌ This command is reserved for the bot owner.", ephemeral=True)
    
    # Instantiate the view to generate the correct initial state
    view_instance = AdminStatusView(owner_id)
    embed = view_instance._create_status_embed()
    
    await interaction.response.send_message(embed=embed, view=view_instance, ephemeral=True)


# =============================
# SLASH COMMANDS (USER/GENERAL GROUP)
# =============================

# --- /ticket ---
@bot.tree.command(name="ticket", description="🎟️ Create a support ticket thread")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket(interaction: discord.Interaction):
    # 🛑 FIX 9: Acknowledge the interaction immediately with defer()
    try:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await create_new_ticket(interaction)
    except Exception as e:
        print(f"CRITICAL ERROR in Ticket Creation Slash Command: {e}")
        # Send the error as a FOLLOWUP message
        await interaction.followup.send(
            "❌ An unexpected error occurred while processing your ticket request. Please notify an administrator.", 
            ephemeral=True
        )

# =============================
# ON MESSAGE — SCREENSHOT + APP DETECTION
# =============================
@bot.event
async def on_message(message):

    # 🛑 CRITICAL FIX: Ignore DMs and messages not from a guild
    if message.guild is None:
        return
        
    # Check if channel is a ticket thread or channel
    is_ticket = message.channel.name.startswith("ticket-")

    if message.author.bot or not is_ticket:
        return

    content_upper = message.content.upper()
    content_lower = message.content.lower()
    
    apps = load_apps()
    matched_app_key = next((key for key in apps if key in content_lower), None)
    has_attachment = bool(message.attachments)
    
    # We only proceed if an app key is mentioned AND an attachment exists
    if matched_app_key and has_attachment:
        
        app_key = matched_app_key
        app_name_display = app_key.title()
        screenshot = message.attachments[0].url
        ver_channel = bot.get_channel(VERIFICATION_CHANNEL_ID)
        is_v2_app = app_key in V2_APPS_LIST
        
        # The ticket channel/thread object
        ticket_destination = message.channel 

        # --- CHECK 1: V2 Final Screenshot Submission ---
        v2_key_word = f"{app_name_display.upper()} KEY" 
        is_v2_verified = v2_key_word in content_upper
        
        if is_v2_app and is_v2_verified:
            # SUCCESS PATH: V2 Proof Confirmed!
            
            embed = discord.Embed(
                title=f"🎉 V2 Proof Received for {app_name_display}!",
                description=f"Final proof confirmed by keyword check. The process is complete.\n\n"
                            f"✅ **Admin Action Required:** Review the attached screenshot and use the `/verify_v2_final app_name:{app_key} user:{message.author.mention}` command to send the final link.",
                color=discord.Color.green()
            )
            embed.set_image(url=screenshot)
            await ver_channel.send(embed=embed)
            
            await message.channel.send(
                embed=discord.Embed(
                    title="✅ Upload Successful! Final Step Proof Received.",
                    description="Thank you! The final verification proof has been forwarded to the Admin for review. You will receive your link shortly. ⏳",
                    color=discord.Color.blue()
                )
            )
            return

        # --- CHECK 2: V1 Subscription Proof Submission ---
        # Look for 'RASH TECH' keyword for V1 proof
        is_rash_tech_verified = "RASH TECH" in content_upper

        if is_rash_tech_verified:
            # V1 Proof is valid—forward to admin for manual button approval
            
            embed = discord.Embed(
                title="📸 Verification Proof Received!",
                description=f"User {message.author.mention} submitted proof for **{app_name_display}**.",
                color=discord.Color.yellow()
            )
            embed.set_image(url=screenshot)
            
            # Send the V1 verification panel with buttons
            await ver_channel.send(
                embed=embed,
                view=VerificationView(ticket_destination, message.author, app_key, screenshot)
            )
            
            # Give immediate user feedback
            await message.channel.send(
                embed=discord.Embed(
                    title="✅ Upload Successful! 🎉",
                    description="Thank you for providing proof! Please wait patiently while the **Owner/Admin** verifies your screenshot. Once verified, you will receive your app link here. ⏳",
                    color=discord.Color.blue()
                )
            )
            return
        
        # --- CHECK 3: Failed Keyword Check ---
        else:
            # Failed V1 (Security Keyword) check
            
            required_keywords = ["RASH TECH"]
            if is_v2_app:
                required_keywords.append(f"{app_name_display.upper()} KEY")
                
            required_keyword_str = ' or '.join(f"**`{kw}`**" for kw in required_keywords)

            embed = discord.Embed(
                title="⚠️ Security Check Failed: Keyword Missing",
                description=f"You must include the required security keyword ({required_keyword_str}) in your message along with the screenshot. This confirms you read the instructions.",
                color=discord.Color.red()
            )
            return await message.channel.send(embed=embed)


    # If app name was mentioned but no attachment was found
    elif matched_app_key and not has_attachment:
         await message.channel.send(
            embed=discord.Embed(
                title="📷 Screenshot Required",
                description=f"You mentioned **{app_name_display}**. Please ensure you upload the screenshot along with the keyword.",
                color=discord.Color.orange()
            )
        )
    
    await bot.process_commands(message)

# ---------------------------
# STARTUP FUNCTIONS
# ---------------------------

async def setup_ticket_panel(force_resend=False):
    """
    Finds or sends the persistent ticket creation button with the requested style,
    tailored for premium app access.
    """
    if not TICKET_PANEL_CHANNEL_ID:
        print("WARNING: TICKET_PANEL_CHANNEL_ID is not set. Skipping ticket panel setup.")
        return

    channel = bot.get_channel(TICKET_PANEL_CHANNEL_ID)
    if not channel:
        print(f"ERROR: Could not find ticket panel channel with ID {TICKET_PANEL_CHANNEL_ID}")
        return

    # UPDATED PANEL MESSAGE FOR AESTHETIC MATCH
    panel_embed = discord.Embed(
        title="__Self-Serve Activation__",
        description=f"You can use this panel to activate automatically.\n\n"
                    f"✨ **Today’s Featured Access**\n"
                    f"**Premium Apps & Modded Tools (Spotify, Bilibili, VPN, etc.)**\n"
                    f"\u200b", # Zero-width space for separation
        color=discord.Color.from_rgb(255, 100, 150) # Matching the aesthetic
    )
    
    # 1. Activation Time/Status Block 
    panel_embed.add_field(
        name="\u200b", # Blank name
        value=f"* The system is active only during announced hours.\n"
              f"* **Time: {TICKET_START_HOUR_IST}:00 – {TICKET_END_HOUR_IST - 1}:59 IST** (converted to your local time).\n"
              f"* This time is an estimate; fixed time is announced by Admins.\n"
              f"* If the button says **'DISABLED'**, please wait for the next open window.",
        inline=False
    )
    
    # 2. Before You Start Block
    panel_embed.add_field(
        name="<:guide:1315037431174529109> Before You Start", # Placeholder emoji
        value=f"* Read the <#{INSTRUCTIONS_CHANNEL_ID}> guide.\n"
              f"* Cooldown: **{COOLDOWN_HOURS} hours** between successful access requests.",
        inline=False
    )
    
    # 3. How to Request (Implied via the button)
    panel_embed.set_footer(text="Done reading? Click 'Create New Ticket' below to start. Check #support for help.")


    try:
        panel_message_found = False
        panel_message = None 

        async for message in channel.history(limit=5):
            if message.author == bot.user and message.components:
                # Check for the custom ID used by the button
                if message.components[0].children[0].custom_id == "persistent_create_ticket_button":
                    panel_message_found = True
                    panel_message = message
                    break
        
        if panel_message_found and force_resend:
            await panel_message.delete()
            panel_message_found = False
            print("Deleted old ticket panel message due to /refresh_panel command.")

        if not panel_message_found:
            await channel.send(embed=panel_embed, view=TicketPanelButton())
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
    # Fetch application info to get the owner ID for the /status command check
    app_info = await bot.application_info()
    bot.owner_id = app_info.owner.id
    
    # Sync slash commands
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

    # Register persistent views (important for buttons/dropdowns that survive bot restart)
    bot.add_view(CloseTicketView())
    bot.add_view(TicketPanelButton())
    
    # Setup initial panel messages
    await setup_ticket_panel()

    print(f"🟢 Bot logged in successfully as {bot.user}")


# =============================
# RUN BOT (Protected Initialization)
# =============================
if __name__ == "__main__":
    
    # 1. Start Flask thread (keeps the bot hosting service alive)
    Thread(target=run_flask).start()
    
    # 2. Start the Discord client
    bot.run(TOKEN)
