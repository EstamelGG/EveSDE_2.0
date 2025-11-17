#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPC船只分类处理器模块
用于处理types表中的NPC船只分类字段

功能: 在types_processor之后，专门处理npc_ship_scene, npc_ship_faction, npc_ship_type, npc_ship_faction_icon字段
"""

import sqlite3
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# NPC船只场景映射
NPC_SHIP_SCENES = [
    {"en": "Asteroid ", "zh": "小行星带"},
    {"en": "Deadspace ", "zh": "死亡空间"},
    {"en": "FW ", "zh": "势力战争"},
    {"en": "Ghost Site ", "zh": "幽灵站点"},
    {"en": "Incursion ", "zh": "入侵"},
    {"en": "Mission ", "zh": "任务"},
    {"en": "Storyline ", "zh": "故事线"},
    {"en": "Abyssal ", "zh": "深渊"}
]

# NPC船只势力映射
NPC_SHIP_FACTIONS = [
    {"en": "Angel Cartel", "zh": "天使"},
    {"en": "Blood Raider", "zh": "血袭者"},
    {"en": "Guristas", "zh": "古斯塔斯"},
    {"en": "Mordu", "zh": "莫德团"},
    {"en": "Rogue Drone", "zh": "自由无人机"},
    {"en": "Sansha", "zh": "萨沙共和国"},
    {"en": "Serpentis", "zh": "天蛇"},
    {"en": "Overseer", "zh": "监察官"},
    {"en": "Sleeper", "zh": "冬眠者"},
    {"en": "Drifter", "zh": "流浪者"},
    {"en": "Amarr Empire", "zh": "艾玛帝国"},
    {"en": "Gallente Federation", "zh": "盖伦特联邦"},
    {"en": "Minmatar Republic", "zh": "米玛塔尔共和国"},
    {"en": "Caldari State", "zh": "加达里合众国"},
    {"en": "CONCORD", "zh": "统合部"},
    {"en": "Faction", "zh": "势力特属"},
    {"en": "Generic", "zh": "任务通用"},
    {"en": "Khanid", "zh": "卡尼迪"},
    {"en": "Thukker", "zh": "图克尔"}
]

# NPC势力ICON映射
NPC_FACTION_ICON_MAP = {
    "Angel Cartel": "faction_500011.png",
    "Blood Raider": "faction_500012.png",
    "Guristas": "faction_500010.png",
    "Mordu": "faction_500018.png",
    "Rogue Drone": "faction_500025.png",
    "Sansha": "faction_500019.png",
    "Serpentis": "faction_500020.png",
    "Overseer": "faction_500021.png",  # 使用默认图标
    "Sleeper": "faction_500005.png",
    "Drifter": "faction_500024.png",
    "Amarr Empire": "faction_500003.png",
    "Gallente Federation": "faction_500004.png",
    "Minmatar Republic": "faction_500002.png",
    "Caldari State": "faction_500001.png",
    "CONCORD": "faction_500006.png",
    "Faction": "faction_500021.png",  # 使用默认图标
    "Generic": "faction_500021.png",  # 使用默认图标
    "Other": "faction_500021.png",  # 使用默认图标
    "Khanid": "faction_500008.png",
    "Thukker": "faction_500015.png"
}

# NPC船只类型映射
NPC_SHIP_TYPES = [
    {"en": " Frigate", "zh": "护卫舰"},
    {"en": " Destroyer", "zh": "驱逐舰"},
    {"en": " Battlecruiser", "zh": "战列巡洋舰"},
    {"en": " Cruiser", "zh": "巡洋舰"},
    {"en": " Battleship", "zh": "战列舰"},
    {"en": " Hauler", "zh": "运输舰"},
    {"en": " Transports", "zh": "运输舰"},
    {"en": " Dreadnought", "zh": "无畏舰"},
    {"en": " Titan", "zh": "泰坦"},
    {"en": " Supercarrier", "zh": "超级航母"},
    {"en": " Carrier", "zh": "航空母舰"},
    {"en": " Officer", "zh": "官员"},
    {"en": " Sentry", "zh": "岗哨"},
    {"en": " Drone", "zh": "无人机"}
]

# 全局缓存（用于跨语言共享分类结果）
npc_classification_cache = {}


class NPCShipClassifier:
    """NPC船只分类处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化NPC船只分类处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        self.brackets_data = None  # 缓存 brackets_output.json 数据
    
    def get_npc_ship_scene(self, group_name: str, lang: str) -> Optional[str]:
        """
        获取NPC船只场景
        """
        for scene in NPC_SHIP_SCENES:
            if group_name.startswith(scene["en"]):
                if scene["en"].strip() == "FW":
                    return "Faction Warfare" if lang == "en" else "势力战争"
                return scene[lang].strip()
        return "Other" if lang == "en" else "其他"
    
    def get_npc_ship_faction(self, group_name: str, lang: str) -> Optional[str]:
        """
        获取NPC船只势力
        """
        for faction in NPC_SHIP_FACTIONS:
            if faction["en"] in group_name:
                return faction[lang].strip()
        return "Other" if lang == "en" else "其他"
    
    def get_faction_icon(self, faction_name: str) -> Optional[str]:
        """
        获取势力图标
        """
        return NPC_FACTION_ICON_MAP.get(faction_name, "faction_500021.png")
    
    def load_brackets_data(self) -> bool:
        """
        加载 brackets_output.json 数据
        如果文件不存在，尝试执行 parse_brackets_standalone.py 生成
        """
        brackets_output_path = self.project_root / "brackets_decode" / "brackets_output.json"
        
        # 如果文件不存在，尝试执行脚本生成
        if not brackets_output_path.exists():
            print("[+] brackets_output.json 不存在，尝试执行 parse_brackets_standalone.py...")
            try:
                script_path = self.project_root / "brackets_decode" / "parse_brackets_standalone.py"
                if script_path.exists():
                    result = subprocess.run(
                        ["python", str(script_path)],
                        cwd=str(self.project_root / "brackets_decode"),
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    if result.returncode != 0:
                        print(f"[!] 执行 parse_brackets_standalone.py 失败: {result.stderr}")
                        return False
                    print("[+] parse_brackets_standalone.py 执行完成")
                else:
                    print(f"[!] 找不到 parse_brackets_standalone.py: {script_path}")
                    return False
            except Exception as e:
                print(f"[!] 执行 parse_brackets_standalone.py 时出错: {e}")
                return False
        
        # 读取 brackets_output.json
        try:
            with open(brackets_output_path, 'r', encoding='utf-8') as f:
                self.brackets_data = json.load(f)
            print("[+] 成功加载 brackets_output.json")
            return True
        except Exception as e:
            print(f"[!] 读取 brackets_output.json 失败: {e}")
            self.brackets_data = None
            return False
    
    def get_bracket_name_from_brackets_data(self, type_id: int, group_id: int, category_id: int) -> Optional[str]:
        """
        从 brackets_data 中获取 name
        优先级：bracketsByType -> bracketsByGroup -> bracketsByCategory
        """
        if not self.brackets_data:
            return None
        
        try:
            # 方法1: 从 bracketsByType 查找
            brackets_by_type = self.brackets_data.get('bracketsByType', {})
            type_id_str = str(type_id)
            if type_id_str in brackets_by_type:
                bracket_info = brackets_by_type[type_id_str]
                if isinstance(bracket_info, dict):
                    name = bracket_info.get('name', '')
                    if name:
                        return name
            
            # 方法2: 从 bracketsByGroup 查找
            brackets_by_group = self.brackets_data.get('bracketsByGroup', {})
            group_id_str = str(group_id)
            if group_id_str in brackets_by_group:
                bracket_info = brackets_by_group[group_id_str]
                if isinstance(bracket_info, dict):
                    name = bracket_info.get('name', '')
                    if name:
                        return name
            
            # 方法3: 从 bracketsByCategory 查找
            brackets_by_category = self.brackets_data.get('bracketsByCategory', {})
            category_id_str = str(category_id)
            if category_id_str in brackets_by_category:
                bracket_info = brackets_by_category[category_id_str]
                if isinstance(bracket_info, dict):
                    name = bracket_info.get('name', '')
                    if name:
                        return name
            
            return None
        except Exception as e:
            # 如果解析失败，返回 None
            return None
    
    def classify_ship_type_from_name(self, name: str, lang: str) -> Optional[str]:
        """
        根据 name 使用 NPC_SHIP_TYPES 进行分类
        特殊处理 "Super Carrier" -> Supercarrier/超级航母
        """
        if not name:
            return None
        
        # 特殊处理 "Super Carrier"
        if name == "Super Carrier":
            return "Supercarrier" if lang == "en" else "超级航母"
        
        # 使用 NPC_SHIP_TYPES 匹配
        for ship_type in NPC_SHIP_TYPES:
            if name.endswith(ship_type["en"]) or name == ship_type["en"].strip():
                return ship_type[lang].strip()
        
        return None
    
    def get_npc_ship_type_method2(self, cursor: sqlite3.Cursor, type_id: int, lang: str) -> Optional[str]:
        """
        方法2: 根据属性1766获取型号group_id，然后从groups表查询
        """
        try:
            cursor.execute('''
                SELECT value
                FROM typeAttributes
                WHERE type_id = ? AND attribute_id = 1766
            ''', (type_id,))
            
            result = cursor.fetchone()
            if result and result[0] is not None:
                model_group_id = int(result[0])
                
                # 从groups表查询对应语言的名称
                lang_column = f"{lang}_name" if lang in ['de', 'en', 'es', 'fr', 'ja', 'ko', 'ru', 'zh'] else 'en_name'
                cursor.execute(f'''
                    SELECT {lang_column}
                    FROM groups
                    WHERE group_id = ?
                ''', (model_group_id,))
                
                group_result = cursor.fetchone()
                if group_result and group_result[0]:
                    return group_result[0].strip()
        except Exception as e:
            pass
        
        return None
    
    def get_npc_ship_type_method3(self, cursor: sqlite3.Cursor, type_id: int, group_id: int, category_id: int, lang: str) -> Optional[str]:
        """
        方法3: 从 brackets_output.json 中查找 name，然后使用 NPC_SHIP_TYPES 分类
        """
        if not self.brackets_data:
            return None
        
        try:
            # 从 brackets_data 中获取 name
            bracket_name = self.get_bracket_name_from_brackets_data(type_id, group_id, category_id)
            if bracket_name:
                # 使用 name 进行分类
                return self.classify_ship_type_from_name(bracket_name, lang)
        except Exception as e:
            pass
        
        return None
    
    def get_npc_ship_type_method1(self, group_name: str, name: str, lang: str) -> Optional[str]:
        """
        方法1: 使用字符串匹配映射（兜底方法）
        """
        # 首先检查组名是否以Officer结尾
        if group_name.endswith("Officer"):
            return "Officer" if lang == "en" else "官员"
        
        # 使用字符串匹配映射
        for ship_type in NPC_SHIP_TYPES:
            if name.endswith(ship_type["en"]) or group_name.endswith(ship_type["en"]):
                return ship_type[lang].strip()
        
        return None
    
    def get_npc_ship_type(self, cursor: sqlite3.Cursor, type_id: int, group_name: str, name: str, group_id: int, category_id: int, lang: str) -> Optional[str]:
        """
        获取NPC船只类型
        优先级：方法2（属性1766）-> 方法3（brackets_output）-> 方法1（字符串匹配）
        """
        # 方法2: 根据属性1766获取型号group_id
        result = self.get_npc_ship_type_method2(cursor, type_id, lang)
        if result:
            return result
        
        # 方法3: 从 brackets_output.json 中查找
        result = self.get_npc_ship_type_method3(cursor, type_id, group_id, category_id, lang)
        if result:
            return result
        
        # 方法1: 使用字符串匹配映射（兜底）
        result = self.get_npc_ship_type_method1(group_name, name, lang)
        if result:
            return result
        
        # 全部失败，返回 Other
        return "Other" if lang == "en" else "其他"
    
    def classify_npc_ships_for_language(self, language: str) -> bool:
        """
        为指定语言分类NPC船只
        """
        print(f"[+] 开始分类NPC船只，语言: {language}")
        
        # 数据库文件路径
        db_path = self.db_output_path / f"item_db_{language}.sqlite"
        
        if not db_path.exists():
            print(f"[!] 数据库文件不存在: {db_path}")
            return False
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 加载 brackets_output.json 数据（仅在英文数据库时加载一次）
            if language == 'en':
                self.load_brackets_data()
            
            # 获取所有categoryID为11的NPC船只（categoryID=11表示Ship）
            cursor.execute('''
                SELECT type_id, en_name, group_name, categoryID, groupID
                FROM types
                WHERE categoryID = 11
            ''')
            
            npc_ships = cursor.fetchall()
            print(f"[+] 找到 {len(npc_ships)} 个NPC船只需要分类")
            
            # 如果是英文数据库，处理并缓存分类结果
            if language == 'en':
                npc_classification_cache.clear()
                update_batch = []
                batch_size = 1000
                
                for type_id, en_name, group_name, category_id, group_id in npc_ships:
                    # 计算分类
                    npc_ship_scene_en = self.get_npc_ship_scene(group_name, 'en')
                    npc_ship_scene_zh = self.get_npc_ship_scene(group_name, 'zh')
                    npc_ship_faction_en = self.get_npc_ship_faction(group_name, 'en')
                    npc_ship_faction_zh = self.get_npc_ship_faction(group_name, 'zh')
                    npc_ship_type_en = self.get_npc_ship_type(cursor, type_id, group_name, en_name, group_id, category_id, 'en')
                    npc_ship_type_zh = self.get_npc_ship_type(cursor, type_id, group_name, en_name, group_id, category_id, 'zh')
                    npc_ship_faction_icon = self.get_faction_icon(npc_ship_faction_en)
                    
                    # 保存到缓存
                    npc_classification_cache[type_id] = {
                        'scene': {'en': npc_ship_scene_en, 'zh': npc_ship_scene_zh},
                        'faction': {'en': npc_ship_faction_en, 'zh': npc_ship_faction_zh},
                        'type': {'en': npc_ship_type_en, 'zh': npc_ship_type_zh},
                        'faction_icon': npc_ship_faction_icon
                    }
                    
                    # 添加到更新批次（使用英文版本）
                    update_batch.append((
                        npc_ship_scene_en,
                        npc_ship_faction_en,
                        npc_ship_type_en,
                        npc_ship_faction_icon,
                        type_id
                    ))
                    
                    # 批量更新
                    if len(update_batch) >= batch_size:
                        cursor.executemany('''
                            UPDATE types
                            SET npc_ship_scene = ?,
                                npc_ship_faction = ?,
                                npc_ship_type = ?,
                                npc_ship_faction_icon = ?
                            WHERE type_id = ?
                        ''', update_batch)
                        update_batch = []
                
                # 处理剩余的数据
                if update_batch:
                    cursor.executemany('''
                        UPDATE types
                        SET npc_ship_scene = ?,
                            npc_ship_faction = ?,
                            npc_ship_type = ?,
                            npc_ship_faction_icon = ?
                        WHERE type_id = ?
                    ''', update_batch)
                
                print(f"[+] 英文数据库：成功分类 {len(npc_ships)} 个NPC船只")
                
            else:
                # 其他语言从缓存获取分类结果
                if not npc_classification_cache:
                    print("[!] 警告：缓存为空，请先处理英文数据库")
                    return False
                
                update_batch = []
                batch_size = 1000
                updated_count = 0
                
                for type_id, en_name, group_name, category_id, group_id in npc_ships:
                    if type_id in npc_classification_cache:
                        cached_data = npc_classification_cache[type_id]
                        
                        # 根据语言选择对应的值
                        if language == 'zh':
                            npc_ship_scene = cached_data['scene']['zh']
                            npc_ship_faction = cached_data['faction']['zh']
                            npc_ship_type = cached_data['type']['zh']
                        else:
                            # 其他语言使用英文版本
                            npc_ship_scene = cached_data['scene']['en']
                            npc_ship_faction = cached_data['faction']['en']
                            npc_ship_type = cached_data['type']['en']
                        
                        npc_ship_faction_icon = cached_data['faction_icon']
                        
                        # 添加到更新批次
                        update_batch.append((
                            npc_ship_scene,
                            npc_ship_faction,
                            npc_ship_type,
                            npc_ship_faction_icon,
                            type_id
                        ))
                        updated_count += 1
                        
                        # 批量更新
                        if len(update_batch) >= batch_size:
                            cursor.executemany('''
                                UPDATE types
                                SET npc_ship_scene = ?,
                                    npc_ship_faction = ?,
                                    npc_ship_type = ?,
                                    npc_ship_faction_icon = ?
                                WHERE type_id = ?
                            ''', update_batch)
                            update_batch = []
                
                # 处理剩余的数据
                if update_batch:
                    cursor.executemany('''
                        UPDATE types
                        SET npc_ship_scene = ?,
                            npc_ship_faction = ?,
                            npc_ship_type = ?,
                            npc_ship_faction_icon = ?
                        WHERE type_id = ?
                    ''', update_batch)
                
                print(f"[+] {language}数据库：成功分类 {updated_count} 个NPC船只")
            
            # 提交更改
            conn.commit()
            print(f"[+] NPC船只分类完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 分类NPC船只时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def classify_all_languages(self) -> bool:
        """
        为所有语言分类NPC船只
        """
        print("[+] 开始分类NPC船只")
        
        success_count = 0
        for language in self.languages:
            if self.classify_npc_ships_for_language(language):
                success_count += 1
        
        print(f"[+] NPC船只分类完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] NPC船只分类处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    classifier = NPCShipClassifier(config)
    classifier.classify_all_languages()
    
    print("\n[+] NPC船只分类处理器完成")


if __name__ == "__main__":
    main()

