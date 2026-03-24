import os
import re
import pymysql
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置信息
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'telegram_bot')
OWNER_ID = os.getenv('OWNER_ID')

# 安装状态管理
install_states = {}

# 连接数据库
def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

# 初始化数据库
def init_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 创建表（如果不存在），保留现有数据
        tables = [
            '''
            CREATE TABLE IF NOT EXISTS bot_configs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                username VARCHAR(255),
                is_global_enabled BOOLEAN DEFAULT TRUE
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS keyword_replies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                keyword VARCHAR(255) UNIQUE NOT NULL,
                reply TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) UNIQUE NOT NULL
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS group_configs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                group_id VARCHAR(255) UNIQUE NOT NULL,
                is_enabled BOOLEAN DEFAULT TRUE
            )
            '''
        ]
        
        for table in tables:
            cursor.execute(table)
        
        conn.commit()
        cursor.close()
        conn.close()
        print('数据库初始化成功')
    except Exception as e:
        print(f'数据库初始化错误: {e}')

# 检查是否是管理员
async def is_admin(user_id):
    print(f"检查用户 {user_id} 是否是管理员")
    if str(user_id) == OWNER_ID:
        print(f"用户 {user_id} 是机器人拥有者")
        return True
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM admins WHERE user_id = %s', (str(user_id),))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        print(f"用户 {user_id} 是管理员: {admin is not None}")
        return admin is not None
    except Exception as e:
        print(f"检查管理员错误: {e}")
        return False

# 获取机器人配置
def get_bot_config():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bot_configs LIMIT 1')
    config = cursor.fetchone()
    cursor.close()
    conn.close()
    return config

# 初始化命令
async def install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) != OWNER_ID:
        await update.message.reply_text('只有机器人拥有者可以运行此命令')
        return
    
    # 发送提示消息
    try:
        await update.message.reply_text('请发送机器人名称：')
        install_states[user_id] = {'step': 'name'}
    except Exception as e:
        print(f'发送消息错误: {e}')

# 处理文本消息
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    
    print(f"收到消息: {message_text} 来自用户: {user_id}")
    
    # 检查是否在安装过程中
    if user_id in install_states:
        print(f"用户 {user_id} 正在安装过程中，状态: {install_states[user_id]['step']}")
        await handle_install_step(update, context)
        return
    
    # 检查是否是学习格式
    bot_config = get_bot_config()
    print(f"机器人配置: {bot_config}")
    
    if bot_config:
        print(f"机器人名称: {bot_config.get('name')}")
        # 构建学习模式，使用更灵活的匹配
        bot_name = bot_config.get("name", "")
        # 尝试不同的格式，包括处理空格和无方括号的情况
        patterns = [
            # 标准格式：[机器人名称学；关键词；回复内容]
            rf'^\[{re.escape(bot_name)}\s*学\s*；\s*(.+?)\s*；\s*(.+?)\s*\]$',
            # 无方括号的情况：机器人名称学；关键词；回复内容
            rf'^{re.escape(bot_name)}\s*学\s*；\s*(.+?)\s*；\s*(.+?)$',
            # 英文分号，无方括号
            rf'^{re.escape(bot_name)}\s*学\s*;\s*(.*?)\s*;\s*(.*?)$',
            # 空格分隔，无方括号
            rf'^{re.escape(bot_name)}\s*学\s+(.*?)\s+(.*?)$'
        ]
        
        match = None
        # 打印原始消息和编码
        print(f"原始消息: {message_text}")
        print(f"消息编码: {[ord(c) for c in message_text]}")
        
        for i, pattern in enumerate(patterns):
            print(f"尝试学习模式 {i+1}: {pattern}")
            learn_pattern = re.compile(pattern)
            temp_match = learn_pattern.match(message_text)
            print(f"匹配结果: {temp_match}")
            if temp_match:
                match = temp_match
                print(f"匹配成功: {match.groups()}")
                break
        
        if match:
            print(f"匹配到学习格式，关键词: {match.groups()[0]}, 回复: {match.groups()[1]}")
            await handle_learn(update, context, match)
            return
    else:
        print("未找到机器人配置，无法处理学习格式")
    
    # 检查是否需要回复关键词
    print("检查关键词回复")
    await handle_reply(update, context)

# 处理安装步骤
async def handle_install_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    state = install_states.get(user_id)
    
    if not state:
        return
    
    try:
        if state['step'] == 'name':
            name = message_text
            try:
                await update.message.reply_text('请发送机器人用户名（不包含@）：')
                install_states[user_id] = {'step': 'username', 'name': name}
            except Exception as e:
                print(f'发送消息错误: {e}')
        
        elif state['step'] == 'username':
            username = message_text
            try:
                await update.message.reply_text('是否添加更多管理员？（是/否）')
                install_states[user_id] = {'step': 'admin', 'name': state['name'], 'username': username}
            except Exception as e:
                print(f'发送消息错误: {e}')
        
        elif state['step'] == 'admin':
            add_admins = message_text.lower() == '是'
            
            # 创建机器人配置
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 检查是否已安装
            cursor.execute('SELECT * FROM bot_configs LIMIT 1')
            existing_config = cursor.fetchone()
            
            if existing_config:
                try:
                    await update.message.reply_text('机器人已经安装')
                except Exception as e:
                    print(f'发送消息错误: {e}')
                del install_states[user_id]
                cursor.close()
                conn.close()
                return
            
            # 插入配置
            cursor.execute('INSERT INTO bot_configs (name, username) VALUES (%s, %s)', 
                         (state['name'], state['username']))
            conn.commit()
            
            cursor.close()
            conn.close()
            
            try:
                await update.message.reply_text('机器人安装成功！')
            except Exception as e:
                print(f'发送消息错误: {e}')
            
            if add_admins:
                try:
                    await update.message.reply_text('请逐个发送管理员用户ID，发送 /done 完成：')
                    install_states[user_id] = {'step': 'add_admin'}
                except Exception as e:
                    print(f'发送消息错误: {e}')
            else:
                del install_states[user_id]
        
        elif state['step'] == 'add_admin':
            if message_text == '/done':
                try:
                    await update.message.reply_text('管理员设置完成')
                except Exception as e:
                    print(f'发送消息错误: {e}')
                del install_states[user_id]
                return
            
            # 添加管理员
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute('INSERT INTO admins (user_id) VALUES (%s)', (message_text,))
                conn.commit()
                try:
                    await update.message.reply_text(f'管理员 {message_text} 添加成功')
                except Exception as e:
                    print(f'发送消息错误: {e}')
            except pymysql.IntegrityError:
                try:
                    await update.message.reply_text('添加管理员失败：该用户已存在')
                except Exception as e:
                    print(f'发送消息错误: {e}')
            
            cursor.close()
            conn.close()
    
    except Exception as e:
        print(f'安装过程错误: {e}')
        try:
            await update.message.reply_text('安装失败')
        except Exception as reply_error:
            print(f'发送错误消息错误: {reply_error}')
        if user_id in install_states:
            del install_states[user_id]

# 处理学习关键词
async def handle_learn(update: Update, context: ContextTypes.DEFAULT_TYPE, match):
    user_id = update.effective_user.id
    
    # 检查权限
    is_admin_flag = await is_admin(user_id)
    print(f"用户 {user_id} 权限检查结果: {is_admin_flag}")
    if not is_admin_flag:
        print(f"用户 {user_id} 没有管理员权限，拒绝学习关键词")
        return
    
    keyword, reply = match.groups()
    
    try:
        print(f"准备添加关键词: {keyword}, 回复: {reply}")
        conn = get_db_connection()
        print(f"数据库连接成功")
        cursor = conn.cursor()
        
        # 插入或更新关键词
        print(f"执行SQL语句")
        cursor.execute('''
        INSERT INTO keyword_replies (keyword, reply) 
        VALUES (%s, %s) 
        ON DUPLICATE KEY UPDATE reply = %s, updated_at = CURRENT_TIMESTAMP
        ''', (keyword, reply, reply))
        
        print(f"SQL执行成功，影响行数: {cursor.rowcount}")
        conn.commit()
        print(f"事务提交成功")
        cursor.close()
        conn.close()
        print(f"数据库连接关闭")
        
        try:
            await update.message.reply_text('关键词学习成功！')
        except Exception as reply_error:
            print(f'发送回复消息错误: {reply_error}')
            # 忽略回复错误，确保关键词添加成功
    
    except Exception as e:
        print(f'学习错误: {e}')
        try:
            await update.message.reply_text('学习关键词失败')
        except Exception as reply_error:
            print(f'发送错误消息错误: {reply_error}')

# 处理回复关键词
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    # 检查全局开关
    bot_config = get_bot_config()
    if not bot_config or not bot_config.get('is_global_enabled', True):
        return
    
    # 检查群组开关
    if chat_type in ['group', 'supergroup']:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # 尝试检查表是否存在
            cursor.execute('SHOW TABLES LIKE "group_configs"')
            table_exists = cursor.fetchone()
            
            if table_exists:
                # 尝试获取表结构
                cursor.execute('DESCRIBE group_configs')
                columns = [row[0] for row in cursor.fetchall()]
                
                if 'group_id' in columns:
                    cursor.execute('SELECT * FROM group_configs WHERE group_id = %s', (str(chat_id),))
                    group_config = cursor.fetchone()
                    
                    if group_config and not group_config.get('is_enabled', True):
                        cursor.close()
                        conn.close()
                        return
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f'群组配置检查错误: {e}')
            # 忽略错误，继续执行
    
    # 查找关键词
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM keyword_replies')
        keywords = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # 找到所有匹配的关键词
        matched_keywords = []
        for keyword_reply in keywords:
            keyword = keyword_reply.get('keyword')
            if keyword and keyword in message_text:
                matched_keywords.append((len(keyword), keyword_reply))
        
        # 按关键词长度降序排序，选择最长的匹配
        if matched_keywords:
            matched_keywords.sort(reverse=True, key=lambda x: x[0])
            longest_match = matched_keywords[0][1]
            try:
                await update.message.reply_text(longest_match.get('reply', ''))
            except Exception as reply_error:
                print(f'发送回复消息错误: {reply_error}')
                # 忽略回复错误，确保其他功能正常
    except Exception as e:
        print(f'关键词查找错误: {e}')
        # 忽略错误，继续执行

# 群组配置命令
async def config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    
    # 检查权限
    if not await is_admin(user_id):
        await update.message.reply_text('只有管理员可以运行此命令')
        return
    
    # 检查是否在群组
    if chat_type not in ['group', 'supergroup']:
        await update.message.reply_text('此命令只能在群组中使用')
        return
    
    # 解析命令
    args = context.args
    if not args or args[0] not in ['off', 'start']:
        await update.message.reply_text('使用方法：/config off 或 /config start')
        return
    
    action = args[0]
    chat_id = str(update.effective_chat.id)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 插入或更新群组配置
        cursor.execute('''
        INSERT INTO group_configs (group_id, is_enabled) 
        VALUES (%s, %s) 
        ON DUPLICATE KEY UPDATE is_enabled = %s
        ''', (chat_id, action == 'start', action == 'start'))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        try:
            await update.message.reply_text(f'机器人在本群组已{"启用" if action == "start" else "禁用"}')
        except Exception as reply_error:
            print(f'发送回复消息错误: {reply_error}')
    
    except Exception as e:
        print(f'配置错误: {e}')
        try:
            await update.message.reply_text('更新配置失败')
        except Exception as reply_error:
            print(f'发送错误消息错误: {reply_error}')

# 管理员管理命令
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 检查是否是拥有者
    if str(user_id) != OWNER_ID:
        await update.message.reply_text('只有机器人拥有者可以运行此命令')
        return
    
    # 解析命令
    args = context.args
    if len(args) < 2:
        await update.message.reply_text('使用方法：/admin add [用户ID] 或 /admin remove [用户ID]')
        return
    
    action = args[0]
    target_user_id = args[1]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if action == 'add':
            try:
                cursor.execute('INSERT INTO admins (user_id) VALUES (%s)', (target_user_id,))
                conn.commit()
                try:
                    await update.message.reply_text(f'管理员 {target_user_id} 添加成功')
                except Exception as reply_error:
                    print(f'发送回复消息错误: {reply_error}')
            except pymysql.IntegrityError:
                try:
                    await update.message.reply_text('添加管理员失败：该用户已存在')
                except Exception as reply_error:
                    print(f'发送回复消息错误: {reply_error}')
        
        elif action == 'remove':
            cursor.execute('DELETE FROM admins WHERE user_id = %s', (target_user_id,))
            conn.commit()
            if cursor.rowcount > 0:
                try:
                    await update.message.reply_text(f'管理员 {target_user_id} 移除成功')
                except Exception as reply_error:
                    print(f'发送回复消息错误: {reply_error}')
            else:
                try:
                    await update.message.reply_text('移除管理员失败：该用户不是管理员')
                except Exception as reply_error:
                    print(f'发送回复消息错误: {reply_error}')
        
        else:
            try:
                await update.message.reply_text('使用方法：/admin add [用户ID] 或 /admin remove [用户ID]')
            except Exception as reply_error:
                print(f'发送回复消息错误: {reply_error}')
        
        cursor.close()
        conn.close()
    
    except Exception as e:
        print(f'管理员管理错误: {e}')
        try:
            await update.message.reply_text('操作失败')
        except Exception as reply_error:
            print(f'发送错误消息错误: {reply_error}')

# 全局开关命令
async def global_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 检查是否是拥有者
    if str(user_id) != OWNER_ID:
        await update.message.reply_text('只有机器人拥有者可以运行此命令')
        return
    
    # 解析命令
    command = update.message.text
    is_enabled = command == '/on'
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 更新全局状态
        cursor.execute('''
        INSERT INTO bot_configs (is_global_enabled) 
        VALUES (%s) 
        ON DUPLICATE KEY UPDATE is_global_enabled = %s
        ''', (is_enabled, is_enabled))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        try:
            await update.message.reply_text(f'机器人已{"全局启用" if is_enabled else "全局禁用"}')
        except Exception as reply_error:
            print(f'发送回复消息错误: {reply_error}')
    
    except Exception as e:
        print(f'全局开关错误: {e}')
        try:
            await update.message.reply_text('切换全局状态失败')
        except Exception as reply_error:
            print(f'发送错误消息错误: {reply_error}')

# 主函数
def main():
    # 检查环境变量
    print(f"BOT_TOKEN: {'已设置' if BOT_TOKEN else '未设置'}")
    print(f"DB_HOST: {DB_HOST}")
    print(f"DB_PORT: {DB_PORT}")
    print(f"DB_USER: {DB_USER}")
    print(f"DB_NAME: {DB_NAME}")
    print(f"OWNER_ID: {OWNER_ID}")
    
    # 初始化数据库
    init_database()
    
    # 测试数据库连接
    try:
        conn = get_db_connection()
        print('数据库连接成功')
        conn.close()
    except Exception as e:
        print(f'数据库连接测试失败: {e}')
    
    # 创建应用
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 添加命令处理器
    application.add_handler(CommandHandler('install', install))
    application.add_handler(CommandHandler('config', config))
    application.add_handler(CommandHandler('admin', admin))
    application.add_handler(CommandHandler('on', global_toggle))
    application.add_handler(CommandHandler('off', global_toggle))
    
    # 添加消息处理器，包括命令
    application.add_handler(MessageHandler(filters.TEXT, handle_text))
    
    # 启动机器人
    print('Bot started')
    application.run_polling()

if __name__ == '__main__':
    main()