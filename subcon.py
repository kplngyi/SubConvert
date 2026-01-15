import requests
import base64
import urllib.parse
import logging
from datetime import datetime
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re
import json

# 加载 .env 文件
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'subconvert_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 从环境变量读取配置
SUBCONVERT_URL = os.getenv('SUBCONVERT_URL', 'http://65.49.200.39:25500/sub')
AIRPORTS_JSON = os.getenv('AIRPORTS', '[]')
LOCAL_NODES = os.getenv('LOCAL_NODES', '')

def parse_airports_config():
    """
    解析机场配置
    """
    try:
        airports = json.loads(AIRPORTS_JSON)
        if not isinstance(airports, list):
            logger.error("AIRPORTS 配置格式错误，应为 JSON 数组")
            return []
        return airports
    except json.JSONDecodeError as e:
        logger.error(f"解析 AIRPORTS 配置失败: {e}")
        return []

def get_subscription_from_airport(airport_url, cookie):
    """
    通过 cookie 登录机场并获取订阅链接
    """
    try:
        logger.info(f"正在访问机场: {airport_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Cookie': cookie,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(airport_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 解析 HTML 寻找订阅链接
        soup = BeautifulSoup(response.text, 'html.parser')
        print(soup.prettify())
        raise Exception("Debugging stop")
        
        # 常见的订阅链接模式
        patterns = [
            r'https?://[^\s<>"]+/link/[^\s<>"?]+',
            r'https?://[^\s<>"]+subscribe[^\s<>"]*',
            r'https?://[^\s<>"]+sub[^\s<>"]*',
        ]
        
        subscription_url = None
        
        # 尝试从链接中查找
        for link in soup.find_all('a', href=True):
            href = link['href']
            for pattern in patterns:
                if re.search(pattern, href):
                    subscription_url = href
                    logger.info(f"找到订阅链接: {subscription_url}")
                    break
            if subscription_url:
                break
        
        # 如果没找到，尝试从页面文本中提取
        if not subscription_url:
            page_text = response.text
            for pattern in patterns:
                match = re.search(pattern, page_text)
                if match:
                    subscription_url = match.group(0)
                    logger.info(f"从页面文本中找到订阅链接: {subscription_url}")
                    break
        
        if not subscription_url:
            logger.error("未能在页面中找到订阅链接")
            return None
        
        return subscription_url
        
    except requests.RequestException as e:
        logger.error(f"访问机场失败: {e}")
        return None
    except Exception as e:
        logger.error(f"解析页面失败: {e}")
        return None

def get_subscription_content(sub_url):
    """
    获取订阅内容
    """
    try:
        logger.info(f"获取订阅内容: {sub_url}")
        response = requests.get(sub_url, timeout=30)
        response.raise_for_status()
        
        # 尝试解码订阅内容
        try:
            content = base64.b64decode(response.text).decode('utf-8')
            logger.info(f"成功解码订阅，节点数: {len(content.splitlines())}")
            return content
        except Exception:
            logger.info(f"订阅未编码，直接使用原始内容，节点数: {len(response.text.splitlines())}")
            return response.text
            
    except requests.RequestException as e:
        logger.error(f"获取订阅内容失败: {e}")
        return None

def merge_all_nodes(airports, local_nodes):
    """
    合并所有机场和本地节点
    """
    all_nodes = []
    
    # 添加本地节点
    if local_nodes:
        logger.info("\n添加本地节点...")
        # 支持用 | 分隔多个节点
        local_node_list = local_nodes.split('|')
        for node in local_node_list:
            node = node.strip()
            if node:
                all_nodes.append(node)
        logger.info(f"添加了 {len(local_node_list)} 个本地节点")
    
    # 遍历所有机场
    for airport in airports:
        name = airport.get('name', 'Unknown')
        url = airport.get('url')
        cookie = airport.get('cookie')
        
        if not url or not cookie:
            logger.warning(f"机场 {name} 配置不完整，跳过")
            continue
        
        logger.info(f"\n处理机场: {name}")
        logger.info("=" * 50)
        
        # 获取订阅链接
        sub_url = get_subscription_from_airport(url, cookie)
        if not sub_url:
            logger.warning(f"机场 {name} 获取订阅链接失败，跳过")
            continue
        
        # 获取订阅内容
        content = get_subscription_content(sub_url)
        if content:
            node_lines = [line.strip() for line in content.splitlines() if line.strip()]
            all_nodes.extend(node_lines)
            logger.info(f"机场 {name} 添加了 {len(node_lines)} 个节点")
        else:
            logger.warning(f"机场 {name} 获取订阅内容失败")
    
    return '\n'.join(all_nodes)

def generate_subconvert_url(subscription_content, output_format="clash"):
    """
    生成 SubConvert 转换链接
    """
    # Base64 编码订阅内容
    encoded_content = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')
    
    # 构建 SubConvert URL
    params = {
        'target': output_format,
        'url': encoded_content,
        'insert': 'false',
        'config': 'https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online.ini',
        'emoji': 'true',
        'list': 'false',
        'udp': 'true',
        'tfo': 'false',
        'scv': 'false',
        'fdn': 'false',
        'sort': 'false',
    }
    
    query_string = urllib.parse.urlencode(params)
    subconvert_url = f"{SUBCONVERT_URL}?{query_string}"
    
    return subconvert_url

def main():
    logger.info("=" * 50)
    logger.info("开始获取机场订阅...")
    logger.info("=" * 50)
    
    # 解析机场配置
    airports = parse_airports_config()
    
    if not airports and not LOCAL_NODES:
        logger.error("没有配置任何机场或本地节点")
        logger.info("\n请在 .env 文件中配置 AIRPORTS 或 LOCAL_NODES")
        return
    
    logger.info(f"\n共配置了 {len(airports)} 个机场")
    
    # 合并所有节点
    local_nodes = LOCAL_NODES.strip()
    merged_content = merge_all_nodes(airports, local_nodes)
    
    if not merged_content:
        logger.error("没有获取到任何节点")
        return
    
    total_nodes = len(merged_content.splitlines())
    logger.info(f"\n" + "=" * 50)
    logger.info(f"合并完成！总共 {total_nodes} 个节点")
    logger.info("=" * 50)
    
    # 生成 SubConvert 链接
    logger.info("\n生成 SubConvert 转换链接...")
    
    formats = {
        "clash": "Clash",
        "v2ray": "V2Ray",
        "surge": "Surge",
        "surfboard": "Surfboard"
    }
    
    logger.info("\n" + "=" * 50)
    for fmt, name in formats.items():
        url = generate_subconvert_url(merged_content, output_format=fmt)
        logger.info(f"{name}: {url}")
        logger.info("-" * 50)
    logger.info("=" * 50)

if __name__ == "__main__":
    main()