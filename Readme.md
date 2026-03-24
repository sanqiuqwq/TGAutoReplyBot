# Telegram自动回复机器人

一个Telegram的关键词自动回复机器人

**PS：程序AI写的，有点bug见谅(**

## 环境要求

Mysql 5.7
Python 3.13
(其他环境版本未经过测试，可能大概率是兼容的)

## 安装步骤

1. 克隆项目并安装依赖（建议从release下载）：

```bash
pip install -r requirements.txt
```

2. 配置环境变量：

```bash
vim .env
```

编辑 `.env` 文件，填入您的配置信息。

4. 运行主程序(建议使用进程守护)：
```bash
python app.py
```

5. 使用Owner的Telegram账户打开机器人私聊
输入:
/install
完成机器人配置

## Owner账户配置

在`.env`文件中配置，需要填入您Telegram的账户id(例如9456123000)


## 功能特性

### 权限控制
- **Owner（所有者）**：拥有机器人所有权限
- **Admin（管理员）**：可以设置关键词
- **普通用户**：仅可以触发管理员设置的关键词

### 关键词配置(仅Owner和Admin可用)

1. 发送
(你的机器人名字)学；关键词；机器人回复内容

**PS：关键词优先保留新设置的，优先匹配长关键词**

### 机器人命令说明
- **Owner（所有者）**：
1. /install 配置机器人
2. /admin add|remove userid 管理管理员用户

## 许可证

GNU General Public License v3.0 (GPL v3)
