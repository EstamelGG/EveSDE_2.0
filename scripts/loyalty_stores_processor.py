#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
忠诚点商店数据处理器模块
用于从ESI API获取所有NPC军团的LP商店数据并存储到数据库

数据来源：
- 军团列表: https://esi.evetech.net/corporations/npccorps
- LP商店数据: https://esi.evetech.net/loyalty/stores/{corporation_id}/offers
"""

import json
import sqlite3
import time
import requests
import urllib3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class LoyaltyStoresProcessor:
    """忠诚点商店数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化LP商店处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en", "zh"])
        
        # ESI API基础URL
        self.esi_base_url = "https://esi.evetech.net"
        self.npccorps_url = f"{self.esi_base_url}/corporations/npccorps"
        
        # 请求配置
        self.max_retries = 5
        self.request_timeout = 30
        self.retry_delay = 1.0
        
        # 统计数据
        self.stats = {
            "total_corporations": 0,
            "processed_corporations": 0,
            "failed_corporations": 0,
            "total_offers": 0,
            "total_required_items": 0
        }
    
    def fetch_with_retry(self, url: str, max_retries: Optional[int] = None) -> Optional[Any]:
        """
        带重试机制的API请求
        
        Args:
            url: 请求的URL
            max_retries: 最大重试次数，默认使用self.max_retries
        
        Returns:
            响应数据（JSON），失败返回None
        """
        if max_retries is None:
            max_retries = self.max_retries
        
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    timeout=self.request_timeout,
                    verify=False,
                    headers={"User-Agent": "EveSDE_2.0/1.0"}
                )
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"    [-] 请求超时，{wait_time:.1f}秒后重试 ({attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"    [x] 请求超时，已达到最大重试次数")
                    return None
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    # 404表示该军团没有LP商店，这是正常的
                    return None
                elif e.response.status_code == 429:
                    # 429表示请求过多，需要等待
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    print(f"    [!] 请求频率限制，等待 {retry_after} 秒...")
                    time.sleep(retry_after)
                    continue
                elif attempt < max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"    [-] HTTP错误 {e.response.status_code}，{wait_time:.1f}秒后重试 ({attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"    [x] HTTP错误 {e.response.status_code}，已达到最大重试次数")
                    return None
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"    [-] 请求失败: {str(e)}，{wait_time:.1f}秒后重试 ({attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"    [x] 请求失败: {str(e)}，已达到最大重试次数")
                    return None
        
        return None
    
    def fetch_npc_corporations(self) -> List[int]:
        """
        获取所有NPC军团ID列表
        
        Returns:
            NPC军团ID列表
        """
        print(f"[+] 获取NPC军团列表: {self.npccorps_url}")
        
        corporations = self.fetch_with_retry(self.npccorps_url)
        
        if corporations is None:
            print("[x] 获取NPC军团列表失败")
            return []
        
        if not isinstance(corporations, list):
            print("[x] NPC军团列表格式错误")
            return []
        
        print(f"[+] 获取到 {len(corporations)} 个NPC军团")
        self.stats["total_corporations"] = len(corporations)
        return corporations
    
    def fetch_loyalty_offers(self, corporation_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        获取指定军团的LP商店数据
        
        Args:
            corporation_id: 军团ID
        
        Returns:
            LP商店offer列表，失败返回None
        """
        url = f"{self.esi_base_url}/loyalty/stores/{corporation_id}/offers"
        return self.fetch_with_retry(url)
    
    def create_tables(self, cursor: sqlite3.Cursor):
        """
        创建数据库表结构
        
        Args:
            cursor: 数据库游标
        """
        # 1. 创建忠诚点商店表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loyalty_stores (
                store_id INTEGER PRIMARY KEY,
                corporation_id INTEGER,
                store_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. 创建忠诚点商店商品表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loyalty_offers (
                offer_id INTEGER PRIMARY KEY,
                store_id INTEGER NOT NULL,
                type_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                isk_cost INTEGER NOT NULL DEFAULT 0,
                lp_cost INTEGER NOT NULL DEFAULT 0,
                ak_cost INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (store_id) REFERENCES loyalty_stores(store_id) ON DELETE CASCADE
            )
        ''')
        
        # 3. 创建忠诚点商店商品所需物品表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loyalty_offer_required_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id INTEGER NOT NULL,
                required_type_id INTEGER NOT NULL,
                required_quantity INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (offer_id) REFERENCES loyalty_offers(offer_id) ON DELETE CASCADE
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offers_store_id 
            ON loyalty_offers(store_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offers_type_id 
            ON loyalty_offers(type_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offers_lp_cost 
            ON loyalty_offers(lp_cost)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offer_required_items_offer_id 
            ON loyalty_offer_required_items(offer_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offer_required_items_type_id 
            ON loyalty_offer_required_items(required_type_id)
        ''')
        
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_loyalty_offer_required_items_unique 
            ON loyalty_offer_required_items(offer_id, required_type_id)
        ''')
        
        print("[+] 数据库表结构创建完成")
    
    def clear_existing_data(self, cursor: sqlite3.Cursor):
        """
        清空现有数据
        
        Args:
            cursor: 数据库游标
        """
        print("[+] 清空现有数据...")
        cursor.execute('DELETE FROM loyalty_offer_required_items')
        cursor.execute('DELETE FROM loyalty_offers')
        cursor.execute('DELETE FROM loyalty_stores')
        print("[+] 数据清空完成")
    
    def process_corporation_offers(
        self, 
        cursor: sqlite3.Cursor, 
        corporation_id: int
    ) -> bool:
        """
        处理单个军团的LP商店数据
        
        Args:
            cursor: 数据库游标
            corporation_id: 军团ID
        
        Returns:
            处理是否成功
        """
        offers = self.fetch_loyalty_offers(corporation_id)
        
        # 如果返回None，可能是404（没有LP商店）或其他错误
        if offers is None:
            # 404是正常的，不是所有军团都有LP商店
            return False
        
        if not isinstance(offers, list) or len(offers) == 0:
            # 空列表表示该军团没有LP商店
            return False
        
        # 插入商店记录
        cursor.execute('''
            INSERT OR REPLACE INTO loyalty_stores 
            (store_id, corporation_id, updated_at)
            VALUES (?, ?, ?)
        ''', (corporation_id, corporation_id, datetime.now().isoformat()))
        
        # 批量插入offer数据
        offers_batch = []
        required_items_batch = []
        
        for offer in offers:
            offer_id = offer.get('offer_id')
            type_id = offer.get('type_id')
            quantity = offer.get('quantity', 1)
            isk_cost = offer.get('isk_cost', 0)
            lp_cost = offer.get('lp_cost', 0)
            ak_cost = offer.get('ak_cost', 0)
            required_items = offer.get('required_items', [])
            
            # 准备offer数据
            offers_batch.append((
                offer_id,
                corporation_id,
                type_id,
                quantity,
                isk_cost,
                lp_cost,
                ak_cost,
                datetime.now().isoformat()
            ))
            
            # 准备required_items数据
            for req_item in required_items:
                required_type_id = req_item.get('type_id')
                required_quantity = req_item.get('quantity', 1)
                required_items_batch.append((
                    offer_id,
                    required_type_id,
                    required_quantity
                ))
        
        # 批量插入offers
        if offers_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO loyalty_offers
                (offer_id, store_id, type_id, quantity, isk_cost, lp_cost, ak_cost, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', offers_batch)
            self.stats["total_offers"] += len(offers_batch)
        
        # 批量插入required_items
        if required_items_batch:
            # 先删除该offer的旧required_items，避免重复
            offer_ids = list(set([item[0] for item in required_items_batch]))
            for offer_id in offer_ids:
                cursor.execute('''
                    DELETE FROM loyalty_offer_required_items 
                    WHERE offer_id = ?
                ''', (offer_id,))
            
            cursor.executemany('''
                INSERT INTO loyalty_offer_required_items
                (offer_id, required_type_id, required_quantity)
                VALUES (?, ?, ?)
            ''', required_items_batch)
            self.stats["total_required_items"] += len(required_items_batch)
        
        return True
    
    def process_all_corporations(self, cursor: sqlite3.Cursor):
        """
        处理所有NPC军团的LP商店数据
        
        Args:
            cursor: 数据库游标
        """
        print("[+] 开始获取所有NPC军团...")
        corporations = self.fetch_npc_corporations()
        
        if not corporations:
            print("[x] 没有获取到NPC军团列表，无法继续处理")
            return
        
        print(f"[+] 开始处理 {len(corporations)} 个军团的LP商店数据...")
        print(f"[+] 注意：不是所有军团都有LP商店，404错误是正常的")
        
        start_time = time.time()
        
        for idx, corporation_id in enumerate(corporations, 1):
            print(f"[{idx}/{len(corporations)}] 处理军团 {corporation_id}...", end=" ")
            
            success = self.process_corporation_offers(cursor, corporation_id)
            
            if success:
                print("✓ 成功")
                self.stats["processed_corporations"] += 1
            else:
                print("✗ 跳过（无LP商店）")
                self.stats["failed_corporations"] += 1
            
            # 每10个请求后稍作延迟，避免触发频率限制
            if idx % 10 == 0:
                time.sleep(0.5)
        
        elapsed_time = time.time() - start_time
        print(f"\n[+] 处理完成，耗时: {elapsed_time:.2f} 秒")
    
    def update_all_databases(self, config: Dict[str, Any]):
        """
        更新所有语言的数据库
        
        Args:
            config: 配置字典
        """
        print("[+] 开始处理LP商店数据...")
        print(f"[+] 支持语言: {', '.join(self.languages)}")
        
        # 为每种语言创建数据库并处理数据
        for lang in self.languages:
            db_filename = self.db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                # 确保数据库目录存在
                self.db_output_path.mkdir(parents=True, exist_ok=True)
                
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 创建表结构
                self.create_tables(cursor)
                
                # 清空现有数据
                self.clear_existing_data(cursor)
                
                # 处理所有军团数据
                self.process_all_corporations(cursor)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                print(f"    - 总军团数: {self.stats['total_corporations']}")
                print(f"    - 有LP商店的军团: {self.stats['processed_corporations']}")
                print(f"    - 无LP商店的军团: {self.stats['failed_corporations']}")
                print(f"    - 总offer数: {self.stats['total_offers']}")
                print(f"    - 总required_items数: {self.stats['total_required_items']}")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")
                import traceback
                traceback.print_exc()


def main(config=None):
    """主函数"""
    print("[+] LP商店数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = LoyaltyStoresProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] LP商店数据处理器完成")


if __name__ == "__main__":
    main()

