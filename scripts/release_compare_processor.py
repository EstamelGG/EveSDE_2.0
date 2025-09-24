#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Release比较处理器
用于比较当前构建与最新Release的差异
"""

import json
import os
import zipfile
import requests
import subprocess
import difflib
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


class ReleaseCompareProcessor:
    """Release比较处理器"""
    
    def __init__(self, config: Dict[str, Any], build_number: int):
        """初始化Release比较处理器"""
        self.config = config
        self.build_number = build_number
        self.project_root = Path(__file__).parent.parent
        self.output_sde_path = self.project_root / "output_sde"
        self.output_icons_path = self.project_root / "output_icons"
        self.tools_path = self.project_root / "tools"
        self.languages = config.get("languages", ["en", "zh"])
        
        # 创建比较日志文件（输出到项目根目录）
        self.compare_log_path = self.project_root / f"release_compare_{build_number}.log"
        
        # 临时目录用于下载和解压旧版本
        self.temp_dir = None
        
    def __enter__(self):
        """上下文管理器入口"""
        self.temp_dir = Path(tempfile.mkdtemp())
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，清理临时文件"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def log(self, message: str):
        """记录日志到文件和控制台"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        
        with open(self.compare_log_path, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    
    def get_latest_release_info(self) -> Optional[Dict[str, Any]]:
        """获取最新Release信息"""
        try:
            self.log("[+] 获取最新Release信息...")
            
            # 获取仓库信息
            github_repo = self.config.get('github_repo', '')
            if not github_repo:
                self.log("[!] 未配置GitHub仓库信息，跳过Release比较")
                return None
            
            # 构建API URL
            repo_url = f"https://api.github.com/repos/{github_repo}/releases/latest"
            
            # 准备请求头
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'EVE-SDE-Processor'
            }
            
            self.log("[+] 使用公开仓库访问，无需认证")
            
            response = requests.get(repo_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            release_info = response.json()
            self.log(f"[+] 最新Release: {release_info.get('tag_name', 'Unknown')}")
            self.log(f"[+] 发布时间: {release_info.get('published_at', 'Unknown')}")
            
            return release_info
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.log("[!] 未找到任何Release，跳过比较")
            else:
                self.log(f"[!] HTTP错误: {e}")
            return None
        except Exception as e:
            self.log(f"[!] 获取最新Release信息失败: {e}")
            return None
    
    def download_release_assets(self, release_info: Dict[str, Any]) -> bool:
        """下载Release资源文件"""
        try:
            self.log("[+] 开始下载Release资源文件...")
            
            assets = release_info.get('assets', [])
            downloaded_files = {}
            
            for asset in assets:
                asset_name = asset.get('name', '')
                download_url = asset.get('browser_download_url', '')
                
                if asset_name in ['icons.zip', 'sde.zip']:
                    self.log(f"[+] 下载 {asset_name}...")
                    
                    # 准备请求头
                    headers = {
                        'Accept': 'application/octet-stream',
                        'User-Agent': 'EVE-SDE-Processor'
                    }
                    
                    response = requests.get(download_url, headers=headers, timeout=300)
                    response.raise_for_status()
                    
                    file_path = self.temp_dir / asset_name
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    downloaded_files[asset_name] = file_path
                    self.log(f"[+] {asset_name} 下载完成: {file_path.stat().st_size} bytes")
            
            # 解压sde.zip
            if 'sde.zip' in downloaded_files:
                sde_zip_path = downloaded_files['sde.zip']
                sde_extract_path = self.temp_dir / "sde_old"
                sde_extract_path.mkdir()
                
                self.log(f"[+] 开始解压SDE数据: {sde_zip_path}")
                self.log(f"[+] 解压到目录: {sde_extract_path}")
                
                # 检查ZIP文件是否存在和大小
                if sde_zip_path.exists():
                    zip_size = sde_zip_path.stat().st_size
                    self.log(f"[+] ZIP文件大小: {zip_size} bytes")
                else:
                    self.log("[!] ZIP文件不存在")
                    return False
                
                try:
                    # 使用zipfile处理ZIP格式的文件
                    with zipfile.ZipFile(sde_zip_path, 'r') as zip_ref:
                        file_list = zip_ref.namelist()
                        self.log(f"[+] ZIP文件包含 {len(file_list)} 个文件")
                        self.log("[+] ZIP文件内容（前10个）:")
                        for i, filename in enumerate(file_list[:10]):
                            self.log(f"    {filename}")
                        
                        zip_ref.extractall(sde_extract_path)
                    
                    self.log(f"[+] SDE数据解压完成: {sde_extract_path}")
                    
                    # 调试：列出解压后的文件
                    self.log("[+] 解压后的文件列表:")
                    extracted_files = list(sde_extract_path.iterdir())
                    if extracted_files:
                        for item in extracted_files:
                            if item.is_file():
                                self.log(f"    {item.name}")
                            elif item.is_dir():
                                self.log(f"    [目录] {item.name}")
                    else:
                        self.log("    [空目录]")
                        
                except Exception as e:
                    self.log(f"[!] 解压失败: {e}")
                    return False
            
            # 保留icons.zip文件用于直接比较（不解压）
            if 'icons.zip' in downloaded_files:
                self.log("[+] 保留旧版本图标ZIP文件用于直接比较")
            
            return True
            
        except Exception as e:
            self.log(f"[x] 下载Release资源失败: {e}")
            return False
    
    def compare_icons(self) -> bool:
        """比较图标文件差异（直接比较ZIP文件内容）"""
        try:
            self.log("[+] 开始比较图标文件...")
            
            # 当前版本图标ZIP文件
            current_icons_zip = self.output_icons_path / "icons.zip"
            old_icons_zip = self.temp_dir / "icons.zip"
            
            if not current_icons_zip.exists():
                self.log("[!] 当前版本图标ZIP文件不存在")
                return False
            
            if not old_icons_zip.exists():
                self.log("[!] 旧版本图标ZIP文件不存在")
                return False
            
            # 读取ZIP文件内容列表
            current_files = set()
            old_files = set()
            
            # 读取当前版本ZIP文件列表
            with zipfile.ZipFile(current_icons_zip, 'r') as zip_ref:
                current_files = set(zip_ref.namelist())
            
            # 读取旧版本ZIP文件列表
            with zipfile.ZipFile(old_icons_zip, 'r') as zip_ref:
                old_files = set(zip_ref.namelist())
            
            # 分析差异
            added_files = current_files - old_files
            removed_files = old_files - current_files
            common_files = current_files & old_files
            
            self.log(f"[+] 图标文件统计:")
            self.log(f"    当前版本: {len(current_files)} 个文件")
            self.log(f"    旧版本: {len(old_files)} 个文件")
            self.log(f"    新增: {len(added_files)} 个文件")
            self.log(f"    删除: {len(removed_files)} 个文件")
            self.log(f"    共同: {len(common_files)} 个文件")
            
            # 详细列出新增文件
            if added_files:
                self.log(f"[+] 新增的图标文件:")
                for file_name in sorted(added_files):
                    self.log(f"    + {file_name}")
            
            # 详细列出删除文件
            if removed_files:
                self.log(f"[+] 删除的图标文件:")
                for file_name in sorted(removed_files):
                    self.log(f"    - {file_name}")
            
            # 检查文件大小变化（只检查前10个文件，避免输出过多）
            changed_files = []
            for file_name in sorted(common_files)[:10]:
                try:
                    with zipfile.ZipFile(current_icons_zip, 'r') as current_zip:
                        current_info = current_zip.getinfo(file_name)
                        current_size = current_info.file_size
                    
                    with zipfile.ZipFile(old_icons_zip, 'r') as old_zip:
                        old_info = old_zip.getinfo(file_name)
                        old_size = old_info.file_size
                    
                    if current_size != old_size:
                        changed_files.append(f"{file_name} ({old_size} -> {current_size} bytes)")
                except KeyError:
                    # 文件在某个ZIP中不存在，跳过
                    continue
            
            if changed_files:
                self.log(f"[+] 内容变化的图标文件:")
                for file_name in changed_files:
                    self.log(f"    ~ {file_name}")
            
            self.log("[+] 图标文件比较完成")
            return True
            
        except Exception as e:
            self.log(f"[x] 比较图标文件失败: {e}")
            return False
    
    def compare_databases(self) -> bool:
        """比较数据库差异"""
        try:
            self.log("[+] 开始比较数据库文件...")
            
            sqldiff_path = self.tools_path / "sqldiff"
            if not sqldiff_path.exists():
                self.log(f"[!] sqldiff工具不存在: {sqldiff_path}")
                return False
            
            # 确保sqldiff有执行权限
            sqldiff_path.chmod(0o755)
            
            for lang in self.languages:
                self.log(f"[+] 比较 {lang} 语言数据库...")
                
                # 当前版本数据库
                current_db = self.output_sde_path / "db" / f"item_db_{lang}.sqlite"
                old_db = self.temp_dir / "sde_old" / f"item_db_{lang}.sqlite"
                
                if not current_db.exists():
                    self.log(f"[!] 当前版本数据库不存在: {current_db}")
                    continue
                
                if not old_db.exists():
                    self.log(f"[!] 旧版本数据库不存在: {old_db}")
                    continue
                
                # 执行sqldiff比较
                try:
                    result = subprocess.run(
                        [str(sqldiff_path), str(old_db), str(current_db)],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    
                    if result.returncode == 0:
                        if result.stdout.strip():
                            self.log(f"[+] {lang} 数据库差异:")
                            for line in result.stdout.strip().split('\n'):
                                self.log(f"    {line}")
                        else:
                            self.log(f"[+] {lang} 数据库无差异")
                    else:
                        self.log(f"[!] sqldiff执行失败: {result.stderr}")
                        
                except subprocess.TimeoutExpired:
                    self.log(f"[!] sqldiff执行超时")
                except Exception as e:
                    self.log(f"[!] sqldiff执行异常: {e}")
            
            return True
            
        except Exception as e:
            self.log(f"[x] 比较数据库失败: {e}")
            return False
    
    def compare_maps(self) -> bool:
        """比较地图文件差异"""
        try:
            self.log("[+] 开始比较地图文件...")
            
            # 当前版本地图目录
            current_maps_path = self.output_sde_path / "maps"
            old_maps_path = self.temp_dir / "sde_old"
            
            if not current_maps_path.exists():
                self.log("[!] 当前版本地图目录不存在")
                return False
            
            # 地图文件列表
            map_files = ['regions_data.json', 'systems_data.json', 'neighbors_data.json']
            
            for map_file in map_files:
                self.log(f"[+] 比较 {map_file}...")
                
                current_file = current_maps_path / map_file
                old_file = old_maps_path / map_file
                
                if not current_file.exists():
                    self.log(f"[!] 当前版本文件不存在: {current_file}")
                    continue
                
                if not old_file.exists():
                    self.log(f"[!] 旧版本文件不存在: {old_file}")
                    continue
                
                # 读取文件内容
                try:
                    with open(current_file, 'r', encoding='utf-8') as f:
                        current_content = f.readlines()
                    
                    with open(old_file, 'r', encoding='utf-8') as f:
                        old_content = f.readlines()
                    
                    # 使用difflib比较
                    diff = list(difflib.unified_diff(
                        old_content,
                        current_content,
                        fromfile=f"old_{map_file}",
                        tofile=f"new_{map_file}",
                        lineterm=''
                    ))
                    
                    if diff:
                        self.log(f"[+] {map_file} 差异:")
                        for line in diff[:50]:  # 只显示前50行差异
                            self.log(f"    {line}")
                        if len(diff) > 50:
                            self.log(f"    ... (还有 {len(diff) - 50} 行差异)")
                    else:
                        self.log(f"[+] {map_file} 无差异")
                        
                except Exception as e:
                    self.log(f"[!] 比较 {map_file} 失败: {e}")
            
            return True
            
        except Exception as e:
            self.log(f"[x] 比较地图文件失败: {e}")
            return False
    
    def process_release_compare(self) -> bool:
        """执行完整的Release比较流程"""
        try:
            self.log("=" * 60)
            self.log(f"[+] 开始Release比较 - Build {self.build_number}")
            self.log("=" * 60)
            
            # 1. 获取最新Release信息
            release_info = self.get_latest_release_info()
            if not release_info:
                self.log("[!] 无法获取最新Release信息，跳过比较")
                self.log("[!] 可能原因：")
                self.log("    1. 这是第一个Release")
                self.log("    2. 网络连接问题")
                self.log("    3. GitHub API限制")
                return False
            
            # 2. 下载Release资源
            if not self.download_release_assets(release_info):
                self.log("[!] 下载Release资源失败，跳过比较")
                return False
            
            # 3. 比较图标文件
            self.compare_icons()
            
            # 4. 比较数据库文件
            self.compare_databases()
            
            # 5. 比较地图文件
            self.compare_maps()
            
            self.log("=" * 60)
            self.log(f"[+] Release比较完成 - Build {self.build_number}")
            self.log("=" * 60)
            
            return True
            
        except Exception as e:
            self.log(f"[x] Release比较失败: {e}")
            return False


def main(config: Dict[str, Any], build_number: int) -> bool:
    """主函数"""
    with ReleaseCompareProcessor(config, build_number) as processor:
        return processor.process_release_compare()


if __name__ == "__main__":
    # 测试代码
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    
    # 加载配置
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 测试Release比较
    success = main(config, build_number=999999)
    print(f"测试结果: {'成功' if success else '失败'}")
