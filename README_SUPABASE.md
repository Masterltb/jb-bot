# 🗄️ FiveM Discord Bot v3 - Supabase Edition

**Hướng Dẫn Chi Tiết Chuyển Đổi từ SQLite sang Supabase (Free Tier)**

---

## 📋 Mục Lục

- [Tại Sao Supabase?](#tại-sao-supabase)
- [Setup Supabase (5 Phút)](#setup-supabase-5-phút)
- [Cài Đặt Bot v3](#cài-đặt-bot-v3)
- [Sử Dụng Các Lệnh](#sử-dụng-các-lệnh)
- [So Sánh v2 vs v3](#so-sánh-v2-vs-v3)
- [Troubleshooting](#troubleshooting)

---

## 🌟 Tại Sao Supabase?

| Tính Năng      | SQLite          | Supabase (Free)            |
| -------------- | --------------- | -------------------------- |
| 📁 Lưu Trữ     | File cục bộ     | Cloud PostgreSQL           |
| 🔐 Bảo Mật     | Chỉ server biết | Encrypted + RLS            |
| 🌐 Truy Cập    | 1 máy           | Nhiều máy / VPS            |
| 💾 Dung Lượng  | Tùy HDD         | 500MB miễn phí             |
| 🔄 Backup      | Manual          | Tự động hàng ngày          |
| 🚀 Scalability | Giới hạn        | Có thể upgrade dễ          |
| 💰 Chi Phí     | Free            | Free (100K requests/month) |

**Tóm tắt:** Supabase = SQLite trên Cloud + Security + Backup + Multi-device

---

## 🚀 Setup Supabase (5 Phút)

### Bước 1: Tạo Tài Khoản Supabase

1. Truy cập [supabase.com](https://supabase.com)
2. Click **"Start your project"** hoặc **"Sign up"**
3. Chọn **"Sign up with GitHub"** hoặc **"Sign up with Google"** (nhanh hơn)

### Bước 2: Tạo Project

1. Click **"New Project"**
2. Điền thông tin:
   - **Name**: `fivem-jira-bot` (hoặc tên bạn thích)
   - **Database Password**: Tạo password mạnh (VD: `Abc123!@#Xyz789`)
   - **Region**: **Southeast Asia (Singapore)** ← Khuyến khích (gần Việt Nam)
3. Click **"Create new project"**
4. **Chờ 2-3 phút** để project initialize

### Bước 3: Lấy Credentials

1. Khi project sẵn sàng, vào **Projects** → Chọn project vừa tạo
2. Vào tab **Settings** (biểu tượng ⚙️)
3. Click **"API"** ở sidebar trái
4. Sẽ thấy:
   ```
   Project URL: https://xxxxx.supabase.co
   Anon (public) key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```
5. **Copy cả hai** → Dán vào `.env`:
   ```env
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

### Bước 4: Tạo Table

1. Từ project, click **"SQL Editor"** hoặc **"Table Editor"** ở sidebar
2. Nếu dùng **Table Editor**:
   - Click **"New table"**
   - **Table name**: `linked_users`
   - Thêm columns (click **"Add column"**):

   | Column Name    | Type      | Default | Primary |
   | -------------- | --------- | ------- | ------- |
   | discord_id     | text      | -       | ✅      |
   | discord_name   | text      | -       | ❌      |
   | jira_email     | text      | -       | ❌      |
   | jira_api_token | text      | -       | ❌      |
   | linked_at      | timestamp | now()   | ❌      |
   - Click **"Save"**

Hoặc nếu dùng **SQL Editor**, chạy query này:

```sql
CREATE TABLE linked_users (
  discord_id TEXT PRIMARY KEY,
  discord_name TEXT,
  jira_email TEXT,
  jira_api_token TEXT,
  linked_at TIMESTAMP DEFAULT NOW()
);
```

### ✅ Xong! Supabase đã sẵn sàng

---

## 💻 Cài Đặt Bot v3

### Bước 1: Cài Dependencies

```bash
pip install -r requirements.txt
```

Hoặc cài riêng:

```bash
pip install discord.py>=2.4.0 python-dotenv requests supabase
```

### Bước 2: Điền `.env`

Mở file `.env` và điền đầy đủ:

```env
# Discord
DISCORD_TOKEN=YOUR_DISCORD_TOKEN

# Grok
GROK_API_KEY=YOUR_GROK_API_KEY

# Jira (Global - dùng cho /create_task nếu user không liên kết)
JIRA_URL=https://jbfivem.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=YOUR_JIRA_TOKEN
JIRA_PROJECT_KEY=SCRUM

# Supabase (Bắt buộc cho v3)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

LOG_LEVEL=INFO
```

### Bước 3: Chạy Bot v3

```bash
python bot_v3_supabase.py
```

Nếu thấy:

```
✅ Bot [name] đã sẵn sàng hoạt động!
✅ Slash commands đã sync thành công
🗄️ Database: Supabase (PostgreSQL)
```

→ **Bot đã chạy thành công!** 🎉

---

## 📖 Sử Dụng Các Lệnh

### 1️⃣ `/link_jira` - Liên Kết Tài Khoản Jira

```
Người dùng: /link_jira
Bot gửi DM:
  📧 Email Jira: <người dùng nhập email>
  🔑 API Token: <người dùng nhập token>
✅ Bot lưu vào Supabase
```

**Cách lấy API Token:**

- Vào [id.atlassian.com/manage/api-tokens](https://id.atlassian.com/manage/api-tokens)
- Click **"Create API token"**
- Copy token → Paste vào DM

### 2️⃣ `/create_task <prompt>`

Tạo task sử dụng Jira credentials của user (nếu linked) hoặc global credentials

**Ví dụ:**

```
/create_task Lỗi xe police spawn không hiện texture
```

### 3️⃣ `/list_tasks [limit]`

Liệt kê task mới nhất

```
/list_tasks 20
```

### 4️⃣ `/add_comment <issue_key> <comment>`

Thêm comment vào task

```
/add_comment SCRUM-123 Đã fix ở branch feature/xyz
```

### 5️⃣ `/my_tasks`

Xem task assigned cho bạn (yêu cầu `/link_jira` trước)

```
/my_tasks
```

### 6️⃣ `/unlink_jira`

Hủy liên kết Jira (xóa credentials khỏi Supabase)

```
/unlink_jira
```

### 7️⃣ `/help`

Xem hướng dẫn

```
/help
```

---

## ⚖️ So Sánh v2 vs v3

| Tính Năng                | v2 (SQLite)                 | v3 (Supabase)             |
| ------------------------ | --------------------------- | ------------------------- |
| Lưu Trữ                  | Cục bộ SQLite               | Cloud PostgreSQL          |
| Liên Kết Jira            | ❌ Không                    | ✅ Có (`/link_jira`)      |
| /my_tasks                | Chỉ dùng global credentials | Dùng personal credentials |
| Multi-device             | ❌                          | ✅                        |
| Backup                   | ❌ Manual                   | ✅ Tự động                |
| RLS (Row Level Security) | ❌                          | ✅ (Optional)             |

---

## 🐛 Troubleshooting

### ❌ Error: `Missing required environment variables`

**Nguyên nhân:** Thiếu `SUPABASE_URL` hoặc `SUPABASE_KEY`

**Fix:**

```bash
# Kiểm tra .env
cat .env

# Chắc chắn có dòng:
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### ❌ Error: `Lỗi kết nối Supabase`

**Nguyên nhân:** URL hoặc API Key sai, hoặc mạng bị block

**Fix:**

1. Kiểm tra lại **Project URL** và **Anon public key** từ Settings → API
2. Đảm bảo copy chính xác (không có dspace trước/sau)
3. Thử ping Supabase:

```python
python -c "from supabase import create_client; supabase = create_client('YOUR_URL', 'YOUR_KEY'); print(supabase)"
```

### ❌ Error: `relation "linked_users" does not exist`

**Nguyên nhân:** Table chưa tạo hoặc xóa nhầm

**Fix:**

1. Vào Supabase → **SQL Editor**
2. Chạy:

```sql
CREATE TABLE IF NOT EXISTS linked_users (
  discord_id TEXT PRIMARY KEY,
  discord_name TEXT,
  jira_email TEXT,
  jira_api_token TEXT,
  linked_at TIMESTAMP DEFAULT NOW()
);
```

### ⚠️ `/link_jira` timeout

**Nguyên nhân:** Bot không nhận được DM hoặc user không reply nhanh

**Fix:**

- Đảm bảo DM từ strangers **enabled** (Settings → Privacy & Safety)
- Thử lại command
- Timeout mặc định là **5 phút**

### ⚠️ Credentials được lưu nhưng `/my_tasks` vẫn lỗi

**Nguyên nhân:** Credentials sai hoặc account Jira không có project access

**Fix:**

```bash
# Test credentials manually
curl -u "email@company.com:TOKEN" https://your-instance.atlassian.net/rest/api/3/myself
```

Nếu lỗi 401 → Revoke token cũ, tạo token mới

### 🔍 Debug Mode

Để xem logs chi tiết:

```bash
# Trong .env, set:
LOG_LEVEL=DEBUG
```

Hoặc chỉnh trong code:

```python
logging.basicConfig(level=logging.DEBUG)
```

---

## 🔒 Security Best Practices

1. **KHÔNG share credentials:**
   - DISCORD_TOKEN
   - GROK_API_KEY
   - SUPABASE_KEY
   - JIRA_API_TOKEN

2. **Gitignore .env:**

```gitignore
.env
.env.local
```

3. **Rotate tokens định kỳ:**
   - Jira: https://id.atlassian.com/manage/api-tokens
   - Supabase: Settings → API → Regenerate key
   - Discord: Developer Portal → Bot → Regenerate

4. **Supabase RLS (Optional - Nâng Cao):**

   Bật Row Level Security để chỉ user được xem data của mình:

   ```sql
   ALTER TABLE linked_users ENABLE ROW LEVEL SECURITY;

   CREATE POLICY "Users can only see their own data"
     ON linked_users
     FOR SELECT
     USING (discord_id = auth.uid());
   ```

---

## 📊 Monitoring Supabase

### Xem Data trong Table Editor:

1. Vào Supabase → **Table Editor**
2. Click **linked_users** table
3. Sẽ thấy tất cả user đã link

### Xem Analytics:

1. Vào **Home** → **Analytics**
2. Kiểm tra:
   - Database size
   - API requests
   - Realtime connections

### Xem Logs:

1. Vào **Logs** → **Database**
2. Thấy chi tiết mọi query được chạy

---

## 🎯 Migration từ v2 sang v3

Nếu bạn có v2 (SQLite) cũ:

### Bước 1: Backup v2

```bash
# Sao lưu jira_users.db
cp jira_users.db jira_users.db.backup
```

### Bước 2: Export Data (nếu cần)

```python
import sqlite3
conn = sqlite3.connect('jira_users.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM users')
for row in cursor.fetchall():
    print(row)
```

### Bước 3: Import vào Supabase

Dùng Supabase SQL Editor:

```sql
INSERT INTO linked_users (discord_id, discord_name, jira_email, jira_api_token)
VALUES ('123456', 'username', 'email@company.com', 'ATATT...');
```

### Bước 4: Chạy v3

```bash
python bot_v3_supabase.py
```

---

## 🆘 Cần Hỗ Trợ?

1. **Kiểm tra logs:**

   ```bash
   python bot_v3_supabase.py 2>&1 | tee bot.log
   ```

2. **Test API:**

   ```bash
   # Supabase
   curl -H "apikey: YOUR_KEY" "https://YOUR_URL/rest/v1/linked_users" | python -m json.tool
   ```

3. **Liên hệ Supabase Support:** https://supabase.com/docs

---

## 📝 Changelog

### v3.0.0 - Supabase Edition

- ✅ PostgreSQL trên cloud (Supabase)
- ✅ Per-user Jira linking (`/link_jira`, `/unlink_jira`)
- ✅ Backup tự động hàng ngày
- ✅ Multi-device support
- ✅ RLS-ready (Row Level Security)
- ✅ Full Vietnamese support
- ✅ Better error handling

---

**Made with ❤️ for FiveM Team - v3 Supabase Edition**

**Powered by:** Grok 4.3 + Supabase + discord.py
