import aiosqlite
import disnake
import time
import datetime

from config import *


class UsersDataBase:
    def __init__(self):
        self.path = DB_FILE
        self.name = str(self.path)
        self.conn = None
        
    async def connect(self):
        if self.conn is None:
            self.conn = await aiosqlite.connect(self.name)
            self.conn.row_factory = aiosqlite.Row 

            await self.conn.execute("PRAGMA journal_mode=WAL")
            await self.conn.execute("PRAGMA foreign_keys=ON;")

            await self.create_tables()

    async def execute(self, query: str, args: tuple = ()):
        async with self.conn.execute(query, args) as cursor:
            await self.conn.commit()
            return cursor

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def create_tables(self):
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                money INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                rate INTEGER DEFAULT 0,
                charity INTEGER DEFAULT 0,
                bio TEXT DEFAULT '```/bio```',
                prison_release REAL DEFAULT 0,
                work_xp INTEGER DEFAULT 0,
                credit_rating INTEGER DEFAULT 0
            )
        """)
        
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cooldown (
                user_id INTEGER,
                command TEXT,
                expires_at REAL,
                PRIMARY KEY (user_id, command)
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                messages INTEGER DEFAULT 0,
                commands INTEGER DEFAULT 0
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_id INTEGER,
                type TEXT,
                status TEXT DEFAULT 'open',
                topic TEXT,
                created_at TEXT,
                transcript_url TEXT
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS punishments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                expires_at REAL,
                reason TEXT DEFAULT 'Не указана',
                moderator_id INTEGER DEFAULT 0,
                created_at REAL DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                target_id INTEGER,
                amount INTEGER,
                source_type TEXT,
                target_type TEXT,
                created_at REAL
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS marriages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER,
                user2_id INTEGER,
                marriage_date REAL,
                balance INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                love_xp INTEGER DEFAULT 0,
                last_love REAL DEFAULT 0,
                improvements TEXT DEFAULT ''                                
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS marriages_businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                marriage_id INTEGER,
                type TEXT,
                balance INTEGER DEFAULT 0,
                supplies INTEGER DEFAULT 0,
                marketing_lvl INTEGER DEFAULT 0,
                logistics_lvl INTEGER DEFAULT 0,
                security_lvl INTEGER DEFAULT 0,
                automation_lvl INTEGER DEFAULT 0,
                offshore_lvl INTEGER DEFAULT 0
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                type TEXT,
                balance INTEGER DEFAULT 0,
                supplies INTEGER DEFAULT 0,
                total_earnings INTEGER DEFAULT 0,
                marketing_lvl INTEGER DEFAULT 0,
                logistics_lvl INTEGER DEFAULT 0,
                security_lvl INTEGER DEFAULT 0,
                automation_lvl INTEGER DEFAULT 0,
                offshore_lvl INTEGER DEFAULT 0,
                last_tax REAL DEFAULT 0
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                profit_amount INTEGER,
                start_time REAL,
                end_time REAL,
                status TEXT DEFAULT 'active'
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount_taken INTEGER,
                amount_total INTEGER,
                amount_paid INTEGER DEFAULT 0,
                due_date REAL,
                last_penalty_date REAL,
                status TEXT DEFAULT 'active'
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS economy_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                supply_factor REAL DEFAULT 1.0,
                status_name TEXT DEFAULT 'Стабильность'
            )
        """)    

        await self.conn.execute("""
            INSERT OR IGNORE INTO economy_state (id, supply_factor, status_name) 
            VALUES (1, 1.0, 'Стабильность')
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS houses (
                user_id INTEGER PRIMARY KEY,
                type TEXT,
                bought_at INTEGER
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                user_id INTEGER PRIMARY KEY,
                owner_id INTEGER,
                rent_price INTEGER DEFAULT 0,
                joined_at INTEGER
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value INTEGER
            )
        """)

        await self.conn.commit()

    async def get_all_users_raw(self):
        async with self.conn.execute('SELECT * FROM users') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_cooldowns_raw(self):
        async with self.conn.execute('SELECT * FROM cooldown') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def increment_daily_stat(self, stat_type: str):
        today = datetime.date.today().isoformat()
        
        await self.conn.execute(
            "INSERT OR IGNORE INTO daily_stats (date, messages, commands) VALUES (?, 0, 0)",
            (today,)
        )

        column = "messages" if stat_type == "message" else "commands"
        await self.execute(
            f"UPDATE daily_stats SET {column} = {column} + 1 WHERE date = ?",
            (today,)
        )

    async def get_weekly_stats(self):
        today = datetime.date.today()
        stats = []
        
        for i in range(6, -1, -1):
            date = (today - datetime.timedelta(days=i)).isoformat()
            
            async with self.conn.execute("SELECT messages, commands FROM daily_stats WHERE date = ?", (date,)) as cursor:
                row = await cursor.fetchone()
                
            if row:
                stats.append({"date": date, "msg": row[0], "cmd": row[1]})
            else:
                stats.append({"date": date, "msg": 0, "cmd": 0})
                
        return stats

    async def get_user(self, user: disnake.Member):
        async with self.conn.execute('SELECT * FROM users WHERE id = ?', (user.id,)) as cursor:
            return await cursor.fetchone()

    async def add_user(self, user: disnake.Member):
        if await self.get_user(user):
            return
            
        await self.execute(
            'INSERT INTO users (id, money, bank, rate, charity, bio, work_xp, credit_rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (user.id, 0, 0, 0, 0, "```/био```", 0, 500)
        )

    async def update_work_xp(self, user: disnake.Member, xp_amount: int):
        await self.execute('UPDATE users SET work_xp = work_xp + ? WHERE id = ?', (xp_amount, user.id))
    
    async def get_bio(self, user: disnake.Member):
        async with self.conn.execute('SELECT bio FROM users WHERE id = ?', (user.id,)) as cursor:
            record = await cursor.fetchone()
        return record[0] if record else 0

    async def get_balance(self, user: disnake.Member, currency: str):
        if currency == 'money':
            query = 'SELECT money FROM users WHERE id = ?'
        elif currency == 'bank':
            query = 'SELECT bank FROM users WHERE id = ?'
        else:
            return 0

        async with self.conn.execute(query, (user.id,)) as cursor:
            record = await cursor.fetchone()
        return record[0] if record else 0

    async def update_rate(self, user: disnake.Member, rate: int):
        await self.execute('UPDATE users SET rate = rate + ? WHERE id = ?', (rate, user.id))
            
    async def get_rate(self, user: disnake.Member):
        async with self.conn.execute('SELECT rate FROM users WHERE id = ?', (user.id,)) as cursor:
            record = await cursor.fetchone()
        return record[0] if record else 0
    
    async def update_charity(self, user: disnake.Member, charity: int):
        await self.execute('UPDATE users SET charity = charity + ? WHERE id = ?', (charity, user.id))
            
    async def get_charity(self, user: disnake.Member):
        async with self.conn.execute('SELECT charity FROM users WHERE id = ?', (user.id,)) as cursor:
            record = await cursor.fetchone()
        return record[0] if record else 0

    async def update_money(self, user: disnake.Member, money: int, bank: int):
        await self.execute(
            'UPDATE users SET money = money + ?, bank = bank + ? WHERE id = ?', 
            (money, bank, user.id)
        )
            
    async def update_bio(self, user: disnake.Member, bio: str):
        await self.execute('UPDATE users SET bio = ? WHERE id = ?', (bio, user.id))

    async def set_cooldown(self, user_id: int, command_name: str, seconds: int):
        expires_at = time.time() + seconds
        await self.execute(
            "REPLACE INTO cooldown (user_id, command, expires_at) VALUES (?, ?, ?)", 
            (user_id, command_name, expires_at)
        )

    async def remove_expired_cooldowns(self):
        await self.execute("DELETE FROM cooldown WHERE expires_at < ?", (time.time(),))

    async def get_remaining_cooldown(self, user_id: int, command_name: str):
        async with self.conn.execute(
            "SELECT expires_at FROM cooldown WHERE user_id = ? AND command = ?",
            (user_id, command_name)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                remaining = row[0] - time.time()
                return max(0, remaining)
        return 0
    
    async def create_ticket(self, user_id: int, channel_id: int, t_type: str, topic: str):
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = await self.execute(
            "INSERT INTO tickets (user_id, channel_id, type, status, topic, created_at) VALUES (?, ?, ?, 'open', ?, ?)",
            (user_id, channel_id, t_type, topic, created_at)
        )
        return cursor.lastrowid

    async def get_ticket_by_channel(self, channel_id: int):
        async with self.conn.execute("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_ticket_by_id(self, ticket_id: int):
        async with self.conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def close_ticket(self, ticket_id: int):
        await self.execute("UPDATE tickets SET status = 'closed' WHERE ticket_id = ?", (ticket_id,))

    async def set_transcript(self, ticket_id: int, url: str):
        await self.execute("UPDATE tickets SET transcript_url = ? WHERE ticket_id = ?", (url, ticket_id))
        
    async def get_active_tickets(self):
        async with self.conn.execute("SELECT * FROM tickets WHERE status != 'deleted'") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        
    async def reopen_ticket(self, ticket_id: int):
        await self.execute("UPDATE tickets SET status = 'open' WHERE ticket_id = ?", (ticket_id,))

    async def add_punishment(self, user_id: int, p_type: str, expires_at: float, reason: str = None, moderator_id: int = None):
        created_at = time.time()
        await self.execute(
            "INSERT INTO punishments (user_id, type, expires_at, reason, moderator_id, created_at, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
            (user_id, p_type, expires_at, reason, moderator_id, created_at)
        )

    async def get_expired_punishments(self):
        sql = "SELECT * FROM punishments WHERE expires_at < ? AND type != 'warn' AND status = 'active'"
        async with self.conn.execute(sql, (time.time(),)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def remove_punishment(self, row_id: int):
        await self.execute("DELETE FROM punishments WHERE id = ?", (row_id,))
    
    async def get_active_ban(self, user_id: int):
        sql = "SELECT * FROM punishments WHERE user_id = ? AND type = 'ban' AND status = 'active'"
        async with self.conn.execute(sql, (user_id,)) as cursor:
            return await cursor.fetchone()

    async def get_active_mute(self, user_id: int):
        sql = "SELECT * FROM punishments WHERE user_id = ? AND type = 'mute' AND status = 'active'"
        async with self.conn.execute(sql, (user_id,)) as cursor:
            return await cursor.fetchone()
        
    async def get_warns_count(self, user_id: int) -> int:
        async with self.conn.execute("SELECT COUNT(*) FROM punishments WHERE user_id = ? AND type = 'warn' AND status = 'active'", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0
        
    async def remove_last_warn(self, user_id: int):
        async with self.conn.execute("SELECT id FROM punishments WHERE user_id = ? AND type = 'warn' AND status = 'active' ORDER BY id DESC LIMIT 1", (user_id,)) as cursor:
            row = await cursor.fetchone()
            
        if row:
            await self.execute("UPDATE punishments SET status = 'revoked' WHERE id = ?", (row[0],))
            return True
        return False
    
    async def get_user_warns(self, user_id: int):
        async with self.conn.execute(
            "SELECT * FROM punishments WHERE user_id = ? AND type = 'warn' ORDER BY id DESC", 
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        
    async def get_punishment_history(self, user_id: int, p_type: str = "all"):
        if p_type == "all":
            sql = "SELECT * FROM punishments WHERE user_id = ? ORDER BY id DESC LIMIT 10"
            args = (user_id,)
        else:
            sql = "SELECT * FROM punishments WHERE user_id = ? AND type = ? ORDER BY id DESC LIMIT 10"
            args = (user_id, p_type)

        async with self.conn.execute(sql, args) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        
    async def expire_punishment(self, row_id: int):
        await self.execute("UPDATE punishments SET status = 'expired' WHERE id = ?", (row_id,))

    async def revoke_punishment(self, row_id: int):
        await self.execute("UPDATE punishments SET status = 'revoked' WHERE id = ?", (row_id,))

    async def get_user_extended_stats(self, user_id: int):
        stats = {}

        async with self.conn.execute("SELECT COUNT(*) FROM tickets WHERE user_id = ?", (user_id,)) as cursor:
            stats['tickets_total'] = (await cursor.fetchone())[0]
            
        async with self.conn.execute("SELECT COUNT(*) FROM tickets WHERE user_id = ? AND status = 'open'", (user_id,)) as cursor:
            stats['tickets_open'] = (await cursor.fetchone())[0]

        async with self.conn.execute("SELECT COUNT(*) FROM punishments WHERE user_id = ? AND type = 'ban'", (user_id,)) as cursor:
            stats['bans_total'] = (await cursor.fetchone())[0]

        async with self.conn.execute("SELECT COUNT(*) FROM punishments WHERE user_id = ? AND type = 'mute'", (user_id,)) as cursor:
            stats['mutes_total'] = (await cursor.fetchone())[0]
            
        async with self.conn.execute("SELECT COUNT(*) FROM punishments WHERE user_id = ? AND type = 'warn'", (user_id,)) as cursor:
            stats['warns_total'] = (await cursor.fetchone())[0]

        return stats
    
    async def add_transaction(self, sender_id: int, target_id: int, amount: int, source: str, target: str):
        created_at = time.time()
        await self.execute(
            "INSERT INTO transactions (sender_id, target_id, amount, source_type, target_type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (sender_id, target_id, amount, source, target, created_at)
        )

    async def get_user_transactions(self, user_id: int, limit: int = 10):
        sql = """
            SELECT * FROM transactions 
            WHERE sender_id = ? OR target_id = ? 
            ORDER BY id DESC LIMIT ?
        """
        async with self.conn.execute(sql, (user_id, user_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        
    async def get_marriage(self, user_id: int):
        sql = "SELECT * FROM marriages WHERE user1_id = ? OR user2_id = ?"
        async with self.conn.execute(sql, (user_id, user_id)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_marriage(self, user1: int, user2: int):
        date = time.time()
        u1, u2 = sorted([user1, user2])
        await self.execute(
            "INSERT INTO marriages (user1_id, user2_id, marriage_date) VALUES (?, ?, ?)",
            (u1, u2, date)
        )

    async def delete_marriage(self, marriage_id: int):
        await self.execute("DELETE FROM marriages WHERE id = ?", (marriage_id,))

    async def update_family_balance(self, marriage_id: int, amount: int):
        await self.execute("UPDATE marriages SET balance = balance + ? WHERE id = ?", (amount, marriage_id))

    async def add_love_xp(self, marriage_id: int, xp: int):
        now = time.time()
        await self.execute(
            "UPDATE marriages SET love_xp = love_xp + ?, last_love = ? WHERE id = ?", 
            (xp, now, marriage_id)
        )
        await self.execute(
            "UPDATE marriages SET level = 1 + (love_xp / 100) WHERE id = ?", 
            (marriage_id,)
        )

    async def jail_user(self, user_id: int, duration: int): 
        release_time = time.time() + duration
        await self.execute("UPDATE users SET prison_release = ? WHERE id = ?", (release_time, user_id))
        return release_time

    async def check_prison_status(self, user_id: int):
        try:
            async with self.conn.execute("SELECT prison_release FROM users WHERE id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                
            if not row or not row[0]:
                return 0
                
            release_time = row[0]
            if release_time > time.time():
                return release_time
            else:
                return 0
        except:
            return 0
        
    async def get_user_businesses(self, owner_id: int):
        async with self.conn.execute("SELECT * FROM businesses WHERE owner_id = ?", (owner_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_business_by_id(self, biz_id: int):
        async with self.conn.execute("SELECT * FROM businesses WHERE id = ?", (biz_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_business(self, owner_id: int, biz_type: str):
        await self.execute(
            "INSERT INTO businesses (owner_id, type) VALUES (?, ?)",
            (owner_id, biz_type)
        )

    async def update_biz_stats(self, biz_id: int, supplies_change: int, balance_change: int):
        await self.execute(
            """UPDATE businesses 
               SET supplies = MAX(0, supplies + ?), 
                   balance = MAX(0, balance + ?),
                   total_earnings = total_earnings + MAX(0, ?)
               WHERE id = ?""",
            (supplies_change, balance_change, balance_change, biz_id)
        )
    
    async def upgrade_biz(self, biz_id: int, upgrade_type: str):
        query = f"UPDATE businesses SET {upgrade_type} = {upgrade_type} + 1 WHERE id = ?"
        await self.execute(query, (biz_id,))

    async def delete_business(self, biz_id: int):
        await self.execute("DELETE FROM businesses WHERE id = ?", (biz_id,))

    async def get_economy_state(self):
        async with self.conn.execute("SELECT supply_factor, status_name FROM economy_state WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            return row if row else (1.0, "Стабильность")

    async def update_economy_state(self, factor: float, name: str):
        await self.execute(
            "UPDATE economy_state SET supply_factor = ?, status_name = ? WHERE id = 1", 
            (factor, name)
        )

    async def get_house(self, user_id: int):
        async with self.conn.execute("SELECT * FROM houses WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

    async def set_house(self, user_id: int, house_type: str):
        await self.execute(
            "INSERT OR REPLACE INTO houses (user_id, type, bought_at) VALUES (?, ?, ?)",
            (user_id, house_type, int(disnake.utils.utcnow().timestamp()))
        )
        
    async def sell_house(self, user_id: int):
        await self.execute("DELETE FROM houses WHERE user_id = ?", (user_id,))

    async def get_credit_rating(self, user_id: int):
        async with self.conn.execute("SELECT credit_rating FROM users WHERE id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else 500

    async def update_credit_rating(self, user_id: int, change: int):
        await self.execute(
            "UPDATE users SET credit_rating = MAX(0, MIN(1000, credit_rating + ?)) WHERE id = ?", 
            (change, user_id)
        )

    async def create_deposit(self, user_id: int, amount: int, profit: int, days: int):
        start = time.time()
        end = start + (days * 86400)
        await self.execute(
            "INSERT INTO deposits (user_id, amount, profit_amount, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, profit, start, end)
        )

    async def get_active_deposit(self, user_id: int):
        async with self.conn.execute("SELECT * FROM deposits WHERE user_id = ? AND status = 'active'", (user_id,)) as cursor:
            return await cursor.fetchone()

    async def create_loan(self, user_id: int, amount: int, total_pay: int, days: int):
        due_date = time.time() + (days * 86400)
        await self.execute(
            "INSERT INTO loans (user_id, amount_taken, amount_total, due_date, last_penalty_date) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, total_pay, due_date, time.time())
        )

    async def get_active_loan(self, user_id: int):
        async with self.conn.execute("SELECT * FROM loans WHERE user_id = ? AND status = 'active'", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def repay_loan_part(self, loan_id: int, amount: int):
        await self.execute(
            "UPDATE loans SET amount_paid = amount_paid + ? WHERE id = ?", 
            (amount, loan_id)
        )

    async def close_loan(self, loan_id: int):
        await self.execute("UPDATE loans SET status = 'closed' WHERE id = ?", (loan_id,))

    async def get_ready_deposits(self):
        async with self.conn.execute("SELECT * FROM deposits WHERE end_time <= ? AND status = 'active'", (time.time(),)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def close_deposit(self, deposit_id: int):
        await self.execute("UPDATE deposits SET status = 'paid' WHERE id = ?", (deposit_id,))

    async def get_overdue_loans(self):
        async with self.conn.execute("SELECT * FROM loans WHERE status = 'active'") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def apply_loan_penalty(self, loan_id: int, penalty_amount: int):
        await self.execute(
            "UPDATE loans SET amount_total = amount_total + ?, last_penalty_date = ? WHERE id = ?",
            (penalty_amount, time.time(), loan_id)
        )

    async def revoke_deposit(self, deposit_id: int):
        await self.execute("UPDATE deposits SET status = 'revoked' WHERE id = ?", (deposit_id,))

    async def add_tenant(self, user_id: int, owner_id: int, rent: int):
        await self.execute(
            "INSERT OR REPLACE INTO tenants (user_id, owner_id, rent_price, joined_at) VALUES (?, ?, ?, ?)",
            (user_id, owner_id, rent, int(time.time()))
        )

    async def remove_tenant(self, user_id: int):
        await self.execute("DELETE FROM tenants WHERE user_id = ?", (user_id,))

    async def get_tenant_info(self, user_id: int):
        async with self.conn.execute("SELECT * FROM tenants WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_house_tenants(self, owner_id: int):
        async with self.conn.execute("SELECT * FROM tenants WHERE owner_id = ?", (owner_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
    async def get_living_space(self, user_id: int):
        house = await self.get_house(user_id)
        if house:
            return house, 'owner'

        tenant = await self.get_tenant_info(user_id)
        if tenant:
            owner_house = await self.get_house(tenant['owner_id'])
            if owner_house:
                return owner_house, 'tenant'
        
        return None, None,

    async def add_family_improvement(self, marriage_id: int, improvement: str):
        async with self.conn.execute("SELECT improvements FROM marriages WHERE id = ?", (marriage_id,)) as cursor:
            row = await cursor.fetchone()
            current = row[0] if row and row[0] else ""
        
        if current:
            new_imps = current + "," + improvement
        else:
            new_imps = improvement
            
        await self.execute("UPDATE marriages SET improvements = ? WHERE id = ?", (new_imps, marriage_id))

    async def get_family_businesses(self, marriage_id: int):
        async with self.conn.execute("SELECT * FROM marriages_businesses WHERE marriage_id = ?", (marriage_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def create_family_business(self, marriage_id: int, biz_type: str):
        await self.execute("INSERT INTO marriages_businesses (marriage_id, type) VALUES (?, ?)", (marriage_id, biz_type))

    async def get_family_business(self, biz_id: int):
        async with self.conn.execute("SELECT * FROM marriages_businesses WHERE id = ?", (biz_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_family_biz_stats(self, biz_id: int, supplies: int, balance: int):
        await self.execute(
            "UPDATE marriages_businesses SET supplies = MAX(0, supplies + ?), balance = MAX(0, balance + ?) WHERE id = ?",
            (supplies, balance, biz_id)
        )
    
    async def upgrade_family_biz(self, biz_id: int, upgrade_type: str):
        await self.execute(f"UPDATE marriages_businesses SET {upgrade_type} = {upgrade_type} + 1 WHERE id = ?", (biz_id,))

    async def delete_family_business(self, biz_id: int):
        await self.execute("DELETE FROM marriages_businesses WHERE id = ?", (biz_id,))

    async def get_global_economy_data(self):
        async with self.conn.execute("SELECT money, bank FROM users") as cursor:
            users_data = await cursor.fetchall()

        biz_data = []
        try:
            async with self.conn.execute("SELECT type FROM businesses") as cursor:
                biz_data.extend(await cursor.fetchall())
        except Exception: pass
            
        try:
            async with self.conn.execute("SELECT type FROM marriages_businesses") as cursor:
                biz_data.extend(await cursor.fetchall())
        except Exception: pass

        family_data = []
        
        async with self.conn.execute("SELECT balance FROM marriages") as cursor:
            family_data = await cursor.fetchall()
            
        return users_data, biz_data, family_data
    
    async def set_maintenance(self, state: bool):
        val = 1 if state else 0
        await self.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('maintenance', ?)", (val,))

    async def get_maintenance(self):
        async with self.conn.execute("SELECT value FROM settings WHERE key = 'maintenance'") as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0] == 1
            return False