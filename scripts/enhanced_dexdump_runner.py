#!/usr/bin/env python3
"""
针对新百度reinforcement等商业reinforcement方案，实现DEXfile的完整动态Unpacking
"""

import os
import sys
import subprocess
import time
import re
import json
import hashlib
import struct
import zlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set

class EnhancedDexDumpRunner:
    """增强版Unpacking执行器 - 针对新百度reinforcementOptimizing"""
    
    def __init__(self, verbose: bool = False, max_attempts: int = 3, deep_search: bool = False, 
                 bypass_antidebug: bool = False):
        self.verbose = verbose
        self.max_attempts = max_attempts  # 最大尝试次数
        self.deep_search = deep_search    # 是否启用深度搜索模式
        self.bypass_antidebug = bypass_antidebug  # 是否启用anti-debugBypass
        self.all_dex_files = []  # 收集所有DEXfileInformation（去重）
        self.execution_log = []  # 执行Log
        self.start_time = None
        self.end_time = None
        
    def log(self, message: str, level: str = "INFO"):
        """RecordingLog"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.execution_log.append(log_entry)
        
        # 实时Output到控制台
        if level == "INFO":
            print(f"📝 {message}")
        elif level == "SUCCESS":
            print(f"✅ {message}")
        elif level == "WARNING":
            print(f"⚠️  {message}")
        elif level == "ERROR":
            print(f"❌ {message}")
        elif level == "DEBUG" and self.verbose:
            print(f"🔍 {message}")
        
        # 立即刷新Output缓冲区
        import sys
        sys.stdout.flush()
    
    def check_environment(self) -> bool:
        """检查运行Environment"""
        self.log("检查运行Environment...")
        
        # 检查frida-dexdump
        try:
            result = subprocess.run(["which", "frida-dexdump"], 
                                   capture_output=True, text=True)
            if result.returncode != 0:
                self.log("未找到 frida-dexdump Tool", "ERROR")
                self.log("请执行: pip install frida-dexdump", "WARNING")
                return False
            self.log(f"frida-dexdump Path: {result.stdout.strip()}", "DEBUG")
        except Exception as e:
            self.log(f"检查frida-dexdumpFailed: {e}", "ERROR")
            return False
        
        # 检查ADBDevice连接
        try:
            result = subprocess.run(["adb", "devices"], 
                                   capture_output=True, text=True, timeout=10)
            if "device" not in result.stdout:
                self.log("未找到已连接的AndroidDevice", "ERROR")
                self.log("Please ensure: 1) USBDebuggingEnabled 2) Device已授权", "WARNING")
                return False
            
            # 提取DeviceID
            lines = result.stdout.strip().split('\n')
            device_id = None
            for line in lines[1:]:  # 跳过第一行标题
                if "device" in line:
                    device_id = line.split()[0]
                    break
            
            if device_id:
                self.log(f"找到Device: {device_id}", "SUCCESS")
            else:
                self.log("DeviceStatusException", "ERROR")
                return False
                
        except subprocess.timeoutExpired:
            self.log("ADBDevice检查timeout（10秒）", "ERROR")
            self.log("Please checkUSB连接和Device授权Status", "WARNING")
            return False
        except Exception as e:
            self.log(f"检查ADBDeviceFailed: {e}", "ERROR")
            return False
        
        # 检查FridaService
        try:
            result = subprocess.run(["frida-ps", "-U"], 
                                   capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.log("FridaService可能未运行", "WARNING")
                self.log("Please ensureDevice上已运行 frida-server (需要root权限)", "WARNING")
            else:
                self.log("FridaService运行正常", "SUCCESS")
        except subprocess.timeoutExpired:
            self.log("FridaService检查timeout", "WARNING")
        except Exception as e:
            self.log(f"检查FridaServiceFailed: {e}", "WARNING")
        
        return True
    
    def check_package_installed(self, package_name: str) -> bool:
        """检查Application是否已Installing"""
        try:
            result = subprocess.run(
                ["adb", "shell", "pm", "list", "packages", package_name],
                capture_output=True, text=True, timeout=10
            )
            if package_name in result.stdout:
                self.log(f"Application '{package_name}' 已Installing", "SUCCESS")
                return True
            else:
                self.log(f"未找到Application '{package_name}'", "ERROR")
                self.log("使用 'adb shell pm list packages' 查看所有已InstallingApplication", "WARNING")
                return False
        except subprocess.timeoutExpired:
            self.log(f"检查ApplicationInstallingStatustimeout（10秒）", "ERROR")
            self.log("ADB连接可能不稳定或Device无响应", "WARNING")
            return False
        except Exception as e:
            self.log(f"检查ApplicationInstallingStatusFailed: {e}", "ERROR")
            return False
    
    def start_application(self, package_name: str) -> bool:
        """StartingApplication - 直接StartingUnpackingAPP"""
        self.log(f"StartingApplication '{package_name}'...")
        
        try:
            # 1. 获取Application主Activity - 使用更可靠的cmd package resolve-activity命令
            self.log("获取Application主Activity...")
            main_activity = None
            
            # 方法1: 使用cmd package resolve-activity（Android 7.0+）
            try:
                resolve_cmd = ["adb", "shell", "cmd", "package", "resolve-activity",
                             "--brief", "-c", "android.intent.category.LAUNCHER", package_name]
                result = subprocess.run(resolve_cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) >= 2:
                        main_activity = lines[-1].strip()  # 最后一行是Activity
                        self.log(f"通过resolve-activity找到主Activity: {main_activity}", "DEBUG")
            except Exception as e:
                self.log(f"resolve-activity命令Failed: {e}", "DEBUG")
            
            # 方法2: 如果方法1Failed，使用dumpsys package（备用）
            if not main_activity:
                self.log("尝试使用dumpsys package获取Activity...", "DEBUG")
                activity_cmd = [
                    "adb", "shell", "dumpsys", "package", package_name,
                    "|", "grep", "-A5", "MAIN", "|", "grep", package_name
                ]
                result = subprocess.run(" ".join(activity_cmd), 
                                       shell=True, capture_output=True, text=True, timeout=10)
                
                for line in result.stdout.split('\n'):
                    if package_name in line and "android.intent.action.MAIN" in line:
                        parts = line.split()
                        if len(parts) > 1:
                            main_activity = parts[1].strip()
                            break
            
            # 方法3: 如果以上都Failed，使用通用Activity名称
            if not main_activity:
                # 使用通用Activity名称
                main_activity = f"{package_name}/.MainActivity"
                self.log(f"使用默认Activity: {main_activity}", "WARNING")
            else:
                self.log(f"找到主Activity: {main_activity}", "DEBUG")
            
            # 2. 直接StartingApplication
            self.log("直接StartingApplication...")
            start_cmd = ["adb", "shell", "am", "start", "-n", main_activity]
            result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.log(f"ApplicationStarting成功: {main_activity}", "SUCCESS")
                return True
            else:
                self.log(f"ApplicationStartingFailed，返回码: {result.returncode}", "ERROR")
                self.log(f"StartingOutput: {result.stdout[:200]}...", "DEBUG")
                return False
            
        except Exception as e:
            self.log(f"StartingApplication过程中出错: {e}", "ERROR")
            return False
    
    def wait_for_application_load(self, wait_time: int = 30) -> bool:
        """WaitingApplication加载"""
        self.log(f"WaitingApplication加载 {wait_time} 秒...")
        
        for i in range(wait_time):
            if i % 5 == 0:  # 每5秒显示一次Progress
                remaining = wait_time - i
                self.log(f"Waiting中... ({remaining}秒剩余)")
            time.sleep(1)
        
        self.log("Application加载Waiting完成", "SUCCESS")
        return True
    
    def parse_dexdump_output(self, line: str) -> Optional[Dict]:
        """解析frida-dexdumpOutput，提取DEXfileInformation"""
        # 匹配模式: [+] DexMd5=..., SavePath=..., Dexsize=...
        pattern = r'\[\+\] DexMd5=([0-9a-f]+),\s+SavePath=([^,]+),\s+Dexsize=([0-9a-fx]+)'
        match = re.search(pattern, line)
        
        if match:
            dex_md5, save_path, dex_size = match.groups()
            
            # 转换十六进制size为十进制字节数
            try:
                size_bytes = int(dex_size, 16)
                size_kb = size_bytes / 1024
                size_mb = size_kb / 1024
                
                dex_info = {
                    'md5': dex_md5,
                    'path': save_path,
                    'size_bytes': size_bytes,
                    'size_kb': round(size_kb, 1),
                    'size_mb': round(size_mb, 2) if size_mb >= 0.1 else 0.0,
                    'timestamp': datetime.now().isoformat()
                }
                
                return dex_info
            except ValueError:
                self.log(f"无法解析DEXsize: {dex_size}", "WARNING")
        
        return None
    
    def execute_single_dexdump(self, package_name: str, output_dir: str, attempt: int = 1) -> Tuple[bool, List[Dict]]:
        """执行单次frida-dexdump"""
        self.log(f"执行第 {attempt} 次Unpacking尝试...")
        
        # 确保OutputDirectory存在
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # anti-debugBypass（如果启用）
        if self.bypass_antidebug:
            self.log("执行Anti-debugBypass...", "INFO")
            try:
                # 导入anti-debugBypassModule
                sys.path.append(os.path.dirname(os.path.abspath(__file__)))
                from antidebug_bypass import AntiDebugBypass
                
                # Creatinganti-debugBypass实例
                bypass = AntiDebugBypass(verbose=self.verbose)
                
                # 执行anti-debugBypass
                bypass_success = bypass.run_bypass(package_name)
                
                if bypass_success:
                    self.log("Anti-debugBypassExecution completed", "SUCCESS")
                    # WaitingBypass生效
                    self.log("WaitingBypass生效（5秒）...")
                    time.sleep(5)
                else:
                    self.log("Anti-debugBypassExecution failed，但仍ResumingUnpacking", "WARNING")
                    
            except ImportError as e:
                self.log(f"无法导入Anti-debugBypassModule: {e}", "WARNING")
            except Exception as e:
                self.log(f"Anti-debugBypass执行出错: {e}", "WARNING")
        
        # 构建命令
        cmd = [
            'frida-dexdump',
            '-U',
            '-f', package_name,
            '-o', str(output_path)
        ]
        
        # 添加深度搜索Parameter（如果启用）
        if self.deep_search:
            cmd.append('-d')
            self.log("启用深度搜索模式 (-d Parameter)", "SUCCESS")
            self.log("Deep search mode will perform more thorough memory scanning，可能发现更多DEXfile", "INFO")
        
        self.log(f"执行命令: {' '.join(cmd)}", "DEBUG")
        
        dex_files = []
        
        try:
            # 使用subprocess.run，Settingstimeout避免无限Waiting
            self.log("frida-dexdump Process已Starting，开始执行（timeout180秒）...")
            
            # Recording开始time
            start_time = time.time()
            timeout_seconds = 180
            
            # 执行命令并捕获Output
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds
            )
            
            # 解析Output
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                line = line.rstrip('\n')
                if not line:
                    continue
                
                # 解析DEXfileInformation
                dex_info = self.parse_dexdump_output(line)
                if dex_info:
                    dex_files.append(dex_info)
                    # 显示发现的file
                    size_str = f"{dex_info['size_kb']:.1f}KB"
                    if dex_info['size_mb'] >= 0.1:
                        size_str = f"{dex_info['size_mb']:.2f}MB"
                    
                    self.log(f"Found DEX file: {Path(dex_info['path']).name} ({size_str})", "SUCCESS")
                
                # 显示ProgressInformation
                elif "Searching..." in line:
                    self.log("正在搜索Memory中的DEXfile...")
                elif "Successful found" in line:
                    # 提取找到的DEX数量
                    match = re.search(r'found (\d+) dex', line)
                    if match:
                        count = match.group(1)
                        self.log(f"找到 {count} 个DEXfile", "SUCCESS")
                elif "Starting dump" in line:
                    self.log("开始提取DEXfile...")
                elif "All done" in line:
                    self.log("DEXfile提取完成", "SUCCESS")
                elif "Error" in line or "ERROR" in line:
                    self.log(f"Error: {line}", "ERROR")
                elif self.verbose:
                    # 详细模式下显示所有Output
                    self.log(f"[dexdump] {line}", "DEBUG")
            
            # 检查返回码
            if result.returncode == 0:
                self.log(f"第 {attempt} 次UnpackingExecution successful", "SUCCESS")
                return True, dex_files
            else:
                self.log(f"第 {attempt} 次UnpackingExecution failed，返回码: {result.returncode}", "ERROR")
                return False, dex_files
                
        except Exception as e:
            self.log(f"执行frida-dexdump时发生Exception: {e}", "ERROR")
            return False, dex_files
    
    def merge_dex_files(self, all_dex_lists: List[List[Dict]]) -> List[Dict]:
        """合并多次Unpacking的result，去重"""
        self.log("合并多次Unpackingresult...")
        
        # 使用MD5作为唯一标识去重
        unique_dex_files = {}
        
        for dex_list in all_dex_lists:
            for dex_info in dex_list:
                md5 = dex_info['md5']
                if md5 not in unique_dex_files:
                    unique_dex_files[md5] = dex_info
                else:
                    # 如果已有相同MD5，保留Path更完整的
                    existing = unique_dex_files[md5]
                    if 'path' in dex_info and 'path' in existing:
                        if len(dex_info['path']) > len(existing['path']):
                            unique_dex_files[md5] = dex_info
        
        merged_list = list(unique_dex_files.values())
        self.log(f"合并后共 {len(merged_list)} 个唯一DEXfile", "SUCCESS")
        
        return merged_list
    
    def execute_multi_attempt_dexdump(self, package_name: str, output_dir: str) -> Tuple[bool, List[Dict]]:
        """执行多次Unpacking尝试"""
        all_dex_lists = []
        
        for attempt in range(1, self.max_attempts + 1):
            self.log(f"\n{'='*40}")
            self.log(f"第 {attempt}/{self.max_attempts} 次Unpacking尝试")
            self.log(f"{'='*40}")
            
            # 每次尝试前Waiting一段time
            if attempt > 1:
                wait_time = 30 * attempt  # 递增Waitingtime
                self.log(f"Waiting {wait_time} 秒后再次尝试...")
                time.sleep(wait_time)
                
                # 重新StartingApplication
                self.start_application(package_name)
            
            success, dex_files = self.execute_single_dexdump(package_name, output_dir, attempt)
            
            if success and dex_files:
                all_dex_lists.append(dex_files)
                self.log(f"第 {attempt} 次Unpacking获得 {len(dex_files)} 个DEXfile")
            else:
                self.log(f"第 {attempt} 次Unpacking未获得DEXfile", "WARNING")
        
        # 合并result
        if all_dex_lists:
            merged_dex_files = self.merge_dex_files(all_dex_lists)
            return True, merged_dex_files
        else:
            return False, []
    

    

    
    def _get_expected_md5(self, dex_filename: str) -> Optional[str]:
        """从已收集的DEXfileInformation中获取期望的MD5值"""
        for dex_info in self.all_dex_files:
            if Path(dex_info['path']).name == dex_filename:
                return dex_info['md5']
        return None
    
    def _verify_dex_complete(self, dex_path: Path, expected_md5: str = None) -> Dict:
        """
        完整的DEXfileVerification
        包括CRC32、SHA-1、MD5和DEX结构Verification
        """
        results = {
            'filename': dex_path.name,
            'is_valid': False,
            'checks': [],
            'file_size': 0,
            'actual_md5': None,
            'expected_md5': expected_md5,
            'md5_match': None,
            'magic': None,
            'version': None,
            'crc32_valid': None,
            'sha1_valid': None,
            'dex_structure_valid': None
        }
        
        try:
            # Reading整个file
            with open(dex_path, 'rb') as f:
                data = f.read()
            
            results['file_size'] = len(data)
            
            # 检查1: 最小filesize
            if len(data) >= 0x24:  # 至少需要36字节的DEXfile头
                results['checks'].append({'check': 'min_size', 'result': 'PASS', 'message': f"filesize足够: {len(data)} 字节"})
            else:
                results['checks'].append({'check': 'min_size', 'result': 'FAIL', 'message': f"filesize不足: {len(data)} 字节（需要至少36字节）"})
                return results
            
            # 检查2: DEXfile头魔数
            magic = data[0:4]
            results['magic'] = magic.hex()
            
            if magic in [b'dex\n', b'dey\n']:
                results['checks'].append({'check': 'magic', 'result': 'PASS', 'message': f"DEXfile头: {magic.decode('ascii', errors='replace')}"})
            else:
                results['checks'].append({'check': 'magic', 'result': 'FAIL', 'message': f"无效的DEXfile头: 0x{magic.hex()}"})
                return results
            
            # 检查3: Version号
            if len(data) >= 8:
                version = data[4:8]
                results['version'] = version.decode('ascii', errors='replace')
                results['checks'].append({'check': 'version', 'result': 'INFO', 'message': f"DEXVersion: {results['version']}"})
            
            # 检查4: CRC32校验（偏移0x8）
            if len(data) >= 12:
                # 提取file头中的CRC32（小端序）
                expected_crc32 = struct.unpack('<I', data[8:12])[0]
                
                # 计算实际CRC32（从偏移0x12开始到file末尾）
                # Note：根据DEX格式规范，CRC32计算从file头偏移0x12开始
                actual_crc32 = zlib.crc32(data[12:]) & 0xffffffff
                
                results['crc32_valid'] = expected_crc32 == actual_crc32
                if results['crc32_valid']:
                    results['checks'].append({'check': 'crc32', 'result': 'PASS', 'message': f"CRC32校验通过: 0x{expected_crc32:08x}"})
                else:
                    results['checks'].append({'check': 'crc32', 'result': 'FAIL', 'message': f"CRC32校验Failed: 期望0x{expected_crc32:08x}, 实际0x{actual_crc32:08x}"})
            
            # 检查5: SHA-1签名Verification（偏移0xC，20字节）
            if len(data) >= 32:
                # 提取file头中的SHA-1（20字节）
                expected_sha1 = data[12:32]
                
                # 计算实际SHA-1（从偏移0x20开始到file末尾）
                actual_sha1 = hashlib.sha1(data[32:]).digest()
                
                results['sha1_valid'] = expected_sha1 == actual_sha1
                if results['sha1_valid']:
                    results['checks'].append({'check': 'sha1', 'result': 'PASS', 'message': f"SHA-1签名Verification通过"})
                else:
                    results['checks'].append({'check': 'sha1', 'result': 'FAIL', 'message': f"SHA-1签名VerificationFailed"})
            
            # 检查6: filesize字段Verification（偏移0x20）
            if len(data) >= 0x24:
                expected_size = struct.unpack('<I', data[0x20:0x24])[0]
                size_valid = expected_size == len(data)
                if size_valid:
                    results['checks'].append({'check': 'file_size_field', 'result': 'PASS', 'message': f"filesize字段正确: {expected_size} 字节"})
                else:
                    results['checks'].append({'check': 'file_size_field', 'result': 'FAIL', 'message': f"filesize字段不匹配: 期望{expected_size}, 实际{len(data)}"})
            
            # 检查7: MD5Verification
            actual_md5 = hashlib.md5(data).hexdigest()
            results['actual_md5'] = actual_md5
            
            if expected_md5:
                results['md5_match'] = actual_md5.lower() == expected_md5.lower()
                if results['md5_match']:
                    results['checks'].append({'check': 'md5', 'result': 'PASS', 'message': f"MD5匹配: {actual_md5}"})
                else:
                    results['checks'].append({'check': 'md5', 'result': 'FAIL', 'message': f"MD5不匹配: 期望{expected_md5}, 实际{actual_md5}"})
            else:
                results['checks'].append({'check': 'md5', 'result': 'INFO', 'message': f"计算MD5: {actual_md5}"})
            
            # 检查8: DEX基本结构Verification
            # Verificationfile头中的各个偏移量是否在file范围内
            dex_structure_ok = True
            dex_structure_messages = []
            
            if len(data) >= 0x70:  # 足够Reading所有file头Information
                # Reading各个表的size和偏移
                try:
                    string_ids_size = struct.unpack('<I', data[0x38:0x3c])[0]
                    string_ids_off = struct.unpack('<I', data[0x3c:0x40])[0]
                    
                    type_ids_size = struct.unpack('<I', data[0x40:0x44])[0]
                    type_ids_off = struct.unpack('<I', data[0x44:0x48])[0]
                    
                    # 检查偏移是否在file范围内
                    if string_ids_off + string_ids_size * 4 > len(data):
                        dex_structure_ok = False
                        dex_structure_messages.append(f"字符串表超出file范围")
                    else:
                        dex_structure_messages.append(f"字符串表: {string_ids_size} 项")
                    
                    if type_ids_off + type_ids_size * 4 > len(data):
                        dex_structure_ok = False
                        dex_structure_messages.append(f"类型表超出file范围")
                    else:
                        dex_structure_messages.append(f"类型表: {type_ids_size} 项")
                
                except struct.error:
                    dex_structure_ok = False
                    dex_structure_messages.append(f"无法解析DEX结构")
            
            results['dex_structure_valid'] = dex_structure_ok
            if dex_structure_ok:
                results['checks'].append({'check': 'dex_structure', 'result': 'PASS', 'message': f"DEX结构基本有效: {', '.join(dex_structure_messages)}"})
            else:
                results['checks'].append({'check': 'dex_structure', 'result': 'WARNING', 'message': f"DEX结构可能有问题: {', '.join(dex_structure_messages)}"})
            
            # 综合判断
            # 要求：魔数正确 + CRC32有效 + SHA-1有效（如果存在）
            all_passed = True
            for check in results['checks']:
                if check['result'] == 'FAIL':
                    all_passed = False
                    break
            
            results['is_valid'] = all_passed
            
            return results
            
        except Exception as e:
            results['checks'].append({'check': 'general', 'result': 'ERROR', 'message': f"Verification过程中发生Exception: {str(e)}"})
            return results
    
    def verify_dex_integrity(self, output_dir: str) -> Dict:
        """VerificationDEXfile完整性"""
        self.log("开始VerificationDEXfile完整性...")
        
        output_path = Path(output_dir)
        verification_results = {
            'total_files': 0,
            'valid_files': 0,
            'invalid_files': 0,
            'details': []
        }
        
        # 查找所有.dexfile
        dex_files = list(output_path.glob("*.dex"))
        verification_results['total_files'] = len(dex_files)
        
        if not dex_files:
            self.log("未找到DEXfile", "WARNING")
            return verification_results
        
        self.log(f"找到 {len(dex_files)} 个DEXfile进行Verification")
        
        # 特别检查dynamic loading的DEX（如baiduprotect*.dex）
        baidu_files = list(output_path.glob("baiduprotect*.dex"))
        if baidu_files:
            self.log(f"Found {len(baidu_files)} Baidu protection related DEX files", "SUCCESS")
        
        for dex_file in dex_files:
            # 获取期望的MD5值（如果已Recording）
            expected_md5 = self._get_expected_md5(dex_file.name)
            
            # 执行完整的DEXVerification
            complete_validation = self._verify_dex_complete(dex_file, expected_md5)
            
            # 将完整Verificationresult转换为兼容格式
            file_info = {
                'filename': dex_file.name,
                'path': str(dex_file),
                'size_bytes': complete_validation['file_size'],
                'is_valid': complete_validation['is_valid'],
                'checks': complete_validation['checks'],
                'complete_validation': {
                    'magic': complete_validation['magic'],
                    'version': complete_validation['version'],
                    'crc32_valid': complete_validation['crc32_valid'],
                    'sha1_valid': complete_validation['sha1_valid'],
                    'dex_structure_valid': complete_validation['dex_structure_valid'],
                    'actual_md5': complete_validation['actual_md5'],
                    'expected_md5': complete_validation['expected_md5'],
                    'md5_match': complete_validation['md5_match']
                }
            }
            
            if complete_validation['is_valid']:
                verification_results['valid_files'] += 1
                
                # 检查是否有任何FAIL的Verification项
                has_fail = any(check['result'] == 'FAIL' for check in complete_validation['checks'])
                has_critical_fail = any(check['result'] == 'FAIL' and check['check'] in ['crc32', 'sha1', 'md5'] for check in complete_validation['checks'])
                
                if has_critical_fail:
                    self.log(f"⚠️  {dex_file.name} - 关键校验Failed", "WARNING")
                elif has_fail:
                    self.log(f"⚠️  {dex_file.name} - 部分VerificationFailed", "WARNING")
                else:
                    self.log(f"✅ {dex_file.name} - 完整Verification通过", "SUCCESS")
            else:
                verification_results['invalid_files'] += 1
                self.log(f"❌ {dex_file.name} - Verification未通过", "ERROR")
            
            verification_results['details'].append(file_info)
        
        # Summary - 添加完整的Verification统计
        success_rate = (verification_results['valid_files'] / verification_results['total_files'] * 100) if verification_results['total_files'] > 0 else 0
        
        # 计算详细Verification统计
        crc32_passed = 0
        sha1_passed = 0
        md5_matched = 0
        structure_valid = 0
        
        for detail in verification_results['details']:
            if 'complete_validation' in detail:
                cv = detail['complete_validation']
                if cv.get('crc32_valid') is True:
                    crc32_passed += 1
                if cv.get('sha1_valid') is True:
                    sha1_passed += 1
                if cv.get('md5_match') is True:
                    md5_matched += 1
                if cv.get('dex_structure_valid') is True:
                    structure_valid += 1
        
        self.log(f"完整性Verification完成: {verification_results['valid_files']}/{verification_results['total_files']} 个file有效 ({success_rate:.1f}%)", "SUCCESS")
        self.log(f"📊 详细Verification统计:", "INFO")
        self.log(f"  - CRC32校验通过: {crc32_passed}/{verification_results['total_files']}", "INFO")
        self.log(f"  - SHA-1签名通过: {sha1_passed}/{verification_results['total_files']}", "INFO")
        self.log(f"  - MD5匹配Verification: {md5_matched}/{verification_results['total_files']}", "INFO")
        self.log(f"  - DEX结构有效: {structure_valid}/{verification_results['total_files']}", "INFO")
        
        return verification_results
    
    def generate_enhanced_report(self, package_name: str, output_dir: str, dex_files: List[Dict], verification_results: Dict) -> str:
        """生成增强版执行Report"""
        report_path = Path(output_dir) / "enhanced_dexdump_report.md"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# 增强版UnpackingReport\n\n")
            f.write("## ReportInformation\n")
            f.write(f"- **目标Application**: {package_name}\n")
            f.write(f"- **OutputDirectory**: {output_dir}\n")
            f.write(f"- **Unpacking策略**: {self.max_attempts} 次尝试 + Feature触发\n")
            
            # 添加搜索模式Information
            if self.deep_search:
                f.write(f"- **搜索模式**: 深度搜索模式 (-dParameter)\n")
                f.write(f"- **模式说明**: 针对新百度reinforcement等强力protection，可突破26个DEX限制\n")
                f.write(f"- **成功案例**: com.example.app 从26个突破到53个DEX\n")
            else:
                f.write(f"- **搜索模式**: 普通搜索模式\n")
            
            f.write(f"- **开始time**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **结束time**: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if self.start_time and self.end_time:
                duration = (self.end_time - self.start_time).total_seconds()
                f.write(f"- **执行耗时**: {duration:.1f} 秒\n")
            
            # DEXfile统计
            f.write("\n## DEXfile统计\n")
            f.write(f"- **提取file数**: {len(dex_files)}\n")
            f.write(f"- **Verification有效数**: {verification_results['valid_files']}\n")
            f.write(f"- **Verification无效数**: {verification_results['invalid_files']}\n")
            
            # filesize分布
            if dex_files:
                total_size = sum(d['size_bytes'] for d in dex_files)
                avg_size = total_size / len(dex_files) if len(dex_files) > 0 else 0
                max_file = max(dex_files, key=lambda x: x['size_bytes']) if dex_files else None
                min_file = min(dex_files, key=lambda x: x['size_bytes']) if dex_files else None
                
                f.write(f"- **总size**: {total_size/1024/1024:.2f} MB\n")
                f.write(f"- **平均size**: {avg_size/1024:.2f} KB\n")
                if max_file:
                    f.write(f"- **最大file**: {Path(max_file['path']).name} ({max_file['size_bytes']/1024/1024:.2f} MB)\n")
                if min_file:
                    f.write(f"- **最小file**: {Path(min_file['path']).name} ({min_file['size_bytes']} 字节)\n")
            
            # file列表
            if dex_files:
                f.write("\n## 提取的DEXfile\n")
                f.write("| file名 | size | MD5 | Status |\n")
                f.write("|--------|------|-----|------|\n")
                
                # 按file名排序
                sorted_dex = sorted(dex_files, key=lambda x: Path(x['path']).name)
                
                for dex_info in sorted_dex:
                    filename = Path(dex_info['path']).name
                    size_str = f"{dex_info['size_kb']:.1f}KB"
                    if dex_info['size_mb'] >= 0.1:
                        size_str = f"{dex_info['size_mb']:.2f}MB"
                    
                    # 查找VerificationStatus
                    status = "未知"
                    for detail in verification_results['details']:
                        if detail['filename'] == filename:
                            status = "有效" if detail['is_valid'] else "无效"
                            break
                    
                    f.write(f"| {filename} | {size_str} | {dex_info['md5']} | {status} |\n")
            
            # VerificationDetails
            f.write("\n## integrityVerificationDetails\n")
            
            # 添加完整Verification统计摘要
            crc32_passed = 0
            sha1_passed = 0
            md5_matched = 0
            structure_valid = 0
            
            for detail in verification_results['details']:
                if 'complete_validation' in detail:
                    cv = detail['complete_validation']
                    if cv.get('crc32_valid') is True:
                        crc32_passed += 1
                    if cv.get('sha1_valid') is True:
                        sha1_passed += 1
                    if cv.get('md5_match') is True:
                        md5_matched += 1
                    if cv.get('dex_structure_valid') is True:
                        structure_valid += 1
            
            f.write("### 完整Verification统计\n")
            f.write(f"- **CRC32校验通过**: {crc32_passed}/{verification_results['total_files']}\n")
            f.write(f"- **SHA-1签名通过**: {sha1_passed}/{verification_results['total_files']}\n")
            f.write(f"- **MD5匹配Verification**: {md5_matched}/{verification_results['total_files']}\n")
            f.write(f"- **DEX结构有效**: {structure_valid}/{verification_results['total_files']}\n")
            
            # 各个fileVerificationDetails
            for detail in verification_results['details']:
                f.write(f"\n### {detail['filename']}\n")
                f.write(f"- **filesize**: {detail['size_bytes']} 字节\n")
                f.write(f"- **VerificationStatus**: {'✅ 有效' if detail['is_valid'] else '❌ 无效'}\n")
                
                # 显示完整Verificationresult（如果有）
                if 'complete_validation' in detail:
                    cv = detail['complete_validation']
                    f.write("- **完整VerificationInformation**:\n")
                    if cv.get('magic'):
                        f.write(f"  - DEX魔数: 0x{cv['magic']} ({bytes.fromhex(cv['magic']).decode('ascii', errors='replace')})\n")
                    if cv.get('version'):
                        f.write(f"  - DEXVersion: {cv['version']}\n")
                    if cv.get('crc32_valid') is not None:
                        status = "✅ 通过" if cv['crc32_valid'] else "❌ Failed"
                        f.write(f"  - CRC32校验: {status}\n")
                    if cv.get('sha1_valid') is not None:
                        status = "✅ 通过" if cv['sha1_valid'] else "❌ Failed"
                        f.write(f"  - SHA-1签名: {status}\n")
                    if cv.get('dex_structure_valid') is not None:
                        status = "✅ 有效" if cv['dex_structure_valid'] else "⚠️ 可能有问题"
                        f.write(f"  - DEX结构: {status}\n")
                    if cv.get('actual_md5'):
                        f.write(f"  - 计算MD5: {cv['actual_md5']}\n")
                        if cv.get('expected_md5'):
                            status = "✅ 匹配" if cv.get('md5_match') else "❌ 不匹配"
                            f.write(f"  - MD5匹配: {status} (期望: {cv['expected_md5']})\n")
                
                f.write("- **检查Project**:\n")
                for check in detail['checks']:
                    status_emoji = "✅" if check['result'] == 'PASS' else "⚠️" if check['result'] == 'WARNING' else "ℹ️" if check['result'] == 'INFO' else "❌"
                    f.write(f"  - {status_emoji} {check['check']}: {check['message']}\n")
            
            # 执行Log
            f.write("\n## 执行Log\n")
            f.write("```\n")
            for log_entry in self.execution_log:
                f.write(f"{log_entry}\n")
            f.write("```\n")
        
        self.log(f"增强版Report已生成: {report_path}", "SUCCESS")
        return str(report_path)
    
    def run(self, package_name: str, output_dir: str) -> bool:
        """增强版Unpacking主执行流程"""
        self.log("=" * 60)
        self.log("增强版Unpacking执行器 - 基于文档Description的完整方案")
        self.log("针对新百度reinforcement等商业reinforcementOptimizing")
        
        # 显示模式Information
        mode_info = "普通模式"
        if self.deep_search:
            mode_info = "深度搜索模式 (-dParameter)"
            self.log(f"📊 模式: {mode_info} - 针对新百度reinforcement等强力protection")
            self.log("💡 经验: 可突破26个DEX限制，完整获取53个DEX")
            self.log("💡 案例: com.example.app 从26个突破到53个DEX")
        else:
            self.log(f"📊 模式: {mode_info} - 普通商业reinforcement")
        
        self.log("=" * 60)
        
        self.start_time = datetime.now()
        
        # 1. Environment检查
        if not self.check_environment():
            return False
        
        # 2. 检查Application是否Installing
        if not self.check_package_installed(package_name):
            return False
        
        # 3. StartingApplication
        self.log("StartingApplication...")
        if not self.start_application(package_name):
            self.log("ApplicationStarting可能有问题，但仍ResumingUnpacking", "WARNING")
        
        # 4. WaitingApplication加载
        if not self.wait_for_application_load(wait_time=30):
            self.log("Application加载Waiting可能有问题，但仍ResumingUnpacking", "WARNING")
        
        # 5. 执行FridaUnpacking
        self.log("执行FridaUnpacking...")
        self.log("💡 当前策略：专注FridaDebugging", "INFO")
        
        # FridaUnpacking
        success, all_dex_files = self.execute_multi_attempt_dexdump(package_name, output_dir)
        
        # 如果FridaUnpackingFailed，直接返回Failed
        if not success:
            self.log("FridaUnpackingFailed，专注FridaDebugging模式结束", "ERROR")
            self.log("Failedanalysis:", "INFO")
            self.log("1. 检查Application是否正常运行且无强Anti-debug", "INFO")
            self.log("2. 检查Frida-server是否正常运行且已Hiding特征", "INFO")
            self.log("3. 尝试不同的ApplicationStarting时机和注入策略", "INFO")
            self.log("4. 确认Anti-debugBypassModule是否正确执行", "INFO")
            self.log("⚠️ Note：当前模式专注FridaUnpacking", "WARNING")
            return False
        
        # 6. Verificationintegrity
        verification_results = self.verify_dex_integrity(output_dir)
        
        self.end_time = datetime.now()
        
        # 7. 生成Report
        report_path = self.generate_enhanced_report(package_name, output_dir, all_dex_files, verification_results)
        
        # 8. 最终Summary
        self.log("=" * 60)
        self.log("增强版Unpacking任务完成!", "SUCCESS")
        self.log(f"- 提取DEXfile: {len(all_dex_files)} 个")
        self.log(f"- 有效DEXfile: {verification_results['valid_files']} 个")
        self.log(f"- 百度protectionDEX: {len([f for f in all_dex_files if 'baiduprotect' in Path(f['path']).name.lower()])} 个")
        self.log(f"- 详细Report: {report_path}")
        
        # UnpackingresultSummary
        actual_count = len(all_dex_files)
        self.log(f"- 动态获取: {actual_count} 个DEXfile")
        
        # 深度搜索模式result评估
        if self.deep_search:
            if actual_count >= 53:
                self.log(f"✅ 深度搜索成功! 获得 {actual_count} 个DEXfile (超过53个)", "SUCCESS")
                self.log(f"💡 说明: 已突破新百度reinforcement的26个DEX限制", "INFO")
            elif actual_count >= 26:
                self.log(f"⚠️  深度搜索部分成功: 获得 {actual_count} 个DEXfile", "WARNING")
                self.log(f"💡 说明: Broke through normal mode limits, but there may still be undiscovered DEX", "INFO")
            else:
                self.log(f"❌ 深度搜索效果不佳: 仅获得 {actual_count} 个DEXfile", "ERROR")
                self.log(f"💡 Recommendation: 尝试增加Waitingtime、多次尝试或检查Anti-debug机制", "INFO")
        else:
            # 普通模式评估
            if actual_count >= 26:
                self.log(f"✅ 普通模式成功: 获得 {actual_count} 个DEXfile", "SUCCESS")
            elif actual_count >= 10:
                self.log(f"⚠️  普通模式部分成功: 获得 {actual_count} 个DEXfile", "WARNING")
                self.log(f"💡 Recommendation: 如需更多DEXfile，请尝试 --deep-search Parameter", "INFO")
            else:
                self.log(f"❌ 普通模式效果不佳: 仅获得 {actual_count} 个DEXfile", "ERROR")
                self.log(f"💡 Recommendation: 请尝试 --deep-search Parameter或检查EnvironmentConfiguration", "INFO")
        
        self.log("=" * 60)
        
        return True

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='增强版Unpacking执行器 - 针对新百度reinforcementOptimizing')
    parser.add_argument('--package', '-p', required=True, help='AndroidApplicationPackage name')
    parser.add_argument('--output', '-o', default='./enhanced_dex_output', help='OutputDirectory (默认: ./enhanced_dex_output)')
    parser.add_argument('--attempts', '-a', type=int, default=3, help='Unpacking尝试次数 (默认: 3)')
    parser.add_argument('--deep-search', '-d', action='store_true', help='启用深度搜索模式 (针对新百度reinforcement等强力protection)')
    parser.add_argument('--bypass-antidebug', '-b', action='store_true', help='启用Anti-debugBypass（针对强力Anti-debugprotection）')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细Output模式')
    
    args = parser.parse_args()
    
    runner = EnhancedDexDumpRunner(
        verbose=args.verbose, 
        max_attempts=args.attempts, 
        deep_search=args.deep_search,
        bypass_antidebug=args.bypass_antidebug
    )
    success = runner.run(args.package, args.output)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()