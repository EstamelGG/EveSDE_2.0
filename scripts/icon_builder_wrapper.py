#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图标构造器包装模块
调用eve_icon_builder生成图标包
"""

import sys
import zipfile
import shutil
from pathlib import Path


def build_icons_with_eve_builder(config):
    """使用eve_icon_builder构造图标"""
    print("[+] 使用eve_icon_builder构造图标")
    
    project_root = Path(__file__).parent.parent
    eve_icon_builder_path = project_root / "eve_icon_builder"
    
    # 检查eve_icon_builder是否存在
    if not eve_icon_builder_path.exists():
        print("[x] eve_icon_builder目录不存在")
        return False
    
    main_py = eve_icon_builder_path / "main.py"
    if not main_py.exists():
        print("[x] eve_icon_builder/main.py不存在")
        return False
    
    # 准备输出路径
    icons_zip_dir = project_root / "icons_zip"
    icons_zip_dir.mkdir(exist_ok=True)
    output_zip = icons_zip_dir / "icons_generated.zip"
    
    # 准备eve_icon_builder的输出目录
    eve_output_dir = eve_icon_builder_path / "output"
    eve_output_dir.mkdir(exist_ok=True)
    
    print(f"[+] eve_icon_builder路径: {eve_icon_builder_path}")
    print(f"[+] 输出文件: {output_zip}")
    
    # 导入eve_icon_builder模块
    try:
        # 将eve_icon_builder添加到sys.path
        sys.path.insert(0, str(eve_icon_builder_path))
        
        # 导入必要的模块
        from cache import CacheDownloader
        from sde import update_sde, read_types, read_group_categories, read_icons, read_graphics, read_skin_materials
        from icons import IconBuildData, build_icon_export
        
        print("[+] 初始化缓存...")
        cache = CacheDownloader(
            eve_icon_builder_path / "cache",
            "EVE-SDE-Builder/1.0",
            use_macos_build=False
        )
        
        print("[+] 加载SDE数据...")
        sde = update_sde(silent_mode=False)
        
        icon_build_data = IconBuildData(
            types=read_types(sde, silent_mode=False),
            group_categories=read_group_categories(sde, silent_mode=False),
            icon_files=read_icons(sde, silent_mode=False),
            graphics_folders=read_graphics(sde, silent_mode=False),
            skin_materials=read_skin_materials(sde, silent_mode=False)
        )
        
        sde.close()
        
        print("[+] 开始构造图标...")
        added, removed = build_icon_export(
            output_mode='service_bundle',
            skip_output_if_fresh=False,
            data=icon_build_data,
            cache=cache,
            icon_dir=eve_icon_builder_path / "icons",
            force_rebuild=False,
            silent_mode=False,
            log_file=None,
            show_progress=True,
            skip_skins=True,  # 跳过SKIN图标以加快速度
            test_type_id=None,
            out=str(output_zip)
        )
        
        print(f"[+] 图标构造完成: {added} 新增, {removed} 删除")
        
        # 清理不必要的缓存
        cache.purge(['sde.zip', 'checksum.txt'])
        
        # 从sys.path中移除
        sys.path.remove(str(eve_icon_builder_path))
        
        if not output_zip.exists():
            print("[x] 图标包生成失败")
            return False
        
        print(f"[+] 图标包已生成: {output_zip}")
        return True
        
    except Exception as e:
        print(f"[x] 构造图标时出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def extract_generated_icons(config):
    """解压生成的图标包"""
    print("[+] 解压图标包")
    
    project_root = Path(__file__).parent.parent
    icons_zip_dir = project_root / "icons_zip"
    output_zip = icons_zip_dir / "icons_generated.zip"
    
    if not output_zip.exists():
        print("[x] 图标包不存在，无法解压")
        return False
    
    icons_input_path = project_root / config["paths"]["icons_input"]
    icons_output_path = project_root / config["paths"]["icons_output"]
    
    try:
        # 清理旧的解压目录
        if icons_input_path.exists():
            print(f"[+] 清理旧的图标输入数据: {icons_input_path}")
            shutil.rmtree(icons_input_path)
        
        if icons_output_path.exists():
            print(f"[+] 清理旧的图标输出数据: {icons_output_path}")
            shutil.rmtree(icons_output_path)
        
        icons_input_path.mkdir(parents=True, exist_ok=True)
        
        # 解压图标包
        print(f"[+] 开始解压图标包: {output_zip}")
        with zipfile.ZipFile(output_zip, 'r') as zip_ref:
            zip_ref.extractall(icons_input_path)
        
        print(f"[+] 图标包解压完成: {icons_input_path}")
        
        # 统计解压的文件数量
        png_files = list(icons_input_path.glob("**/*.png"))
        json_files = list(icons_input_path.glob("**/*.json"))
        
        print(f"[+] 解压得到:")
        print(f"    - PNG图标文件: {len(png_files)} 个")
        print(f"    - JSON元数据文件: {len(json_files)} 个")
        
        # 查找service_metadata.json
        metadata_files = list(icons_input_path.glob("**/service_metadata.json"))
        if metadata_files:
            print(f"[+] 找到service_metadata.json: {metadata_files[0]}")
        else:
            print("[!] 未找到service_metadata.json文件")
        
        return True
        
    except Exception as e:
        print(f"[x] 解压失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main(config=None):
    """主函数"""
    print("[+] 图标构造器启动")
    
    # 如果没有传入配置，则尝试加载本地配置
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 构造图标
    if not build_icons_with_eve_builder(config):
        print("[x] 图标构造失败")
        return False
    
    # 解压图标包
    if not extract_generated_icons(config):
        print("[x] 图标解压失败")
        return False
    
    print("[+] 图标构造器完成")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

