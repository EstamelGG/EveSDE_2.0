#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图标版本更新工具
用于比较本地图标包与远程图标包的SHA256，并更新数据库中的icon_version字段
"""

import sys
import json
import sqlite3
import hashlib
import requests
from pathlib import Path
from typing import Optional, Dict, Any


class IconVersionUpdater:
    """图标版本更新器"""
    
    def __init__(self, config: Dict[str, Any], github_repo_api_url: str):
        """初始化图标版本更新器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.github_repo_api_url = github_repo_api_url
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        
        # 本地图标ZIP路径
        self.local_icons_zip = self.project_root / "output_icons" / "icons.zip"
    
    def calculate_sha256(self, file_path: Path) -> str:
        """计算文件的SHA256哈希值"""
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                # 分块读取以处理大文件
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            print(f"[x] 计算SHA256时出错: {e}")
            return None
    
    def get_remote_release_info(self) -> Optional[Dict[str, Any]]:
        """
        从GitHub Release API获取远程Release信息
        返回: {
            "icons_sha256": "xxx",
            "metadata_download_url": "xxx"  (可选)
        }
        """
        try:
            print(f"[+] 获取远程Release信息: {self.github_repo_api_url}")
            response = requests.get(self.github_repo_api_url, timeout=30)
            response.raise_for_status()
            
            release_data = response.json()
            assets = release_data.get("assets", [])
            
            result = {}
            
            # 查找icons.zip和metadata.json
            for asset in assets:
                asset_name = asset.get("name", "")
                
                if asset_name == "icons.zip":
                    digest = asset.get("digest", "")
                    download_url = asset.get("browser_download_url", "")
                    
                    # 解析digest字段: "sha256:xxxx"
                    if digest.startswith("sha256:"):
                        sha256_value = digest.split(":", 1)[1]
                        result["icons_sha256"] = sha256_value
                        result["icons_download_url"] = download_url
                        print(f"[+] 远程图标包SHA256: {sha256_value}")
                
                elif asset_name == "metadata.json":
                    download_url = asset.get("browser_download_url", "")
                    result["metadata_download_url"] = download_url
                    print(f"[+] 远程metadata.json URL: {download_url}")
            
            # 检查是否找到icons.zip
            if "icons_sha256" not in result:
                print("[!] 未在Release中找到icons.zip")
                return None
            
            # metadata.json是可选的
            if "metadata_download_url" not in result:
                print("[!] 未在Release中找到metadata.json，将使用默认版本号0")
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"[x] 获取远程Release信息失败: {e}")
            return None
        except Exception as e:
            print(f"[x] 解析Release数据失败: {e}")
            return None
    
    def download_metadata(self, metadata_url: str) -> Optional[Dict[str, Any]]:
        """
        下载并解析metadata.json文件
        返回metadata字典
        """
        try:
            print(f"[+] 下载metadata.json: {metadata_url}")
            
            response = requests.get(metadata_url, timeout=30)
            response.raise_for_status()
            
            metadata = response.json()
            print(f"[+] metadata.json下载完成")
            
            return metadata
            
        except Exception as e:
            print(f"[x] 下载或解析metadata.json失败: {e}")
            return None
    
    def get_old_icon_version_from_metadata(self, metadata_url: str) -> int:
        """
        从metadata.json中获取icon_version
        如果无法获取，返回0
        """
        try:
            metadata = self.download_metadata(metadata_url)
            
            if not metadata:
                print("[!] 无法下载metadata.json，使用默认版本号0")
                return 0
            
            icon_version = metadata.get("icon_version", 0)
            print(f"[+] 旧版图标版本号: {icon_version}")
            
            return icon_version
            
        except Exception as e:
            print(f"[x] 从metadata.json读取icon_version时出错: {e}")
            return 0
    
    def update_icon_version_in_databases(self, new_version: int) -> bool:
        """
        更新所有语言数据库中的icon_version字段
        """
        try:
            print(f"[+] 开始更新所有数据库的icon_version为: {new_version}")
            
            success_count = 0
            for language in self.languages:
                db_path = self.db_output_path / f"item_db_{language}.sqlite"
                
                if not db_path.exists():
                    print(f"[!] 数据库不存在: {db_path}")
                    continue
                
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    
                    # 更新icon_version
                    cursor.execute("""
                        UPDATE version_info SET icon_version = ?
                    """, (new_version,))
                    
                    conn.commit()
                    conn.close()
                    
                    print(f"[+] 已更新数据库 {language}: icon_version = {new_version}")
                    success_count += 1
                    
                except Exception as e:
                    print(f"[x] 更新数据库 {language} 时出错: {e}")
            
            print(f"[+] 成功更新 {success_count}/{len(self.languages)} 个数据库")
            return success_count > 0
            
        except Exception as e:
            print(f"[x] 更新数据库时出错: {e}")
            return False
    
    def create_metadata_file(self, icon_version: int, icon_sha256: str) -> bool:
        """
        创建metadata.json文件
        包含icon_version和icon_sha256信息
        注意：sde_sha256会在GitHub Actions中后续添加
        """
        try:
            # 从数据库读取build_number等信息
            db_path = self.db_output_path / "item_db_en.sqlite"
            
            build_number = None
            patch_number = None
            release_date = None
            
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute("SELECT build_number, patch_number, release_date FROM version_info LIMIT 1")
                    result = cursor.fetchone()
                    conn.close()
                    
                    if result:
                        build_number = result[0]
                        patch_number = result[1]
                        release_date = result[2]
                except Exception as e:
                    print(f"[!] 读取数据库版本信息时出错: {e}")
            
            # 创建metadata（sde_sha256将在GitHub Actions中添加）
            metadata = {
                "icon_version": icon_version,
                "icon_sha256": icon_sha256,
                "sde_sha256": None,
                "build_number": build_number,
                "patch_number": patch_number,
                "release_date": release_date
            }
            
            # 写入文件到output_icons目录
            output_icons_path = self.project_root / "output_icons"
            output_icons_path.mkdir(exist_ok=True)
            
            metadata_path = output_icons_path / "metadata.json"
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            print(f"[+] 已创建metadata.json: {metadata_path}")
            print(f"[+] icon_version: {icon_version}, icon_sha256: {icon_sha256[:16]}...")
            print(f"[!] sde_sha256将在压缩包创建后添加")
            
            return True
            
        except Exception as e:
            print(f"[x] 创建metadata.json失败: {e}")
            return False
    
    def process(self) -> bool:
        """执行图标版本更新流程"""
        print("[+] 开始执行图标版本更新流程")
        print("=" * 50)
        
        # 1. 检查本地图标包是否存在
        if not self.local_icons_zip.exists():
            print(f"[x] 本地图标包不存在: {self.local_icons_zip}")
            return False
        
        # 2. 计算本地图标包的SHA256
        print("[+] 计算本地图标包SHA256...")
        local_sha256 = self.calculate_sha256(self.local_icons_zip)
        if not local_sha256:
            print("[x] 无法计算本地图标包SHA256")
            return False
        print(f"[+] 本地图标包SHA256: {local_sha256}")
        
        # 3. 获取远程Release信息
        remote_info = self.get_remote_release_info()
        if not remote_info:
            print("[!] 无法获取远程Release信息，使用默认版本号0")
            # 无法获取远程信息时，直接使用版本号0
            new_version = 0
            success = self.update_icon_version_in_databases(new_version)
            if success:
                self.create_metadata_file(new_version, local_sha256)
            return success
        
        remote_sha256 = remote_info["icons_sha256"]
        metadata_url = remote_info.get("metadata_download_url")
        
        # 4. 比较SHA256
        print("[+] 比较SHA256...")
        if local_sha256 == remote_sha256:
            print("[+] SHA256相同，图标包未更新")
            sha256_changed = False
        else:
            print("[+] SHA256不同，图标包已更新")
            sha256_changed = True
        
        # 5. 获取旧版本号
        if metadata_url:
            print("[+] 从metadata.json获取旧版本号...")
            old_version = self.get_old_icon_version_from_metadata(metadata_url)
        else:
            print("[!] 未找到metadata.json，使用默认版本号0")
            old_version = 0
        
        # 6. 确定新版本号
        if sha256_changed:
            new_version = old_version + 1
            print(f"[+] 图标包已更新，新版本号: {new_version} (旧版本: {old_version})")
        else:
            new_version = old_version
            print(f"[+] 图标包未更新，版本号保持: {new_version}")
        
        # 7. 更新所有数据库
        success = self.update_icon_version_in_databases(new_version)
        
        if not success:
            print("[x] 图标版本更新失败")
            print("=" * 50)
            return False
        
        # 8. 创建metadata.json文件
        if not self.create_metadata_file(new_version, local_sha256):
            print("[!] 创建metadata.json失败，但继续执行")
        
        print("[+] 图标版本更新完成")
        print("=" * 50)
        
        return True


def main(config=None, github_repo_api_url=None):
    """主函数"""
    if not config:
        print("[x] 配置参数缺失")
        return False
    
    if not github_repo_api_url:
        print("[x] github_repo_api_url参数缺失")
        return False
    
    updater = IconVersionUpdater(config, github_repo_api_url)
    return updater.process()


if __name__ == "__main__":
    # 用于独立运行测试
    import argparse
    
    parser = argparse.ArgumentParser(description='图标版本更新工具')
    parser.add_argument('--api-url', required=True, help='GitHub Release API URL')
    args = parser.parse_args()
    
    # 加载配置
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    success = main(config, args.api_url)
    sys.exit(0 if success else 1)

