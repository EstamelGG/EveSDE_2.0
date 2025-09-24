#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPC公司处理器模块
处理EVE NPC公司数据并存储到数据库
"""

import json
import sqlite3
import time
import asyncio
import aiohttp
import os
from pathlib import Path
from typing import Dict, Any, List
import scripts.jsonl_loader as jsonl_loader


class NpcCorporationsProcessor:
    """EVE NPC公司处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化NPC公司处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        self.custom_icons_path = self.project_root / "custom_icons"
        
        # 确保自定义图标目录存在
        self.custom_icons_path.mkdir(parents=True, exist_ok=True)
        
        # 缓存数据
        self.corporations_data = {}
    
    def load_corporations_data(self):
        """加载NPC公司数据"""
        print("[+] 加载NPC公司数据...")
        
        # 加载NPC公司数据
        corporations_file = self.sde_input_path / "npcCorporations.jsonl"
        if corporations_file.exists():
            corporations_list = jsonl_loader.load_jsonl(str(corporations_file))
            self.corporations_data = {item['_key']: item for item in corporations_list}
            print(f"[+] 加载了 {len(self.corporations_data)} 个NPC公司")
        else:
            print(f"[x] NPC公司文件不存在: {corporations_file}")
    
    async def download_corporation_icon(self, corp_id: int, output_dir: Path, semaphore: asyncio.Semaphore, retry_count: int = 15) -> str:
        """下载单个军团图标，带有重试逻辑"""
        url = f"https://images.evetech.net/corporations/{corp_id}/logo?size=128"
        filename = f"corperation_{corp_id}_128.png"
        filepath = output_dir / filename
        
        # 如果文件已存在，直接返回文件名
        if filepath.exists():
            # print(f"[+] 图标已存在，跳过下载: {filename}")
            return filename
        
        async with semaphore:  # 使用信号量限制并发数
            for attempt in range(retry_count):
                try:
                    # 创建SSL上下文，忽略证书验证
                    ssl_context = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(connector=ssl_context) as session:
                        async with session.get(url, timeout=10) as response:
                            if response.status == 200:
                                content = await response.read()
                                with open(filepath, 'wb') as f:
                                    f.write(content)
                                print(f"[+] 成功下载图标: {url} -> {filename}")
                                return filename
                            else:
                                print(f"[-] 下载失败 (HTTP {response.status}): {filename}")
                except asyncio.TimeoutError:
                    print(f"[-] 超时 (尝试 {attempt + 1}/{retry_count}): {filename}")
                except Exception as e:
                    print(f"[-] 错误 (尝试 {attempt + 1}/{retry_count}): {filename} - {str(e)}")
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(1)  # 重试前等待1秒
        
        print(f"[x] 所有重试均失败: {filename}")
        return None
    
    async def download_all_corporation_icons(self, corp_ids: List[int], output_dir: Path) -> Dict[int, str]:
        """下载所有军团图标"""
        # 创建输出目录
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建信号量以限制并发请求数
        semaphore = asyncio.Semaphore(10)
        
        # 创建下载任务
        tasks = [
            self.download_corporation_icon(corp_id, output_dir, semaphore)
            for corp_id in corp_ids
        ]
        
        print(f"[+] 准备下载 {len(corp_ids)} 个军团图标...")
        
        # 异步执行所有下载任务
        results = await asyncio.gather(*tasks)
        
        # 返回结果字典
        return {corp_id: filename for corp_id, filename in zip(corp_ids, results) if filename}
    
    def create_npc_corporations_table(self, cursor: sqlite3.Cursor):
        """创建 npcCorporations 表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS npcCorporations (
                corporation_id INTEGER NOT NULL PRIMARY KEY,
                name TEXT,
                de_name TEXT,
                en_name TEXT,
                es_name TEXT,
                fr_name TEXT,
                ja_name TEXT,
                ko_name TEXT,
                ru_name TEXT,
                zh_name TEXT,
                description TEXT,
                faction_id INTEGER,
                icon_filename TEXT
            )
        ''')
        
        # 创建索引以优化查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_npcCorporations_faction_id ON npcCorporations(faction_id)')
    
    async def process_corporations_data_async(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """处理 npcCorporations 数据并插入数据库（异步版本）"""
        self.create_npc_corporations_table(cursor)
        
        # 获取所有军团ID
        corp_ids = list(self.corporations_data.keys())
        
        # 下载所有图标
        icon_filenames = await self.download_all_corporation_icons(corp_ids, self.custom_icons_path)
        
        # 用于存储批量插入的数据
        batch_data = []
        batch_size = 1000  # 每批处理的记录数
        
        for corp_id, corp_info in self.corporations_data.items():
            # 获取当前语言的名称作为主要name
            name_data = corp_info.get('name', {})
            name = name_data.get(lang, name_data.get('en', ''))
            
            # 获取所有语言的名称
            names = {
                'de': name_data.get('de', name),
                'en': name_data.get('en', name),
                'es': name_data.get('es', name),
                'fr': name_data.get('fr', name),
                'ja': name_data.get('ja', name),
                'ko': name_data.get('ko', name),
                'ru': name_data.get('ru', name),
                'zh': name_data.get('zh', name)
            }
            
            # 获取描述，如果没有对应语言的就用英文
            description_data = corp_info.get('description', {})
            description = description_data.get(lang, description_data.get('en', ''))
            
            # 获取其他信息
            faction_id = corp_info.get('factionID', 500021)
            
            # 获取图标文件名
            icon_filename = icon_filenames.get(corp_id, "corporations_default.png")
            
            # 添加到批处理列表
            batch_data.append((
                corp_id,
                name,
                names['de'],
                names['en'],
                names['es'],
                names['fr'],
                names['ja'],
                names['ko'],
                names['ru'],
                names['zh'],
                description,
                faction_id,
                icon_filename
            ))
            
            # 当达到批处理大小时执行插入
            if len(batch_data) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO npcCorporations (
                        corporation_id,
                        name,
                        de_name, en_name, es_name, fr_name,
                        ja_name, ko_name, ru_name, zh_name,
                        description,
                        faction_id,
                        icon_filename
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch_data)
                batch_data = []  # 清空批处理列表
        
        # 处理剩余的数据
        if batch_data:
            cursor.executemany('''
                INSERT OR REPLACE INTO npcCorporations (
                    corporation_id,
                    name,
                    de_name, en_name, es_name, fr_name,
                    ja_name, ko_name, ru_name, zh_name,
                    description,
                    faction_id,
                    icon_filename
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch_data)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM npcCorporations')
        corporations_count = cursor.fetchone()[0]
        print(f"[+] NPC公司数据处理完成: {corporations_count} 个")
    
    def process_corporations_data(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """处理YAML数据并写入数据库（同步包装器）"""
        # 运行异步版本
        asyncio.run(self.process_corporations_data_async(cursor, lang))
    
    def process_corporations_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理所有NPC公司数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理NPC公司数据 (语言: {lang})...")
        start_time = time.time()
        
        # 处理NPC公司数据
        self.process_corporations_data(cursor, lang)
        
        end_time = time.time()
        print(f"[+] NPC公司数据处理完成，耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载NPC公司数据
        self.load_corporations_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理NPC公司数据
                self.process_corporations_to_db(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] NPC公司处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = NpcCorporationsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] NPC公司处理器完成")


if __name__ == "__main__":
    main()
