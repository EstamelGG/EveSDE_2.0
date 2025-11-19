#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可压缩物品类型数据处理器模块
用于从网络获取物品压缩对照表数据并存储到数据库

对应old版本: old/main.py中的fetch_compressable函数
功能: 从外部URL下载可压缩物品数据，创建compressible_types表
数据源: https://sde.hoboleaks.space/tq/compressibletypes.json
"""

import json
import sqlite3
from pathlib import Path
from utils.http_client import get
from typing import Dict, List, Any, Optional


class CompressableTypesProcessor:
    """可压缩物品类型数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化可压缩物品类型处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        self.data_url = "https://sde.hoboleaks.space/tq/compressibletypes.json"
    
    def download_compressable_data(self) -> Dict[str, str]:
        """从网络获取可压缩物品数据"""
        print(f"[+] 正在从 {self.data_url} 获取可压缩物品数据...")
        
        try:
            response = get(self.data_url, timeout=30, verify=False)
            compressible_data = response.json()
            print(f"[+] 成功获取了 {len(compressible_data)} 条压缩对照数据")
            return compressible_data
            
        except Exception as e:
            print(f"[x] 网络请求失败: {e}")
            raise
        except json.JSONDecodeError as e:
            print(f"[x] JSON解析失败: {e}")
            raise
        except Exception as e:
            print(f"[x] 获取数据时发生未知错误: {e}")
            raise
    
    def create_compressible_types_table(self, cursor: sqlite3.Cursor):
        """创建compressible_types表"""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS compressible_types (
            origin INTEGER NOT NULL,
            compressed INTEGER NOT NULL,
            PRIMARY KEY (origin)
        )
        ''')
        print("[+] 创建compressible_types表")
    
    def process_compressable_data_to_db(self, compressible_data: Dict[str, str], cursor: sqlite3.Cursor, lang: str):
        """处理可压缩物品数据并写入数据库"""
        try:
            # 创建表
            self.create_compressible_types_table(cursor)
            
            # 清空现有数据（如果有的话）
            cursor.execute('DELETE FROM compressible_types')
            
            # 插入新数据
            insert_count = 0
            for origin_id, compressed_id in compressible_data.items():
                cursor.execute(
                    'INSERT INTO compressible_types (origin, compressed) VALUES (?, ?)',
                    (int(origin_id), int(compressed_id))
                )
                insert_count += 1
            
            print(f"[+] 数据库 {lang}: 已创建/更新 compressible_types 表，插入了 {insert_count} 条记录")
            
        except Exception as e:
            print(f"[x] 处理过程中出错: {str(e)}")
            raise
    
    def process_compressable_data_for_language(self, compressible_data: Dict[str, str], language: str) -> bool:
        """为指定语言处理可压缩物品数据"""
        print(f"[+] 开始处理可压缩物品数据，语言: {language}")
        
        # 数据库文件路径
        db_path = self.db_output_path / f"item_db_{language}.sqlite"
        
        if not db_path.exists():
            print(f"[!] 数据库文件不存在: {db_path}")
            return False
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 处理数据
            self.process_compressable_data_to_db(compressible_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] 可压缩物品数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理可压缩物品数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """为所有语言处理可压缩物品数据"""
        print("[+] 开始处理可压缩物品数据")
        
        # 下载数据
        compressible_data = self.download_compressable_data()
        
        success_count = 0
        for language in self.languages:
            if self.process_compressable_data_for_language(compressible_data, language):
                success_count += 1
        
        print(f"[+] 可压缩物品数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 可压缩物品类型数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = CompressableTypesProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 可压缩物品类型数据处理器完成")


if __name__ == "__main__":
    main()
