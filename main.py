#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EVE SDE 处理器 - 主入口
用于处理EVE Online静态数据导出(SDE)的主程序
"""

import json
import sys
import os
import shutil
import argparse
import requests
import urllib3
from pathlib import Path
from datetime import datetime
# 导入SDE处理模块
import scripts.sde_downloader as sde_downloader
import scripts.jsonl_loader as jsonl_loader
import scripts.icons_downloader as icons_downloader
import scripts.icon_fetcher as icon_fetcher
import scripts.dynamic_items_updater as dynamic_items_updater
import scripts.universe_processor as universe_processor
import scripts.universe_names_processor as universe_names_processor
import scripts.dogma_effects_processor as dogma_effects_processor
import scripts.planet_schematics_processor as planet_schematics_processor
import scripts.categories_processor as categories_processor
import scripts.groups_processor as groups_processor
import scripts.metagroups_processor as metagroups_processor
import scripts.stations_processor as stations_processor
import scripts.factions_processor as factions_processor
import scripts.npcCorporations_processor as npcCorporations_processor
import scripts.agents_processor as agents_processor
import scripts.agent_localization_processor as agent_localization_processor
import scripts.divisions_processor as divisions_processor
import scripts.dogmaAttributeCategories_processor as dogmaAttributeCategories_processor
import scripts.dogmaAttributes_processor as dogmaAttributes_processor
import scripts.typeDogma_processor as typeDogma_processor
import scripts.types_processor as types_processor
import scripts.dbuffCollections_processor as dbuffCollections_processor
import scripts.marketGroups_processor as marketGroups_processor
import scripts.typeMaterials_processor as typeMaterials_processor
import scripts.blueprints_processor as blueprints_processor
import scripts.celestial_names_processor as celestial_names_processor
import scripts.skill_requirements_processor as skill_requirements_processor
import scripts.facility_rig_effects_processor as facility_rig_effects_processor
import scripts.dogma_effect_patch_processor as dogma_effect_patch_processor
import scripts.compressable_types_processor as compressable_types_processor
import scripts.compression_processor as compression_processor
import scripts.typeTraits_processor as typeTraits_processor
import scripts.update_categories_icons as update_categories_icons
import scripts.map_generator as map_generator
import scripts.version_info_processor as version_info_processor
import scripts.release_compare_processor as release_compare_processor
import clean
# 本地化处理通过调用localization/main.py完成


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='EVE SDE 处理器')
    parser.add_argument('--force-localization', action='store_true', 
                       help='强制重新解析本地化数据')
    parser.add_argument('--skip-localization', action='store_true',
                       help='跳过本地化数据解析')
    parser.add_argument('--force-rebuild', action='store_true',
                       help='强制重新构建，忽略版本检查')
    return parser.parse_args()

def get_latest_sde_info():
    """获取最新的SDE版本信息"""
    try:
        print("[+] 获取最新SDE版本信息...")
        release_source_url = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
        print(f"[+] URL: {release_source_url}")
        response = requests.get(release_source_url, timeout=10)
        response.raise_for_status()
        
        # 解析JSONL格式的数据
        data = json.loads(response.text.strip())
        
        return {
            'build_number': data.get('buildNumber'),
            'release_date': data.get('releaseDate'),
            'key': data.get('_key')
        }
    except Exception as e:
        print(f"[x] 获取SDE版本信息失败: {e}")
        return None

def check_existing_version():
    """检查已存在的版本信息"""
    project_root = Path(__file__).parent
    latest_log_path = project_root / "output" / "latest.log"
    
    if not latest_log_path.exists():
        return None
    
    try:
        with open(latest_log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('build_number')
    except Exception as e:
        print(f"[x] 读取现有版本信息失败: {e}")
        return None

def write_latest_log(build_number, release_date):
    """写入latest.log文件"""
    project_root = Path(__file__).parent
    output_sde_dir = project_root / "output_sde"
    output_sde_dir.mkdir(exist_ok=True)
    
    latest_log_path = output_sde_dir / "latest.log"
    
    log_data = {
        'completion_time': datetime.now().isoformat(),
        'build_number': build_number,
        'release_date': release_date
    }
    
    try:
        with open(latest_log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        print(f"[+] 已写入版本日志: {latest_log_path}")
    except Exception as e:
        print(f"[x] 写入版本日志失败: {e}")

def check_network_connectivity():
    """检查网络连接和关键URL的可访问性"""
    print("[+] 开始网络连接检查...")
    
    # 禁用SSL警告（用于处理自签名证书）
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # 要检查的URL列表
    test_urls = [
        "https://images.evetech.net/corporations/500001/logo",
        "https://sde.hoboleaks.space/tq/compressibletypes.json", 
        "https://binaries.eveonline.com/eveclient_TQ.json",
        "https://evemaps.dotlan.net/svg/New_Eden.svg",
        "https://jambeeno.com/jo.txt",
        "https://esi.evetech.net/status",
        "https://newedenencyclopedia.net/dev_resource/icons_dedup.zip"
    ]
    
    failed_urls = []
    
    # 配置会话以处理SSL问题
    session = requests.Session()
    session.verify = False  # 禁用SSL验证以避免证书问题
    session.timeout = 10    # 设置超时时间
    
    for url in test_urls:
        try:
            print(f"[+] 检查URL: {url}")
            
            # 对newedenencyclopedia.net使用无代理连接
            if "newedenencyclopedia.net" in url:
                session.proxies = {'http': None, 'https': None}
            else:
                session.proxies = {}  # 使用默认代理设置
            
            # 使用HEAD请求检查URL可访问性
            response = session.head(url, allow_redirects=True)
            
            if response.status_code == 200:
                print(f"[+] URL可访问: {url}")
            else:
                print(f"[-] URL不可访问: {url} (状态码: {response.status_code})")
                failed_urls.append(url)
                
        except requests.exceptions.SSLError as e:
            print(f"[x] SSL证书错误: {url}")
            failed_urls.append(url)
        except requests.exceptions.Timeout as e:
            print(f"[x] 请求超时: {url}")
            failed_urls.append(url)
        except requests.exceptions.ConnectionError as e:
            print(f"[x] 连接错误: {url}")
            failed_urls.append(url)
        except Exception as e:
            print(f"[x] 未知错误: {url}")
            failed_urls.append(url)
    
    # 检查结果
    if failed_urls:
        print(f"\n[x] 网络检查失败，以下URL无法访问:")
        for url in failed_urls:
            print(f"    - {url}")
        print(f"\n[!] 请检查网络连接或稍后重试")
        print(f"[!] 如果问题持续存在，可能是服务器维护或SSL证书问题")
        return False
    else:
        print(f"\n[+] 网络检查完成，所有关键URL都可以正常访问")
        return True


def load_config():
    """加载JSON配置文件"""
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        print("[x] 配置文件不存在: config.json")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        print(f"[x] 配置文件格式错误: {e}")
        return None
    except Exception as e:
        print(f"[x] 加载配置文件失败: {e}")
        return None

def check_localization_exists() -> bool:
    """检查本地化数据是否已存在"""
    project_root = Path(__file__).parent
    localization_output = project_root / "localization" / "output"
    sde_localization_output = project_root / "output_sde" / "localization"
    
    required_files = [
        "en_multi_lang_mapping.json",
        "combined_localization.json"
    ]
    
    # 检查localization/output目录中的文件
    for file_name in required_files:
        if not (localization_output / file_name).exists():
            return False
    
    # 检查output_sde/localization目录中的文件
    if not (sde_localization_output / "accountingentrytypes_localized.json").exists():
        return False
    
    return True

def process_localization(force: bool = False) -> bool:
    """处理本地化数据"""
    project_root = Path(__file__).parent
    
    # 检查是否需要处理本地化数据
    if not force and check_localization_exists():
        print("[+] 本地化数据已存在，跳过解析")
        return True
    
    print("[+] 开始处理本地化数据...")
    
    try:
        # 直接调用localization/main.py中的main函数
        from localization.main import main as localization_main
        
        print(f"[+] 调用本地化处理函数...")
        
        # 执行本地化处理
        success = localization_main()
        
        if success:
            print("[+] 本地化数据处理完成")
            return True
        else:
            print("[x] 本地化数据处理失败")
            return False
        
    except Exception as e:
        print(f"[x] 调用本地化处理函数时出错: {e}")
        return False


def rebuild_output_directory(config):
    """重构输出目录，删除所有内容并重新创建"""
    project_root = Path(__file__).parent
    
    # 清理output_sde目录
    output_sde_dir = project_root / "output_sde"
    if output_sde_dir.exists():
        print(f"[+] 清理SDE输出目录: {output_sde_dir}")
        shutil.rmtree(output_sde_dir)
    
    # 清理output_icons目录
    output_icons_dir = project_root / "output_icons"
    if output_icons_dir.exists():
        print(f"[+] 清理图标输出目录: {output_icons_dir}")
        shutil.rmtree(output_icons_dir)


def update_config_paths(config):
    """更新配置中的路径，指向新的输出目录结构"""
    project_root = Path(__file__).parent
    
    # 更新配置中的路径
    config["paths"]["db_output"] = "./output_sde/db"
    config["paths"]["icons_output"] = "./output_icons"
    config["paths"]["map_output"] = "./output_sde/maps"
    
    return config

def ensure_directories(config):
    """确保所有必要的目录存在"""
    project_root = Path(__file__).parent
    
    # 创建新的输出目录结构
    output_sde_dir = project_root / "output_sde"
    output_icons_dir = project_root / "output_icons"
    
    # 创建SDE相关目录
    (output_sde_dir / "db").mkdir(parents=True, exist_ok=True)
    (output_sde_dir / "maps").mkdir(parents=True, exist_ok=True)
    (output_sde_dir / "localization").mkdir(parents=True, exist_ok=True)
    
    # 创建图标目录
    output_icons_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[+] 确保目录存在: {output_sde_dir}")
    print(f"[+] 确保目录存在: {output_icons_dir}")
    
    # 保持原有的临时目录结构
    paths = config.get("paths", {})
    for path_name, path_value in paths.items():
        if path_name not in ["db_output", "icons_output", "map_output"]:  # 跳过这些，使用新的目录结构
            full_path = project_root / path_value
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"[+] 确保目录存在: {full_path}")


def safe_execute_processor(processor_func, processor_name, config):
    """安全执行处理器，如果失败则退出程序"""
    try:
        print(f"\n[+] 开始处理{processor_name}")
        result = processor_func(config)
        
        # 如果处理器返回了结果，检查是否为False
        if result is not None and not result:
            print(f"[x] {processor_name}处理失败，程序退出")
            sys.exit(1)
        
        print(f"[+] {processor_name}处理完成")
        return True
        
    except Exception as e:
        print(f"[x] {processor_name}处理时发生异常: {e}")
        print(f"[x] 程序退出")
        sys.exit(1)




def main():
    """主程序入口"""
    # 解析命令行参数
    args = parse_arguments()
    
    print("[+] EVE SDE 处理器启动")
    
    # 版本检查（第一步）
    print("\n[+] 第一步: SDE版本检查")
    print("=" * 30)
    
    # 获取最新SDE版本信息
    latest_sde_info = get_latest_sde_info()
    if not latest_sde_info:
        print("[x] 无法获取最新SDE版本信息，程序退出")
        sys.exit(1)
    
    current_build_number = latest_sde_info['build_number']
    current_release_date = latest_sde_info['release_date']
    
    # 检查是否有环境变量指定的最终build number（用于补丁包）
    final_build_number = os.environ.get('FINAL_BUILD_NUMBER')
    patch_version = os.environ.get('PATCH_VERSION', '0')
    
    if final_build_number:
        print(f"[+] 当前最新SDE版本: {current_build_number}")
        print(f"[+] 最终构建版本: {final_build_number}")
        print(f"[+] 补丁版本: {patch_version}")
        # 使用最终的build number进行后续处理
        current_build_number = final_build_number
    else:
        print(f"[+] 当前最新SDE版本: {current_build_number}")
        print(f"[+] 发布时间: {current_release_date}")
    
    # 检查是否需要强制重建
    if not args.force_rebuild:
        existing_build_number = check_existing_version()
        if existing_build_number and existing_build_number == current_build_number:
            print(f"[+] 检测到相同版本 ({current_build_number})，跳过重新构建")
            print("[+] 如需强制重建，请使用 --force-rebuild 参数或删除 'output/latest.log' 文件")
            return

    print("=" * 30)
    print(f"[+] 准备构造")
    clean.clean_python_cache()

    # 网络连接检查（第二步）
    print("\n[+] 第二步: 网络连接检查")
    print("=" * 30)
    if not check_network_connectivity():
        print("[x] 网络连接检查失败，程序退出")
        sys.exit(1)
    
    # 加载配置
    config = load_config()
    if not config:
        return
    
    print("[+] 配置加载完成")
    print(f"[+] 支持语言: {', '.join(config.get('languages', ['en']))}")
    
    # 重构输出目录（第三步）
    print("\n[+] 第三步: 重构输出目录")
    print("=" * 30)
    rebuild_output_directory(config)
    
    # 更新配置路径
    config = update_config_paths(config)
    
    # 确保其他目录存在
    ensure_directories(config)
    
    # 处理本地化数据（第四步）
    if not args.skip_localization:
        print("\n[+] 第四步: 处理本地化数据")
        print("=" * 30)
        localization_success = process_localization(force=args.force_localization)
        if not localization_success:
            print("[x] 本地化数据处理失败，程序退出")
            sys.exit(1)
        print("[+] 本地化数据处理完成")
    else:
        print("\n[+] 跳过本地化数据处理")
    
    # 执行SDE下载 - 必须成功才能继续
    print("\n[+] 开始执行SDE下载")
    sde_success = sde_downloader.main(config)
    if not sde_success:
        print("[x] SDE下载或解压失败，程序退出")
        print("[!] 请检查网络连接或重试")
        sys.exit(1)
    
    print("[+] SDE数据准备完成，继续后续处理...")
    
    # 执行图标包下载
    safe_execute_processor(icons_downloader.main, "图标包下载", config)
    
    # 执行图标获取
    safe_execute_processor(icon_fetcher.main, "图标获取", config)
    
    # 更新动态物品数据
    safe_execute_processor(dynamic_items_updater.main, "动态物品数据", config)
    
    # 处理宇宙数据
    safe_execute_processor(universe_processor.main, "宇宙数据", config)
    
    # 处理宇宙名称
    safe_execute_processor(universe_names_processor.main, "宇宙名称", config)
    
    # 处理Dogma效果数据
    safe_execute_processor(dogma_effects_processor.main, "Dogma效果数据", config)
    
    # 处理行星制造数据
    safe_execute_processor(planet_schematics_processor.main, "行星制造数据", config)
    
    # 处理物品分类数据
    safe_execute_processor(categories_processor.main, "物品分类数据", config)
    
    # 处理物品组数据
    safe_execute_processor(groups_processor.main, "物品组数据", config)
    
    # 处理物品衍生组数据
    safe_execute_processor(metagroups_processor.main, "物品衍生组数据", config)
    
    # 处理空间站数据
    safe_execute_processor(stations_processor.main, "空间站数据", config)
    
    # 处理派系数据
    safe_execute_processor(factions_processor.main, "派系数据", config)
    
    # 处理NPC公司数据
    safe_execute_processor(npcCorporations_processor.main, "NPC公司数据", config)
    
    # 处理代理人数据
    safe_execute_processor(agents_processor.main, "代理人数据", config)
    
    # 更新代理人本地化信息
    safe_execute_processor(agent_localization_processor.main, "代理人本地化信息", config)
    
    # 处理NPC公司部门数据
    safe_execute_processor(divisions_processor.main, "NPC公司部门数据", config)
    
    # 处理物品属性目录数据
    safe_execute_processor(dogmaAttributeCategories_processor.main, "物品属性目录数据", config)
    
    # 处理物品属性数据
    safe_execute_processor(dogmaAttributes_processor.main, "物品属性数据", config)
    
    # 处理物品属性详情数据
    safe_execute_processor(typeDogma_processor.main, "物品属性详情数据", config)
    
    # 处理物品详情数据
    safe_execute_processor(types_processor.main, "物品详情数据", config)
    
    # 处理dbuff集合数据
    safe_execute_processor(dbuffCollections_processor.main, "dbuff集合数据", config)
    
    # 处理市场分组数据
    safe_execute_processor(marketGroups_processor.main, "市场分组数据", config)
    
    # 处理物品材料产出数据
    safe_execute_processor(typeMaterials_processor.main, "物品材料产出数据", config)
    
    # 处理蓝图数据
    safe_execute_processor(blueprints_processor.main, "蓝图数据", config)
    
    # 处理天体名称数据
    safe_execute_processor(celestial_names_processor.main, "天体名称数据", config)
    
    # 处理技能需求数据
    safe_execute_processor(skill_requirements_processor.main, "技能需求数据", config)
    
    # 处理设施装配效果数据
    safe_execute_processor(facility_rig_effects_processor.main, "设施装配效果数据", config)
    
    # 处理dogmaEffects修补数据
    safe_execute_processor(dogma_effect_patch_processor.main, "dogmaEffects修补数据", config)
    
    # 处理可压缩物品数据
    safe_execute_processor(compressable_types_processor.main, "可压缩物品数据", config)
    
    # 处理类型特性数据
    safe_execute_processor(typeTraits_processor.main, "类型特性数据", config)
    
    # 更新分组图标（使用物品图标替代默认图标）
    safe_execute_processor(update_categories_icons.main, "分组图标更新", config)
    
    # 执行地图生成
    safe_execute_processor(map_generator.main, "地图生成", config)
    
    # 执行数据库标准化（确保跨平台一致性）
    print("\n[+] 执行数据库标准化")
    print("=" * 30)
    import scripts.database_normalizer as database_normalizer
    safe_execute_processor(database_normalizer.main, "数据库标准化", config)
    
    # 处理版本信息（在所有语言数据库中创建版本信息表）
    print("\n[+] 处理版本信息")
    print("=" * 30)
    version_success = version_info_processor.main(
        config, 
        build_number=current_build_number, 
        release_date=current_release_date,
        build_key=latest_sde_info.get('key')
    )
    if not version_success:
        print("[x] 版本信息处理失败，程序退出")
        sys.exit(1)
    print("[+] 版本信息处理完成")
    
    # 执行图标打包处理（在Release比较之前）
    print("\n[+] 执行图标打包处理")
    print("=" * 30)
    safe_execute_processor(compression_processor.main, "图标打包", config)
    
    # 执行Release比较（与最新Release比较差异）
    print("\n[+] 执行Release比较")
    print("=" * 30)
    
    compare_success = release_compare_processor.main(config, current_build_number)
    if not compare_success:
        print("[!] Release比较失败，但继续执行")
    else:
        print("[+] Release比较完成")
    
    # 写入版本日志
    print("\n[+] 写入版本日志")
    print("=" * 30)
    write_latest_log(current_build_number, current_release_date)

    print("\n[+] 所有处理完成")


if __name__ == "__main__":
    main()
