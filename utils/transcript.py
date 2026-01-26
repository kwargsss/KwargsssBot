import disnake
import datetime
import html
import markdown
import re


CSS_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    :root {
        --bg-primary: #313338;
        --bg-secondary: #2b2d31;
        --bg-tertiary: #1e1f22;
        --header-primary: #f2f3f5;
        --header-secondary: #dbdee1;
        --text-normal: #dbdee1;
        --text-muted: #949ba4;
        --text-link: #00a8fc;
        --interactive-active: #fff;
        --divider: #3f4147;
        --blurple: #5865f2;
        --blurple-hover: #4752c4;
        --danger: #fa777c;
        --brand: #5865F2;
        
        --font-primary: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
        --font-code: 'JetBrains Mono', Consolas, monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
        font-family: var(--font-primary);
        background-color: var(--bg-primary);
        color: var(--text-normal);
        font-size: 16px;
        line-height: 1.375rem;
        overflow-x: hidden;
    }

    a { color: var(--text-link); text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* --- HEADER --- */
    .meta-header {
        background-color: var(--bg-secondary);
        border-bottom: 1px solid #1f2023;
        padding: 16px 24px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .channel-info h1 {
        font-size: 1.3rem; font-weight: 700; color: var(--header-primary);
        display: flex; align-items: center; gap: 8px;
    }
    .channel-icon { color: var(--text-muted); width: 24px; height: 24px; }
    .meta-stats {
        display: flex; gap: 15px; font-size: 0.85rem; color: var(--text-muted);
    }
    .stat-badge {
        background: var(--bg-tertiary); padding: 4px 10px; border-radius: 4px;
    }

    /* --- MESSAGES --- */
    .chat-container {
        padding: 20px 16px;
        max-width: 100%;
        display: flex; flex-direction: column; gap: 0;
    }

    .message-group {
        display: flex;
        margin-top: 1.0625rem;
        padding: 2px 16px;
        position: relative;
    }
    .message-group:hover { background-color: rgba(4, 4, 5, 0.07); }

    .avatar-col { width: 50px; margin-right: 16px; flex-shrink: 0; cursor: pointer; }
    .avatar {
        width: 40px; height: 40px; border-radius: 50%;
        object-fit: cover; transition: 0.1s;
    }
    .avatar:hover { opacity: 0.8; }

    .message-content { flex: 1; min-width: 0; }

    .message-header {
        display: flex; align-items: center; gap: 8px;
        margin-bottom: 2px;
    }
    .username {
        font-size: 1rem; font-weight: 500; color: var(--header-primary);
        cursor: pointer;
    }
    .username:hover { text-decoration: underline; }
    
    .bot-tag {
        background: var(--brand); color: #fff;
        font-size: 0.625rem; text-transform: uppercase;
        padding: 1px 4px; border-radius: 3px;
        font-weight: 700; line-height: 1.3;
        vertical-align: baseline;
    }

    .timestamp {
        font-size: 0.75rem; color: var(--text-muted);
        margin-left: 0.25rem; font-weight: 400;
        cursor: help;
    }

    /* --- MARKDOWN BODY --- */
    .markup {
        color: var(--text-normal);
        font-size: 1rem;
        line-height: 1.375rem;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    .markup p { margin-bottom: 0; }
    .markup pre {
        background: var(--bg-secondary);
        border: 1px solid var(--bg-tertiary);
        border-radius: 4px;
        padding: 8px;
        font-family: var(--font-code);
        font-size: 0.875rem;
        margin-top: 6px;
        overflow-x: auto;
        color: var(--text-normal);
    }
    .markup code {
        background: var(--bg-tertiary);
        padding: 2px 4px;
        border-radius: 3px;
        font-family: var(--font-code);
        font-size: 0.85em;
    }
    .mention {
        background: rgba(88, 101, 242, 0.3);
        color: #dee0fc;
        border-radius: 3px;
        padding: 0 2px;
        font-weight: 500;
        cursor: pointer;
        transition: background-color 0.1s;
    }
    .mention:hover { background: var(--brand); color: #fff; text-decoration: none; }
    .mention.channel { background: rgba(88, 101, 242, 0.1); color: #c9cdfb; }
    .spoiler {
        background-color: #202225;
        color: transparent;
        border-radius: 3px;
        cursor: pointer;
        user-select: none;
    }
    .spoiler:active, .spoiler:hover {
        background-color: #292b2f;
        color: var(--text-normal);
    }
    .emoji {
        width: 1.375em; height: 1.375em;
        vertical-align: bottom;
        object-fit: contain;
    }
    .emoji.jumbo { width: 3rem; height: 3rem; }

    /* --- ATTACHMENTS --- */
    .attachments-grid {
        display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px;
    }
    .attachment-item {
        max-width: 400px; max-height: 350px;
        border-radius: 8px; overflow: hidden;
        border: 1px solid var(--bg-tertiary);
        background: var(--bg-secondary); cursor: pointer;
    }
    .attachment-image {
        display: block; max-width: 100%; max-height: 350px; object-fit: contain;
    }
    .file-card {
        display: flex; align-items: center; gap: 10px;
        padding: 10px; border: 1px solid var(--bg-tertiary);
        border-radius: 4px; background: var(--bg-secondary);
        max-width: 400px;
    }

    /* --- EMBEDS --- */
    .embed-container { display: grid; grid-template-columns: auto; gap: 8px; margin-top: 8px; }
    .embed {
        display: flex; max-width: 520px;
        background: var(--bg-secondary);
        border-radius: 4px; border: 1px solid var(--bg-tertiary);
        overflow: hidden;
    }
    .embed-pill { width: 4px; flex-shrink: 0; background-color: #202225; }
    .embed-inner {
        padding: 8px 16px 16px 12px;
        display: flex; flex-direction: column; gap: 8px; width: 100%;
    }
    .embed-author { display: flex; align-items: center; gap: 8px; font-size: 0.875rem; font-weight: 600; color: var(--header-secondary); margin-top: 8px;}
    .embed-author img { width: 24px; height: 24px; border-radius: 50%; }
    .embed-title { font-size: 1rem; font-weight: 600; color: var(--header-primary); }
    .embed-desc { font-size: 0.875rem; color: var(--text-normal); line-height: 1.375rem; }
    .embed-fields { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
    .embed-field { min-width: 100%; }
    .embed-field.inline { min-width: 30%; flex: 1; }
    .field-name { font-weight: 600; color: var(--header-secondary); font-size: 0.875rem; margin-bottom: 2px; }
    .field-value { font-size: 0.875rem; color: var(--text-normal); white-space: pre-wrap; }
    .embed-image { width: 100%; border-radius: 4px; margin-top: 8px; object-fit: cover; }
    .embed-thumb { max-width: 80px; max-height: 80px; border-radius: 4px; float: right; margin-left: 16px; object-fit: cover; }
    .embed-footer {
        display: flex; align-items: center; gap: 8px;
        font-size: 0.75rem; color: var(--text-muted); margin-top: 8px;
    }
    .embed-footer img { width: 20px; height: 20px; border-radius: 50%; }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
    .message-group { animation: fadeIn 0.3s ease; }
</style>

<script>
    document.addEventListener("DOMContentLoaded", () => {
        // Авто-конвертация времени в локальный часовой пояс зрителя
        document.querySelectorAll('.timestamp').forEach(el => {
            const rawTime = el.getAttribute('data-time');
            if (rawTime) {
                const date = new Date(rawTime);
                // Форматируем время как в системе пользователя (например, 22.01.2026 16:44)
                const localDate = date.toLocaleDateString([], {day:'2-digit', month:'2-digit', year:'numeric'});
                const localTime = date.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
                
                el.textContent = `${localDate} ${localTime}`;
                el.title = "Ваше местное время";
            }
        });
    });
</script>
"""



def format_discord_content(text, guild):
    if not text: return ""
    
    def replace_emoji(match):
        animated = match.group(1) == 'a'
        name = match.group(2)
        eid = match.group(3)
        ext = 'gif' if animated else 'png'
        url = f"https://cdn.discordapp.com/emojis/{eid}.{ext}"
        return f'<img src="{url}" alt=":{name}:" class="emoji" title=":{name}:">'
    
    text = re.sub(r'<(a?):(\w+):(\d+)>', replace_emoji, text)

    def replace_user(match):
        uid = int(match.group(1))
        member = guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        return f'<span class="mention">@{name}</span>'
    text = re.sub(r'<@!?(\d+)>', replace_user, text)

    def replace_role(match):
        rid = int(match.group(1))
        role = guild.get_role(rid)
        name = role.name if role else "Role"
        return f'<span class="mention" style="background: rgba(41,43,47, 0.5); color: {role.color if role else "#fff"}">@{name}</span>'
    text = re.sub(r'<@&(\d+)>', replace_role, text)

    def replace_channel(match):
        cid = int(match.group(1))
        chan = guild.get_channel(cid)
        name = chan.name if chan else "channel"
        return f'<span class="mention channel">#{name}</span>'
    text = re.sub(r'<#(\d+)>', replace_channel, text)

    text = re.sub(r'\|\|(.*?)\|\|', r'<span class="spoiler" onclick="this.style.color=\'inherit\';this.style.cursor=\'text\'">\1</span>', text)
    html_text = markdown.markdown(text, extensions=['fenced_code', 'nl2br', 'sane_lists', 'tables'])
    return html_text

async def generate_transcript(channel: disnake.TextChannel):
    messages = await channel.history(limit=None, oldest_first=True).flatten()
    
    user_ids = set()
    for m in messages:
        if not m.author.bot: user_ids.add(m.author.id)
    
    
    
    msk_zone = datetime.timezone(datetime.timedelta(hours=3))
    
    export_dt = datetime.datetime.now(msk_zone)
    export_date = export_dt.strftime("%d.%m.%Y %H:%M (МСК)")

    html_out = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Архив: {html.escape(channel.name)}</title>
        {CSS_STYLE}
    </head>
    <body>
        <div class="meta-header">
            <div class="channel-info">
                <h1>
                    <svg class="channel-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    {html.escape(channel.name)}
                </h1>
                <div class="meta-stats">
                    <span>Тема: {html.escape(str(channel.topic)) if channel.topic else 'Нет темы'}</span>
                </div>
            </div>
            <div class="meta-stats">
                <div class="stat-badge">Сообщений: {len(messages)}</div>
                <div class="stat-badge">Участников: {len(user_ids)}</div>
                <div class="stat-badge">Дата: {export_date}</div>
            </div>
        </div>

        <div class="chat-container">
    """

    for msg in messages:
        username = html.escape(msg.author.display_name)
        avatar_url = msg.author.display_avatar.url
        
        
        msg_msk = msg.created_at.astimezone(msk_zone)
        time_str = msg_msk.strftime("%d.%m.%Y %H:%M")
        
        
        
        iso_time = msg.created_at.isoformat()
        
        color = str(msg.author.color) if msg.author.color != disnake.Color.default() else "#fff"
        bot_badge = '<span class="bot-tag">BOT</span>' if msg.author.bot else ''
        content_html = format_discord_content(msg.content, channel.guild)

        attachments_html = ""
        if msg.attachments:
            attachments_html = '<div class="attachments-grid">'
            for att in msg.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    attachments_html += f'<div class="attachment-item"><a href="{att.url}" target="_blank"><img src="{att.url}" class="attachment-image"></a></div>'
                else:
                    attachments_html += f"""
                    <div class="file-card">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#949ba4" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>
                        <div style="flex:1; overflow:hidden;">
                            <div style="color:#dbdee1; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{html.escape(att.filename)}</div>
                            <div style="color:#949ba4; font-size:0.75rem;">{round(att.size/1024, 2)} KB</div>
                        </div>
                        <a href="{att.url}" target="_blank" style="color:#00a8fc;"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg></a>
                    </div>
                    """
            attachments_html += '</div>'

        embeds_html = ""
        if msg.embeds:
            embeds_html = '<div class="embed-container">'
            for emb in msg.embeds:
                pill_color = f"#{emb.color.value:06x}" if emb.color else "#202225"
                author_html = ""
                if emb.author:
                    icon = f'<img src="{emb.author.icon_url}">' if emb.author.icon_url else ""
                    author_html = f'<div class="embed-author">{icon}{html.escape(emb.author.name)}</div>'
                
                title_html = f'<div class="embed-title">{format_discord_content(emb.title, channel.guild)}</div>' if emb.title else ""
                
                desc_html = ""
                if emb.description:
                    desc_parsed = format_discord_content(emb.description, channel.guild)
                    desc_html = f'<div class="embed-desc">{desc_parsed}</div>'
                
                fields_html = ""
                if emb.fields:
                    fields_html = '<div class="embed-fields">'
                    for f in emb.fields:
                        inline_class = "inline" if f.inline else ""
                        val_parsed = format_discord_content(f.value, channel.guild)
                        fields_html += f'<div class="embed-field {inline_class}"><div class="field-name">{html.escape(f.name)}</div><div class="field-value">{val_parsed}</div></div>'
                    fields_html += '</div>'
                
                img_html = f'<img src="{emb.image.url}" class="embed-image">' if emb.image else ""
                thumb_html = f'<img src="{emb.thumbnail.url}" class="embed-thumb">' if emb.thumbnail else ""
                
                footer_html = ""
                if emb.footer:
                    icon = f'<img src="{emb.footer.icon_url}">' if emb.footer.icon_url else ""
                    footer_html = f'<div class="embed-footer">{icon}{html.escape(emb.footer.text)}</div>'

                embeds_html += f"""
                <div class="embed">
                    <div class="embed-pill" style="background-color: {pill_color};"></div>
                    <div class="embed-inner">
                        <div style="display:flex; justify-content: space-between;">
                            <div style="width: 100%;">
                                {author_html}
                                {title_html}
                                {desc_html}
                                {fields_html}
                            </div>
                            {thumb_html}
                        </div>
                        {img_html}
                        {footer_html}
                    </div>
                </div>
                """
            embeds_html += '</div>'

        
        html_out += f"""
        <div class="message-group">
            <div class="avatar-col">
                <img src="{avatar_url}" class="avatar" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'">
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="username" style="color: {color}">{username}</span>
                    {bot_badge}
                    <span class="timestamp" data-time="{iso_time}">{time_str}</span>
                </div>
                <div class="markup">{content_html}</div>
                {attachments_html}
                {embeds_html}
            </div>
        </div>
        """

    html_out += """
        </div>
        <div style="text-align: center; margin-top: 50px; padding-bottom: 30px; color: #5865f2; font-size: 0.8rem; opacity: 0.7;">
            Exported by KwargsssBot System
        </div>
    </body>
    </html>
    """
    
    return html_out