import discord
from discord.ext import commands
from discord import app_commands
import requests
import json
import os
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ================= LOGGING SETUP =================
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================= CONFIGURATION =================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROK_API_KEY = os.getenv('GROK_API_KEY')
JIRA_URL = os.getenv('JIRA_URL', 'https://jbfivem.atlassian.net')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', 'SCRUM')

# Supabase Configuration (sử dụng HTTP API thay vì library)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SUPABASE_API_URL = f"{SUPABASE_URL}/rest/v1" if SUPABASE_URL else None

# Validate required config
if not all([DISCORD_TOKEN, GROK_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    logger.error("❌ Thiếu cấu hình quan trọng. Vui lòng kiểm tra file .env")
    raise ValueError("Missing required environment variables")

logger.info("✅ Kết nối tới Supabase thành công (HTTP API)")

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

GROK_MODEL = "grok-3"  # Sử dụng model ổn định nhất
JIRA_API_URL = f"{JIRA_URL}/rest/api/3"

# ================= COLOR SCHEME =================
COLORS = {
    "Task": discord.Color.green(),
    "Bug": discord.Color.red(),
    "List": discord.Color.blue(),
    "Success": discord.Color.green(),
    "Error": discord.Color.red(),
    "Info": discord.Color.blue()
}

# ================= SUPABASE FUNCTIONS (HTTP API) =================
def get_user_jira_credentials(discord_id: str) -> Optional[tuple]:
    """
    Lấy Jira credentials từ Supabase cho user Discord (sử dụng HTTP API)
    Returns: (jira_email, jira_api_token) hoặc None nếu không tìm thấy
    """
    try:
        url = f"{SUPABASE_API_URL}/linked_users?discord_id=eq.{discord_id}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                user_data = data[0]
                return user_data["jira_email"], user_data["jira_api_token"]
        return None
    except Exception as e:
        logger.error(f"Lỗi lấy credentials từ Supabase: {str(e)}")
        return None


def save_user_jira_credentials(discord_id: str, discord_name: str, jira_email: str, jira_api_token: str) -> bool:
    """
    Lưu Jira credentials vào Supabase (upsert) - sử dụng HTTP API
    Returns: True nếu thành công, False nếu lỗi
    """
    try:
        url = f"{SUPABASE_API_URL}/linked_users"
        headers = {
            "apikey": SUPABASE_KEY,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        
        payload = {
            "discord_id": str(discord_id),
            "discord_name": discord_name,
            "jira_email": jira_email,
            "jira_api_token": jira_api_token,
            "linked_at": datetime.utcnow().isoformat()
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Lưu vào Supabase: {jira_email} (Discord: {discord_name})")
            return True
        else:
            logger.error(f"Supabase save error {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Lỗi lưu vào Supabase: {str(e)}")
        return False


def delete_user_jira_credentials(discord_id: str) -> bool:
    """
    Xóa Jira credentials khỏi Supabase - sử dụng HTTP API
    Returns: True nếu thành công, False nếu lỗi
    """
    try:
        url = f"{SUPABASE_API_URL}/linked_users?discord_id=eq.{discord_id}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.delete(url, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            logger.info(f"✅ Xóa khỏi Supabase: Discord ID {discord_id}")
            return True
        else:
            logger.error(f"Supabase delete error {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Lỗi xóa khỏi Supabase: {str(e)}")
        return False


# ================= GROK API FUNCTIONS =================
def ask_grok_to_parse_task(user_prompt: str) -> Optional[dict]:
    """
    Gửi yêu cầu của user qua Grok để bóc tách thành cấu trúc JSON của Jira
    Trả về: dict với keys: summary, description, issuetype, priority
    """
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """Bạn là trợ lý quản lý dự án chuyên nghiệp cho team phát triển FiveM Server (GTA V Roleplay) tại Việt Nam.

Nhiệm vụ của bạn: Phân tích yêu cầu của developer (bằng tiếng Việt) và chuyển thành thông tin task/bug để tạo trên Jira.

QUY TẮC BẮT BUỘC:
- CHỈ trả về DUY NHẤT một JSON object thuần túy.
- KHÔNG được thêm bất kỳ markdown nào (```json)
- Nếu user viết bằng tiếng Việt có lỗi chính tả nhẹ vẫn phải hiểu được.
- Ưu tiên phát hiện "Bug", "Lỗi", "Fix", "Crash" → issuetype = "Bug" và priority = "High".
- Các từ như "Tạo", "Thêm", "Xây dựng", "Implement" → issuetype = "Task".

JSON BẮT BUỘC PHẢI CÓ ĐÚNG 4 KEY SAU:
{
  "summary": "Tiêu đề ngắn gọn, rõ ràng, tối đa 100 ký tự, bằng tiếng Việt",
  "description": "Mô tả chi tiết bằng tiếng Việt. Có thể dùng \\n để xuống dòng. Nên thêm context nếu cần.",
  "issuetype": "Task" hoặc "Bug",
  "priority": "High" | "Medium" | "Low"
}"""
    
    data = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3
    }
    
    try:
        logger.info(f"Gửi request tới Grok: {user_prompt[:100]}...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            # Strip markdown if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            logger.info(f"Grok response: {content[:200]}...")
            parsed = json.loads(content)
            return parsed
        else:
            logger.error(f"Grok API Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception khi gọi Grok: {str(e)}")
        return None


# ================= JIRA API FUNCTIONS =================
def create_jira_issue(summary: str, description: str, issuetype: str, priority: str = "Medium", 
                     jira_email: str = None, jira_api_token: str = None) -> Optional[dict]:
    """
    Tạo issue trên Jira Cloud với description theo Atlassian Document Format
    Sử dụng credentials riêng của user nếu cấp, ngược lại dùng credentials toàn cục từ .env
    """
    # Nếu không cấp credentials, sử dụng từ .env
    if jira_email is None or jira_api_token is None:
        jira_email = os.getenv('JIRA_EMAIL')
        jira_api_token = os.getenv('JIRA_API_TOKEN')
    
    if not jira_email or not jira_api_token:
        logger.error("Không có Jira credentials khả dụng")
        return None
    
    url = f"{JIRA_API_URL}/issue"
    headers = {
        "Content-Type": "application/json"
    }
    auth = (jira_email, jira_api_token)
    
    # Cấu trúc ADF cho description
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": description}
                        ]
                    }
                ]
            },
            "issuetype": {"name": issuetype},
            "priority": {"name": priority}
        }
    }
    
    try:
        logger.info(f"Tạo issue: {summary}")
        response = requests.post(url, headers=headers, auth=auth, json=payload, timeout=15)
        
        if response.status_code == 201:
            result = response.json()
            logger.info(f"Issue created successfully: {result.get('key')}")
            return result
        else:
            logger.error(f"Jira API Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception khi tạo issue: {str(e)}")
        return None


def search_jira_issues(jql: str, max_results: int = 10, jira_email: str = None, jira_api_token: str = None) -> Optional[list]:
    """
    Tìm kiếm issues trên Jira theo JQL
    """
    if jira_email is None or jira_api_token is None:
        jira_email = os.getenv('JIRA_EMAIL')
        jira_api_token = os.getenv('JIRA_API_TOKEN')
    
    if not jira_email or not jira_api_token:
        return None
    
    url = f"{JIRA_API_URL}/search"
    headers = {"Content-Type": "application/json"}
    auth = (jira_email, jira_api_token)
    
    params = {
        "jql": jql,
        "maxResults": max_results,
        "fields": "key,summary,issuetype,priority,status,assignee,updated"
    }
    
    try:
        logger.info(f"Tìm kiếm JQL: {jql}")
        response = requests.get(url, headers=headers, auth=auth, params=params, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Tìm thấy {len(result.get('issues', []))} issues")
            return result.get('issues', [])
        else:
            logger.error(f"Jira Search Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception khi tìm kiếm: {str(e)}")
        return None


def add_jira_comment(issue_key: str, comment_text: str, jira_email: str = None, jira_api_token: str = None) -> Optional[dict]:
    """
    Thêm comment vào issue trên Jira
    """
    if jira_email is None or jira_api_token is None:
        jira_email = os.getenv('JIRA_EMAIL')
        jira_api_token = os.getenv('JIRA_API_TOKEN')
    
    if not jira_email or not jira_api_token:
        return None
    
    url = f"{JIRA_API_URL}/issue/{issue_key}/comments"
    headers = {"Content-Type": "application/json"}
    auth = (jira_email, jira_api_token)
    
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": comment_text}
                    ]
                }
            ]
        }
    }
    
    try:
        logger.info(f"Thêm comment vào {issue_key}")
        response = requests.post(url, headers=headers, auth=auth, json=payload, timeout=15)
        
        if response.status_code == 201:
            result = response.json()
            logger.info(f"Comment added to {issue_key}")
            return result
        else:
            logger.error(f"Jira Comment Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception khi thêm comment: {str(e)}")
        return None


# ================= EMBED TEMPLATES =================
def create_success_embed(title: str, issue_key: str, issue_url: str) -> discord.Embed:
    """Tạo embed cho task tạo thành công"""
    embed = discord.Embed(
        title="✅ Tạo Task Thành Công",
        description=title,
        color=COLORS["Success"]
    )
    embed.add_field(name="Issue Key", value=f"[{issue_key}]({issue_url})", inline=False)
    embed.add_field(name="Link", value=f"[Mở trên Jira]({issue_url})", inline=False)
    embed.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase", icon_url="https://pbs.twimg.com/profile_images/1445764532/grok_normal.jpeg")
    return embed


def create_error_embed(title: str, error_msg: str) -> discord.Embed:
    """Tạo embed cho lỗi"""
    embed = discord.Embed(
        title="❌ Lỗi",
        description=title,
        color=COLORS["Error"]
    )
    embed.add_field(name="Chi tiết", value=error_msg[:1024], inline=False)
    embed.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase")
    return embed


def create_issue_embed(issue: dict, show_url: bool = True) -> discord.Embed:
    """Tạo embed để hiển thị chi tiết issue"""
    issue_key = issue['key']
    fields = issue['fields']
    summary = fields['summary']
    issuetype = fields['issuetype']['name']
    priority = fields['priority']['name'] if fields.get('priority') else "N/A"
    status = fields['status']['name'] if fields.get('status') else "N/A"
    assignee = fields['assignee']['displayName'] if fields.get('assignee') else "Chưa assign"
    updated = fields['updated'][:10] if fields.get('updated') else "N/A"
    
    color = COLORS.get(issuetype, COLORS["Info"])
    
    embed = discord.Embed(
        title=f"{issue_key}: {summary}",
        color=color
    )
    embed.add_field(name="Loại", value=issuetype, inline=True)
    embed.add_field(name="Priority", value=priority, inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Assigned", value=assignee, inline=True)
    embed.add_field(name="Updated", value=updated, inline=True)
    
    if show_url:
        issue_url = f"{JIRA_URL}/browse/{issue_key}"
        embed.add_field(name="Link", value=f"[Mở trên Jira]({issue_url})", inline=False)
    
    embed.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase")
    return embed


def create_list_item(issue: dict) -> str:
    """Tạo item cho danh sách task"""
    fields = issue['fields']
    summary = fields['summary']
    issuetype = fields['issuetype']['name']
    priority = fields['priority']['name'] if fields.get('priority') else "Medium"
    status = fields['status']['name'] if fields.get('status') else "N/A"
    
    # Emoji cho status
    status_emoji = "🟢" if status == "Done" else "🟡" if status == "In Progress" else "⚪"
    
    return f"{status_emoji} **{summary}**\n📌 {issuetype} | 🎯 {priority} | 📊 {status}\n[Xem chi tiết]({JIRA_URL}/browse/{issue['key']})"


# ================= SLASH COMMANDS =================
@bot.tree.command(name="link_jira", description="Liên kết tài khoản Jira của bạn")
async def link_jira(interaction: discord.Interaction):
    """Command để link Jira credentials - /link_jira (gửi DM)"""
    await interaction.response.defer(thinking=True)
    
    try:
        # Gửi DM ask cho user
        embed_dm = discord.Embed(
            title="🔗 Liên Kết Jira",
            description="Sau đây tôi sẽ hỏi bạn 2 thứ:\n1. Email Jira\n2. API Token Jira",
            color=COLORS["Info"]
        )
        embed_dm.add_field(name="Cách lấy API Token", value="Vào https://id.atlassian.com/manage/api-tokens → Create API token", inline=False)
        embed_dm.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase")
        
        dm_channel = await interaction.user.create_dm()
        await dm_channel.send(embed=embed_dm)
        
        # Ask email
        email_embed = discord.Embed(
            title="📧 Email Jira",
            description="Nhập email Jira của bạn:",
            color=COLORS["Info"]
        )
        await dm_channel.send(embed=email_embed)
        
        # Wait for email
        def check_email(msg):
            return msg.author == interaction.user and msg.channel == dm_channel
        
        try:
            email_msg = await bot.wait_for('message', check=check_email, timeout=300)
            jira_email = email_msg.content.strip()
        except discord.ext.commands.CommandError:
            await dm_channel.send("❌ Timeout - vui lòng thử lại")
            await interaction.followup.send("❌ Timeout - vui lòng thử lại")
            return
        
        # Ask token
        token_embed = discord.Embed(
            title="🔑 API Token",
            description="Nhập API Token Jira của bạn:",
            color=COLORS["Info"]
        )
        await dm_channel.send(embed=token_embed)
        
        # Wait for token
        try:
            token_msg = await bot.wait_for('message', check=check_email, timeout=300)
            jira_api_token = token_msg.content.strip()
        except discord.ext.commands.CommandError:
            await dm_channel.send("❌ Timeout - vui lòng thử lại")
            await interaction.followup.send("❌ Timeout - vui lòng thử lại")
            return
        
        # Validate by calling Jira API
        test_url = f"{JIRA_URL}/rest/api/3/myself"
        test_response = requests.get(test_url, auth=(jira_email, jira_api_token), timeout=10)
        
        if test_response.status_code != 200:
            error_msg = "❌ Thông tin Jira không chính xác. Kiểm tra lại email/token"
            await dm_channel.send(error_msg)
            await interaction.followup.send(error_msg)
            logger.error(f"Jira validation failed for {interaction.user.name}: {test_response.status_code}")
            return
        
        # Save to Supabase
        success = save_user_jira_credentials(
            str(interaction.user.id),
            interaction.user.name,
            jira_email,
            jira_api_token
        )
        
        if success:
            success_msg = "✅ Liên kết Jira thành công! Bạn có thể dùng /my_tasks để xem task của bạn."
            await dm_channel.send(success_msg)
            await interaction.followup.send(success_msg)
        else:
            error_msg = "❌ Lỗi lưu vào Supabase. Vui lòng thử lại sau."
            await dm_channel.send(error_msg)
            await interaction.followup.send(error_msg)
            
    except Exception as e:
        logger.exception(f"Exception in link_jira: {str(e)}")
        error_embed = create_error_embed("Lỗi", str(e)[:500])
        await interaction.followup.send(embed=error_embed)


@bot.tree.command(name="unlink_jira", description="Hủy liên kết tài khoản Jira")
async def unlink_jira(interaction: discord.Interaction):
    """Command để unlink Jira credentials"""
    await interaction.response.defer(thinking=True)
    
    try:
        success = delete_user_jira_credentials(str(interaction.user.id))
        
        if success:
            embed = discord.Embed(
                title="✅ Hủy Liên Kết",
                description="Tài khoản Jira của bạn đã bị hủy liên kết thành công",
                color=COLORS["Success"]
            )
            embed.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase")
            await interaction.followup.send(embed=embed)
        else:
            embed = create_error_embed("Lỗi", "Không thể hủy liên kết. Vui lòng thử lại.")
            await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.exception(f"Exception in unlink_jira: {str(e)}")
        embed = create_error_embed("Lỗi", str(e)[:500])
        await interaction.followup.send(embed=embed)


@bot.tree.command(name="create_task", description="Tạo task mới từ prompt tiếng Việt")
@app_commands.describe(prompt="Mô tả task cần tạo (tiếng Việt)")
async def create_task(interaction: discord.Interaction, prompt: str):
    """Command để tạo task mới - /create_task <prompt>"""
    await interaction.response.defer(thinking=True)
    
    try:
        # Get user's Jira credentials from Supabase
        user_creds = get_user_jira_credentials(str(interaction.user.id))
        
        # Bước 1: Gửi sang Grok phân tích
        embed_processing = discord.Embed(
            title="🔄 Đang xử lý...",
            description="Grok đang phân tích yêu cầu của bạn",
            color=COLORS["Info"]
        )
        await interaction.followup.send(embed=embed_processing)
        
        parsed_data = ask_grok_to_parse_task(prompt)
        
        if not parsed_data:
            embed_error = create_error_embed(
                "Grok không thể phân tích",
                "Vui lòng kiểm tra prompt của bạn và thử lại. Prompt nên rõ ràng và bằng tiếng Việt."
            )
            await interaction.followup.send(embed=embed_error)
            return
        
        summary = parsed_data.get('summary', 'N/A')
        description = parsed_data.get('description', 'Không có mô tả')
        issuetype = parsed_data.get('issuetype', 'Task')
        priority = parsed_data.get('priority', 'Medium')
        
        # Bước 2: Tạo issue trên Jira
        if user_creds:
            jira_email, jira_api_token = user_creds
            jira_result = create_jira_issue(summary, description, issuetype, priority, jira_email, jira_api_token)
        else:
            jira_result = create_jira_issue(summary, description, issuetype, priority)
        
        if not jira_result:
            embed_error = create_error_embed(
                "Lỗi tạo issue trên Jira",
                "Kiểm tra lại credentials hoặc liên kết Jira bằng /link_jira"
            )
            await interaction.followup.send(embed=embed_error)
            return
        
        issue_key = jira_result.get('key')
        issue_url = f"{JIRA_URL}/browse/{issue_key}"
        
        # Trả về kết quả
        embed_success = create_success_embed(summary, issue_key, issue_url)
        await interaction.followup.send(embed=embed_success)
        logger.info(f"Task created by {interaction.user.name}: {issue_key}")
        
    except Exception as e:
        logger.exception(f"Exception in create_task: {str(e)}")
        embed_error = create_error_embed(
            "Lỗi không diễn tả được",
            f"Chi tiết: {str(e)[:500]}"
        )
        await interaction.followup.send(embed=embed_error)


@bot.tree.command(name="list_tasks", description="Xem danh sách task mới nhất")
@app_commands.describe(limit="Số lượng task hiển thị (mặc định 10)")
async def list_tasks(interaction: discord.Interaction, limit: int = 10):
    """Command để liệt kê task - /list_tasks [limit]"""
    await interaction.response.defer(thinking=True)
    
    try:
        # Get user's Jira credentials
        user_creds = get_user_jira_credentials(str(interaction.user.id))
        
        if user_creds:
            jira_email, jira_api_token = user_creds
        else:
            jira_email = None
            jira_api_token = None
        
        # Lấy task mới nhất từ project
        jql = f"project = {JIRA_PROJECT_KEY} ORDER BY updated DESC"
        issues = search_jira_issues(jql, max_results=min(limit, 20), jira_email=jira_email, jira_api_token=jira_api_token)
        
        if not issues:
            embed_empty = discord.Embed(
                title="📝 Danh sách Task",
                description="Không có task nào trong project hiện tại",
                color=COLORS["Info"]
            )
            embed_empty.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase")
            await interaction.followup.send(embed=embed_empty)
            return
        
        # Tạo embed chính
        embed_main = discord.Embed(
            title=f"📝 Danh sách {JIRA_PROJECT_KEY} ({len(issues)} task)",
            color=COLORS["List"]
        )
        
        for issue in issues[:limit]:
            embed_main.add_field(name=f"{issue['key']}", value=create_list_item(issue), inline=False)
        
        embed_main.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase")
        await interaction.followup.send(embed=embed_main)
        logger.info(f"Listed {len(issues)} tasks for {interaction.user.name}")
        
    except Exception as e:
        logger.exception(f"Exception in list_tasks: {str(e)}")
        embed_error = create_error_embed("Lỗi lấy danh sách task", str(e)[:500])
        await interaction.followup.send(embed=embed_error)


@bot.tree.command(name="add_comment", description="Thêm comment vào issue")
@app_commands.describe(
    issue_key="Mã task (ví dụ: SCRUM-123)",
    comment="Nội dung comment"
)
async def add_comment(interaction: discord.Interaction, issue_key: str, comment: str):
    """Command để thêm comment - /add_comment <issue_key> <comment>"""
    await interaction.response.defer(thinking=True)
    
    try:
        # Get user's Jira credentials
        user_creds = get_user_jira_credentials(str(interaction.user.id))
        
        if user_creds:
            jira_email, jira_api_token = user_creds
            result = add_jira_comment(issue_key, comment, jira_email, jira_api_token)
        else:
            result = add_jira_comment(issue_key, comment)
        
        if result:
            embed_success = discord.Embed(
                title="✅ Comment Added",
                description=f"Comment đã thêm vào [{issue_key}]({JIRA_URL}/browse/{issue_key})",
                color=COLORS["Success"]
            )
            embed_success.add_field(name="Nội dung", value=comment[:500], inline=False)
            embed_success.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase")
            await interaction.followup.send(embed=embed_success)
            logger.info(f"Comment added to {issue_key} by {interaction.user.name}")
        else:
            embed_error = create_error_embed(
                "Lỗi thêm comment",
                f"Kiểm tra xem issue {issue_key} có tồn tại không hoặc kiểm tra credentials"
            )
            await interaction.followup.send(embed=embed_error)
    except Exception as e:
        logger.exception(f"Exception in add_comment: {str(e)}")
        embed_error = create_error_embed("Lỗi", str(e)[:500])
        await interaction.followup.send(embed=embed_error)


@bot.tree.command(name="my_tasks", description="Xem task được assign cho bạn")
async def my_tasks(interaction: discord.Interaction):
    """Command để xem task được assign cho user"""
    await interaction.response.defer(thinking=True)
    
    try:
        # Get user's Jira credentials
        user_creds = get_user_jira_credentials(str(interaction.user.id))
        
        if not user_creds:
            embed_error = create_error_embed(
                "Chưa liên kết Jira",
                "Vui lòng dùng /link_jira để liên kết tài khoản Jira của bạn trước"
            )
            await interaction.followup.send(embed=embed_error)
            return
        
        jira_email, jira_api_token = user_creds
        
        # Lấy task assigned cho user
        jql = f"project = {JIRA_PROJECT_KEY} AND assignee = currentUser() ORDER BY updated DESC"
        issues = search_jira_issues(jql, max_results=20, jira_email=jira_email, jira_api_token=jira_api_token)
        
        if not issues:
            embed_empty = discord.Embed(
                title="📋 My Tasks",
                description=f"Không có task nào được assign cho bạn trong project {JIRA_PROJECT_KEY}",
                color=COLORS["Info"]
            )
            embed_empty.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase")
            await interaction.followup.send(embed=embed_empty)
            return
        
        # Tạo embed
        embed_main = discord.Embed(
            title=f"📋 My Tasks ({len(issues)} task)",
            color=COLORS["List"]
        )
        
        for issue in issues[:10]:
            embed_main.add_field(name=f"{issue['key']}", value=create_list_item(issue), inline=False)
        
        embed_main.set_footer(text="FiveM Server Bot • Powered by Grok 4.3 + Supabase")
        await interaction.followup.send(embed=embed_main)
        logger.info(f"Listed tasks for {interaction.user.name}")
        
    except Exception as e:
        logger.exception(f"Exception in my_tasks: {str(e)}")
        embed_error = create_error_embed("Lỗi lấy danh sách task", str(e)[:500])
        await interaction.followup.send(embed=embed_error)


@bot.tree.command(name="help", description="Xem hướng dẫn sử dụng bot")
async def help_command(interaction: discord.Interaction):
    """Command để hiển thị trợ giúp"""
    embed = discord.Embed(
        title="🤖 FiveM Discord Bot v3 - Hướng Dẫn Sử Dụng",
        color=COLORS["Info"]
    )
    
    embed.add_field(
        name="/link_jira",
        value="Liên kết tài khoản Jira của bạn (gửi DM)\nVí dụ: `/link_jira`",
        inline=False
    )
    
    embed.add_field(
        name="/unlink_jira",
        value="Hủy liên kết tài khoản Jira",
        inline=False
    )
    
    embed.add_field(
        name="/create_task <prompt>",
        value="Tạo task/bug mới từ mô tả tiếng Việt\nVí dụ: `/create_task Lỗi xe police spawn không hiện texture`",
        inline=False
    )
    
    embed.add_field(
        name="/list_tasks [limit]",
        value="Xem danh sách task mới nhất của project (mặc định 10)\nVí dụ: `/list_tasks 15`",
        inline=False
    )
    
    embed.add_field(
        name="/add_comment <issue_key> <comment>",
        value="Thêm comment vào task\nVí dụ: `/add_comment SCRUM-123 Đã fix ở branch feature/xyz`",
        inline=False
    )
    
    embed.add_field(
        name="/my_tasks",
        value="Xem tất cả task được assign cho bạn (cần link Jira trước)",
        inline=False
    )
    
    embed.add_field(
        name="/help",
        value="Hiển thị hướng dẫn này",
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value="• Dùng /link_jira để lưu credentials cá nhân trên Supabase\n"
              "• Prompt càng rõ ràng càng tốt\n"
              "• Bot tự động phát hiện Bug vs Task từ prompt\n"
              "• Credentials được mã hóa trên Supabase",
        inline=False
    )
    
    embed.set_footer(text="FiveM Server Bot v3 • Powered by Grok 4.3 + Supabase | Made with ❤️ for FiveM Team")
    await interaction.response.send_message(embed=embed)


# ================= BOT EVENTS =================
@bot.event
async def on_ready():
    """Khi bot sẵn sàng"""
    try:
        await bot.tree.sync()
        logger.info(f"✅ Bot {bot.user.name} đã sẵn sàng hoạt động!")
        logger.info(f"✅ Slash commands đã sync thành công")
        logger.info(f"📌 Project: {JIRA_PROJECT_KEY} | Grok Model: {GROK_MODEL}")
        logger.info(f"🗄️  Database: Supabase (PostgreSQL)")
    except Exception as e:
        logger.error(f"Lỗi khi sync commands: {str(e)}")


@bot.event
async def on_command_error(ctx, error):
    """Xử lý lỗi command"""
    logger.error(f"Command error: {str(error)}")
    await ctx.send(f"❌ Lỗi: {str(error)}")


# ================= MAIN =================
if __name__ == "__main__":
    logger.info("🚀 Khởi động Discord Bot v3 (Supabase Edition)...")
    logger.info(f"📊 Jira Project: {JIRA_PROJECT_KEY} ({JIRA_URL})")
    logger.info(f"🗄️  Database: {SUPABASE_URL}")
    
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"❌ Lỗi khởi động bot: {str(e)}")
