from curl_cffi import requests
from dotenv import load_dotenv
import os
import logging
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
from datetime import datetime

# 加载 .env 文件
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'suburl_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

AIRPORTS_PATH = 'config/airpots.json'

def get_subscription_from_airport(airport_url, user_agent, cookie):
    """
    通过 cookie 登录机场并获取订阅链接
    """
    try:
        logger.info(f"正在访问机场: {airport_url}")
        
        # 构建请求头
        headers = {
            "User-Agent": user_agent or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        
        # 解析 cookie 字符串为字典
        cookies = parse_cookie_string(cookie)
        
        # 发起请求
        resp = requests.get(
            airport_url,
            headers=headers,
            cookies=cookies,
            impersonate="chrome120",
            timeout=15
        )
        
        logger.info(f"响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            logger.info(f"✅ {airport_url} 登录成功！")
            
            # 提取订阅链接
            subscription_url = extract_url_re(resp.text, 'clash')
            
            if subscription_url:
                logger.info(f"找到订阅链接: {subscription_url}")
                return subscription_url
            else:
                logger.warning(f"未找到订阅链接，尝试其他方式...")
                # 尝试其他提取方式
                subscription_url = extract_subscription_url(resp.text, airport_url)
                if subscription_url:
                    logger.info(f"找到订阅链接: {subscription_url}")
                    return subscription_url
                logger.error(f"未能找到任何订阅链接")
                return None
        else:
            logger.error(f"❌ {airport_url} 登录失败，状态码：{resp.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ {airport_url} 登录失败，错误信息：{e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def parse_cookie_string(cookie_str):
    """将字符串格式的 Cookie 转换为字典格式"""
    if not cookie_str:
        return {}
    return {
        item.split('=')[0].strip(): item.split('=')[1].strip() 
        for item in cookie_str.split(';') if '=' in item
    }

def extract_url_re(html_content, sub_pattern):
    """匹配 value=" 后面直到 ?mu=pattern 的内容"""
    pattern = rf'value="(https?://[^"]+\?mu={sub_pattern})"'
    match = re.search(pattern, html_content)
    
    if match:
        return match.group(1)
    return None

def extract_subscription_url(html_content, base_url):
    """
    从 HTML 内容中提取订阅链接，支持多种格式
    """
    # 方法1: 匹配通用 URL 模式
    pattern1 = r'https?://[^\s<>"\']+(?:/link/|/subscribe|/sub)[^\s<>"\']*'
    match = re.search(pattern1, html_content)
    if match:
        return match.group(0)
    
    # 方法2: 匹配 href 属性中的订阅链接
    pattern2 = r'href="(https?://[^"]+)"'
    for match in re.finditer(pattern2, html_content):
        url = match.group(1)
        if any(keyword in url.lower() for keyword in ['link', 'subscribe', 'sub']):
            return url
    
    # 方法3: 使用 BeautifulSoup 解析
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找包含订阅关键词的链接
        for link in soup.find_all('a', href=True):
            href = link['href']
            if any(keyword in href.lower() for keyword in ['link', 'subscribe', 'sub']):
                if href.startswith('/'):
                    href = urljoin(base_url, href)
                if href.startswith('http'):
                    return href
                
    except Exception as e:
        logger.warning(f"BeautifulSoup 解析失败: {e}")
    
    return None

def process_airports():
    """处理所有机场配置"""
    # 加载json文件
    if not os.path.exists(AIRPORTS_PATH):
        logger.error(f"机场配置文件不存在: {AIRPORTS_PATH}")
        return
        
    with open(AIRPORTS_PATH, 'r', encoding='utf-8') as f:
        try:
            airports = json.load(f)
            if not isinstance(airports, list):
                logger.error("机场配置格式错误，应为 JSON 数组")
                return
        except json.JSONDecodeError as e:
            logger.error(f"解析机场配置文件失败: {e}")
            return
    
    logger.info(f"共配置了 {len(airports)} 个机场")
    logger.info("=" * 50)
    
    # 遍历每个机场
    for airport in airports:
        if not airport.get('active', True):
            logger.info(f"跳过未激活的机场: {airport.get('name', '未知机场')}")
            continue
            
        airport_name = airport.get('name', '未知机场')
        airport_url = airport.get('url')
        user_agent = airport.get('user_agent', '')
        cookie = airport.get('cookie', '')
        
        if not airport_url or not cookie:
            logger.error(f"机场 {airport_name} 配置缺少 URL 或 Cookie")
            continue
        
        logger.info(f"处理机场: {airport_name}")
        try:
            subscription_link = get_subscription_from_airport(airport_url, user_agent, cookie)
            if subscription_link:
                logger.info(f"✅ {airport_name} 成功获取订阅链接")
            else:
                logger.error(f"❌ {airport_name} 未找到订阅链接")
        except Exception as e:
            logger.error(f"❌ {airport_name} 获取订阅链接失败: {e}")
        
        logger.info("=" * 50)

if __name__ == "__main__":
    process_airports()