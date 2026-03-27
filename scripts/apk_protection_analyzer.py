#!/usr/bin/env python3
"""
APK reinforcement Type Analyzer
Directly analyze APK files，Detect reinforcement types and protection levels used
"""

import os
import sys
import zipfile
import re
import json
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import struct
import binascii

class ApkprotectionAnalyzer:
    """APKreinforcementanalysis器"""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.apk_path = ""
        self.analysis_results = {
            "apk_file": "",
            "file_size": 0,
            "protection_type": "unknown",
            "protection_level": "unknown",
            "detected_vendors": [],
            "confidence_score": 0.0,
            "detailed_findings": {},
            "recommendations": []
        }
        
        # reinforcement feature library
        self.protection_patterns = {
            # 爱encryption
            "ijiami": [
                (r"libijiami.*\.so$", "strong"),
                (r"libexec.*\.so$", "strong"),
                (r"libexecmain.*\.so$", "strong"),
                (r"libdvm.*\.so$", "strong"),
                (r"libsecexe.*\.so$", "strong"),
                (r"libsecmain.*\.so$", "strong"),
                (r"ijiami.*\.dat$", "medium"),
                (r"ijiami.*\.xml$", "medium"),
                (r"\.ijiami\.", "weak"),
            ],
            # 360reinforcement
            "360": [
                (r".*libjiagu.*\.so$", "strong"),           # 任意Directory下的libjiagulibrary
                (r"assets/libjiagu.*\.so$", "strong"),      # assetsDirectory下的jiagulibrary（重点）
                (r"lib360\.so$", "strong"),
                (r"jiagu\.dex$", "strong"),
                (r"protect\.jar$", "medium"),
                (r".*360.*\.so$", "medium"),                # 任何360.sofile
                (r"assets/.*360.*", "weak"),                # assets中的360file
                (r"assets/.*jiagu.*", "strong"),            # assets中的jiagufile
                (r".*jiagu.*", "weak"),                     # file名包含jiagu
            ],
            # 百度reinforcement
            "baidu": [
                (r"baiduprotect.*\.dex$", "strong"),
                (r"baiduprotect.*\.i\.dex$", "strong"),  # 新百度reinforcement中间DEXfile
                (r"libbaiduprotect.*\.so$", "strong"),
                (r"libbdprotect.*\.so$", "strong"),
                (r"protect\.jar$", "medium"),
                (r"baiduprotect.*\.jar$", "medium"),  # 百度reinforcementJARfile
            ],
            # 腾讯reinforcement
            "tencent": [
                (r"libshell.*\.so$", "strong"),
                (r"libtprotect.*\.so$", "strong"),
                (r"libstub\.so$", "strong"),
                (r"libAntiCheat\.so$", "strong"),  # 腾讯游戏Security(ACE)反作弊核心library
                (r"tps\.jar$", "medium"),
                (r"libmain\.so$", "weak"),  # Note: 也可能是普通library
            ],
            # 阿里reinforcement
            "ali": [
                (r"libmobisec.*\.so$", "strong"),
                (r"aliprotect\.dex$", "strong"),
                (r"aliprotect\.jar$", "medium"),
            ],
            # 梆梆reinforcement
            "bangcle": [
                (r"libbangcle.*\.so$", "strong"),
                (r"libbc.*\.so$", "strong"),
                (r"bangcle\.jar$", "medium"),
                # 梆梆reinforcement企业版特征
                (r"libdexjni\.so$", "strong"),
                (r"libDexHelper\.so$", "strong"),
                (r"libdexjni.*\.so$", "strong"),  # 变体
                (r"libdexhelper.*\.so$", "strong"),  # 变体
            ],
            # 娜迦reinforcement
            "naga": [
                (r"libnaga.*\.so$", "strong"),
                (r"libng.*\.so$", "strong"),
            ],
            # 顶象reinforcement
            "dingxiang": [
                (r"libdxp.*\.so$", "strong"),
                (r"libdx\.so$", "strong"),
            ],
            # 网易易盾
            "netease": [
                (r"libnesec\.so$", "strong"),
                (r"libneso\.so$", "strong"),
            ],
            # 几维Security（KiwiVM/奇安信/奇虎360）
            "kiwivm": [
                (r"libKwProtectSDK\.so$", "strong"),
                (r"libkiwi.*\.so$", "strong"),           # libkiwi_dumper.so, libkiwicrash.so
                (r"libkwsdataenc\.so$", "strong"),
                (r"libkadp\.so$", "strong"),
                (r"com\.kiwivm\.security\.StubApplication", "strong"),  # Application类
            ],
        }
        
        # 白名单（不视为reinforcement）
        self.sdk_whitelist = [
            r".*BaiduSpeechSDK.*",
            r".*baidumap.*",
            r".*AMapSDK.*",
            r".*bugly.*",
            r".*qq.*",
            r".*wechat.*",
            r".*alipay.*",
            r".*alivc.*",       # 阿里云视频SDK
            r".*aliyun.*",      # 阿里云通用SDK
            r".*alibaba.*",     # 阿里巴巴SDK
            r".*umeng.*",
            r".*tencent.*\.so$",  # Note：排除腾讯SDK，但不是libtprotect.so
            r"^libc\.so$",
            r"^libz\.so$",
            r"^liblog\.so$",
            r"^libm\.so$",
            r"^libdl\.so$",
            # 常见Application自有encryption/Securitylibrary（非reinforcement特征）
            r".*Encryptor.*",
            r".*encrypt.*",
            r".*crypto.*",
            r".*security.*",
            r".*secure.*",
            r".*safe.*",
            # r".*protect.*",  # Note：可能是reinforcement，但排除常见Application自有protectionlibrary - 暂时注释，避免漏报百度reinforcement
            r".*guard.*",
            r".*shield.*",
            r".*defense.*",
            r".*armor.*",
            r".*obfuscate.*",
            r".*antidebug.*",
            r".*anti.*debug.*",
            # 常见SDKlibrary
            r".*volc.*",
            r".*tx.*",
            r".*apminsight.*",
            r".*mmkv.*",
            r".*liteav.*",
            r".*rive.*",
            r".*CtaApi.*",
        ]
    
    def log(self, message: str, level: str = "INFO"):
        """RecordingLog"""
        if self.verbose or level in ["WARNING", "ERROR"]:
            prefix = {
                "INFO": "📝",
                "SUCCESS": "✅",
                "WARNING": "⚠️",
                "ERROR": "❌",
                "DEBUG": "🔍"
            }.get(level, "📝")
            print(f"{prefix} {message}")
    

    def analyze_apk(self, apk_path: str) -> Dict:
        """analysisAPKfilereinforcement类型"""
        if not os.path.exists(apk_path):
            self.log(f"APKfile不存在: {apk_path}", "ERROR")
            return self.analysis_results
        
        self.apk_path = apk_path
        self.analysis_results["apk_file"] = os.path.basename(apk_path)
        self.analysis_results["file_size"] = os.path.getsize(apk_path)
        
        self.log("=" * 60)
        self.log("🔍 APKreinforcement类型analysis")
        self.log(f"目标file: {os.path.basename(apk_path)}")
        self.log(f"filesize: {self.analysis_results['file_size'] / (1024*1024):.1f} MB")
        self.log("=" * 60)
        
        try:
            with zipfile.ZipFile(apk_path, 'r') as apk_zip:
                # 1. Analyze DEX files
                dex_analysis = self.analyze_dex_files(apk_zip)
                
                # 2. analysisnative library
                native_lib_analysis = self.analyze_native_libs(apk_zip)
                
                # 3. Analyze AndroidManifest.xml
                manifest_analysis = self.analyze_manifest(apk_zip)
                
                # 4. Analyze resource files
                resource_analysis = self.analyze_resources(apk_zip)
                
                # 5. 综合判断
                self.calculate_protection_level(
                    dex_analysis, 
                    native_lib_analysis, 
                    manifest_analysis, 
                    resource_analysis
                )
                
                # 7. 生成Recommendation
                self.generate_recommendations()
                
        except Exception as e:
            self.log(f"analysisAPKFailed: {e}", "ERROR")
        
        return self.analysis_results
    
    def analyze_dex_files(self, apk_zip: zipfile.ZipFile) -> Dict:
        """analysisDEXfile特征"""
        self.log("analysisDEXfile...")
        
        dex_files = [f for f in apk_zip.namelist() if f.endswith('.dex')]
        results = {
            "dex_count": len(dex_files),
            "dex_files": dex_files,
            "protection_indicators": [],
            "unusual_patterns": [],
            "dex_headers": [],
            "dex_size_analysis": {}
        }
        
        if len(dex_files) == 0:
            self.log("❌ 未找到DEXfile", "WARNING")
            results["unusual_patterns"].append("no_dex_files")
        elif len(dex_files) == 1:
            self.log(f"✅ Found {len(dex_files)} DEX files: {dex_files[0]}")
            # 单DEX可能是reinforcement特征
            if "classes.dex" in dex_files:
                # 深度Analyze DEX files头
                dex_analysis = self.deep_analyze_dex(apk_zip, dex_files[0])
                results["dex_headers"].append(dex_analysis)
                results["dex_size_analysis"][dex_files[0]] = dex_analysis
        else:
            self.log(f"✅ Found {len(dex_files)} DEX files")
            # analysis第一个DEXfile作为样本
            if dex_files and "classes.dex" in dex_files:
                dex_analysis = self.deep_analyze_dex(apk_zip, "classes.dex")
                results["dex_headers"].append(dex_analysis)
                results["dex_size_analysis"]["classes.dex"] = dex_analysis
        
        # 检查reinforcement特征DEX
        for dex_file in dex_files:
            for vendor, patterns in self.protection_patterns.items():
                for pattern, strength in patterns:
                    if re.search(pattern, dex_file, re.IGNORECASE):
                        if not self.is_whitelisted(dex_file):
                            results["protection_indicators"].append({
                                "type": "dex",
                                "vendor": vendor,
                                "file": dex_file,
                                "strength": strength,
                                "pattern": pattern
                            })
        
        return results
    
    def deep_analyze_dex(self, apk_zip: zipfile.ZipFile, dex_file: str) -> Dict:
        """深度analysisDEXfile头"""
        try:
            with apk_zip.open(dex_file) as f:
                # ReadingDEXfile头部（前112字节包含关键Information）
                data = f.read(112)
                if len(data) < 8:
                    return {"status": "error", "reason": "file太小"}
                
                # 检查DEX魔数
                magic = data[0:8]
                is_valid_dex = magic in [b'dex\n035\x00', b'dex\n036\x00', b'dex\n037\x00', b'dex\n038\x00', b'dex\n039\x00']
                
                # 检查filesize（从偏移0x20开始，4字节小端）
                if len(data) >= 0x24:
                    file_size = struct.unpack('<I', data[0x20:0x24])[0]
                else:
                    file_size = 0
                
                # 检查校验和（偏移0x08，4字节小端）
                if len(data) >= 0x0C:
                    checksum = struct.unpack('<I', data[0x08:0x0C])[0]
                else:
                    checksum = 0
                
                # 检查签名（偏移0x0C，20字节SHA-1）
                if len(data) >= 0x20:
                    signature = data[0x0C:0x20].hex()
                else:
                    signature = ""
                
                # analysisresult
                result = {
                    "status": "success",
                    "magic": magic.hex(),
                    "is_valid_dex": is_valid_dex,
                    "file_size": file_size,
                    "checksum": checksum,
                    "signature": signature,
                    "analysis": {}
                }
                
                # 判断是否encryption或Obfuscating
                if not is_valid_dex:
                    result["analysis"]["warning"] = "DEX魔数Exception，可能被encryption或Modifying"
                    # 尝试检查是否为常见的reinforcement特征
                    if magic[0:4] == b'\x00\x00\x00\x00':
                        result["analysis"]["suspicion"] = "可能为零填充encryption"
                else:
                    result["analysis"]["conclusion"] = "标准DEX格式，可能未encryption"
                    
                    # 检查是否有常见的reinforcement特征
                    # Reading更多Data检查是否有明显的encryption模式
                    f.seek(0)
                    sample_data = f.read(1024)
                    zero_count = sample_data.count(b'\x00')
                    if zero_count > 512:  # 超过50%为零
                        result["analysis"]["suspicion"] = "高零值比例，可能为简单encryption或填充"
                
                return result
                
        except Exception as e:
            return {"status": "error", "reason": str(e)}
    
    def analyze_native_libs(self, apk_zip: zipfile.ZipFile) -> Dict:
        """analysis原生library特征"""
        self.log("Analyzing native library files...")
        
        # 检查所有.sofile，包括assets/Directory下的reinforcementlibrary
        lib_files = [f for f in apk_zip.namelist() if f.endswith('.so')]
        results = {
            "lib_count": len(lib_files),
            "lib_files": lib_files,
            "protection_indicators": [],
            "security_libs": [],
            "sdk_libs": []
        }
        
        if len(lib_files) == 0:
            self.log("❌ 未找到原生libraryfile", "WARNING")
        else:
            self.log(f"✅ Found {len(lib_files)} native library files")
        
        # 检查reinforcement feature library
        protection_found = False
        for lib_file in lib_files:
            lib_name = os.path.basename(lib_file)
            
            # 检查是否是白名单SDK
            if self.is_whitelisted(lib_file):
                results["sdk_libs"].append(lib_file)
                continue
            
            # 检查reinforcement特征
            vendor_found = False
            for vendor, patterns in self.protection_patterns.items():
                for pattern, strength in patterns:
                    if re.search(pattern, lib_file, re.IGNORECASE):
                        if not vendor_found:  # 避免重复添加
                            results["protection_indicators"].append({
                                "type": "native",
                                "vendor": vendor,
                                "file": lib_file,
                                "strength": strength,
                                "pattern": pattern
                            })
                            vendor_found = True
                            protection_found = True
            
            # 如果没有匹配reinforcement特征，检查是否是其他Securitylibrary
            if not vendor_found:
                security_patterns = [
                    r"protect", r"secure", r"safe", r"guard", r"shield",
                    r"encrypt", r"crypto", r"decrypt", r"obfuscate",
                    r"anti", r"defense", r"security", r"armor"
                ]
                for pattern in security_patterns:
                    if re.search(pattern, lib_name, re.IGNORECASE):
                        results["security_libs"].append(lib_file)
                        break
        
        if protection_found:
            self.log(f"⚠️  Found reinforcement feature library", "WARNING")
        else:
            self.log("✅ No obvious reinforcement feature library found", "SUCCESS")
        
        return results
    
    def analyze_manifest(self, apk_zip: zipfile.ZipFile) -> Dict:
        """analysisAndroidManifest.xml"""
        self.log("Analyzing AndroidManifest.xml...")
        
        results = {
            "manifest_found": False,
            "debuggable": False,
            "backup_allowed": True,
            "protection_indicators": []
        }
        
        try:
            if "AndroidManifest.xml" in apk_zip.namelist():
                results["manifest_found"] = True
                with apk_zip.open("AndroidManifest.xml") as manifest_file:
                    content = manifest_file.read()
                    
                    # 简单文本检查（实际Application中应使用AXML解析器）
                    try:
                        text = content.decode('utf-8', errors='ignore')
                        
                        # 检查Debugging属性
                        if 'android:debuggable="true"' in text:
                            results["debuggable"] = True
                            self.log("⚠️  Application可Debugging (debuggable=true)", "WARNING")
                        
                        # 检查Backing up属性
                        if 'android:allowBackup="false"' in text:
                            results["backup_allowed"] = False
                            self.log("✅ Backing upDisabled (SecurityConfiguration)", "INFO")
                        
                        # 检查reinforcement相关特征
                        if 'com.ijiami' in text:
                            results["protection_indicators"].append({
                                "type": "manifest",
                                "vendor": "ijiami",
                                "indicator": "Package name包含ijiami"
                            })
                        
                    except:
                        pass
            else:
                self.log("❌ 未找到AndroidManifest.xml", "WARNING")
                
        except Exception as e:
            self.log(f"analysisManifestFailed: {e}", "DEBUG")
        
        return results
    
    def analyze_resources(self, apk_zip: zipfile.ZipFile) -> Dict:
        """analysisResourcefile"""
        self.log("Analyzing resource files...")
        
        results = {
            "resource_count": 0,
            "protection_indicators": [],
            "unusual_files": []
        }
        
        file_list = apk_zip.namelist()
        results["resource_count"] = len(file_list)
        
        # reinforcementResourcefile特征模式
        resource_protection_patterns = {
            "ijiami": [
                r"assets/ijiami.*\.dat$",
                r"assets/ijiami.*\.xml$",
                r"ijiami.*\.properties$",
            ],
            "360": [
                r"assets/jiagu.*",
                r"assets/.*360.*\.dat$",
                r"assets/.*360.*\.xml$",
            ],
            "baidu": [
                r"assets/baiduprotect.*",
                r"assets/baidu.*\.dat$",
            ],
            "tencent": [
                r"assets/tprotect.*",
                r"assets/tencent.*\.dat$",
                r"assets/libwbsafeedit.*",  # 腾讯WebSecurity编辑组件
            ],
            "ali": [
                r"assets/aliprotect.*",
                r"assets/alisec.*",
            ],
            "bangcle": [
                r"assets/meta-data/.*",  # 梆梆reinforcement企业版签名fileDirectory
                r"assets/.*bangcle.*",
                r"assets/.*bangele.*",
                r"assets/.*libdexjni.*",
                r"assets/.*libDexHelper.*",
            ],
            # 网易易盾Resourcefile特征
            "netease": [
                r"assets/netease.*",
                r"assets/yidun.*",
                r"assets/nd.*",
                r"assets/libnesec.*",
                r"assets/libneso.*",
            ]
        }
        
        for file_name in file_list:
            # 跳过白名单file
            if self.is_whitelisted(file_name):
                continue
                
            # 检查是否是明显的reinforcementResourcefile
            for vendor, patterns in resource_protection_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, file_name, re.IGNORECASE):
                        results["protection_indicators"].append({
                            "type": "resource",
                            "vendor": vendor,
                            "file": file_name,
                            "pattern": pattern
                        })
                        break  # 找到一个匹配就跳出内层循环
        
        return results
    
    def is_whitelisted(self, file_name: str) -> bool:
        """检查是否在白名单中"""
        for pattern in self.sdk_whitelist:
            if re.search(pattern, file_name, re.IGNORECASE):
                return True
        return False
    
    def analyze_dex_status(self, dex_results: Dict) -> Dict:
        """analysisDEXfileStatus"""
        status = {
            "is_normal_dex": False,
            "is_encrypted": False,
            "is_obfuscated": False,
            "details": []
        }
        
        # 检查DEX头analysisresult
        dex_headers = dex_results.get("dex_headers", [])
        if dex_headers:
            for header_info in dex_headers:
                if header_info.get("status") == "success":
                    is_valid = header_info.get("is_valid_dex", False)
                    if is_valid:
                        status["is_normal_dex"] = True
                        status["details"].append("标准DEX格式")
                    else:
                        status["is_encrypted"] = True
                        status["details"].append("DEX魔数Exception")
        
        # 如果没有深度analysisresult，使用简单判断
        if not dex_headers and dex_results.get("dex_count", 0) > 0:
            # 假设DEX正常，直到有证据证明Exception
            status["is_normal_dex"] = True
            status["details"].append("未深度analysis，假设为标准DEX")
        
        return status
    
    def calculate_protection_level(self, dex_results: Dict, native_results: Dict, 
                                  manifest_results: Dict, resource_results: Dict):
        """综合判断protection级别"""
        
        # 收集所有protection指标
        all_indicators = []
        all_indicators.extend(dex_results.get("protection_indicators", []))
        all_indicators.extend(native_results.get("protection_indicators", []))
        all_indicators.extend(manifest_results.get("protection_indicators", []))
        all_indicators.extend(resource_results.get("protection_indicators", []))
        
        # 按厂商分组，调整弱特征权重
        vendor_scores = {}
        weak_indicators_count = 0
        strong_indicators_count = 0
        
        for indicator in all_indicators:
            vendor = indicator.get("vendor")
            strength = indicator.get("strength", "weak")
            if vendor:
                # 调整权重：弱特征权重降低，强特征权重增加
                score = {"strong": 3, "medium": 1.5, "weak": 0.3}.get(strength, 0.3)  # 弱特征权重大幅降低
                vendor_scores[vendor] = vendor_scores.get(vendor, 0) + score
                
                if strength == "weak":
                    weak_indicators_count += 1
                elif strength == "strong":
                    strong_indicators_count += 1
        
        # analysisDEXStatus
        dex_status = self.analyze_dex_status(dex_results)
        self.log(f"📊 DEXStatusanalysis: 正常={dex_status['is_normal_dex']}, encryption={dex_status['is_encrypted']}", "DEBUG")
        
        # 计算初始confidence score
        total_score = sum(vendor_scores.values())
        max_score = len(all_indicators) * 3 if all_indicators else 0
        confidence = total_score / max_score if max_score > 0 else 0
        
        # 考虑DEX深度analysisresult
        dex_headers = dex_results.get("dex_headers", [])
        if dex_headers:
            for dex_analysis in dex_headers:
                if dex_analysis.get("status") == "success" and dex_analysis.get("is_valid_dex"):
                    # Standard DEX format，大幅降低reinforcement可能性
                    confidence = confidence * 0.3  # confidence score大幅降低
                    self.log(f"📊 标准DEX格式detected，大幅降低reinforcement置信度至 {confidence:.1%}", "DEBUG")
        

        
        # 确定protection类型 - 使用更严格的判断逻辑
        protection_type = "none"
        protection_level = "basic"
        
        if vendor_scores:
            # 选择得分最高的厂商
            protection_type = max(vendor_scores.items(), key=lambda x: x[1])[0]
            top_score = vendor_scores[protection_type]
            
            # 基于DEXStatus和特征强度进行综合判断
            if dex_status["is_normal_dex"]:
                # DEX正常，需要更强的证据才能判断为reinforcement
                if top_score >= 2.0 and strong_indicators_count >= 1:
                    protection_level = "commercial"
                elif top_score >= 1.0 and weak_indicators_count <= 2:
                    protection_level = "basic"
                else:
                    # 分数不够高，可能是误判
                    protection_type = "none"
                    protection_level = "basic"
                    confidence = max(confidence * 0.2, 0.1)  # 大幅降低confidence score
            else:
                # DEXException，更容易判断为reinforcement
                if top_score >= 3:
                    protection_level = "enterprise"
                elif top_score >= 2:
                    protection_level = "commercial"
                elif top_score >= 1:
                    protection_level = "basic"
                else:
                    protection_type = "none"
                    protection_level = "basic"
        else:
            # 没有detectedreinforcement特征
            if dex_results.get("dex_count", 0) == 1:
                # 单DEX可能是简单protection或未reinforcement
                protection_type = "unknown"
                protection_level = "basic"
            else:
                protection_type = "none"
                protection_level = "basic"
        
        # 特殊情况：如果只有弱特征且DEX正常，强制判断为无reinforcement
        if vendor_scores and dex_status["is_normal_dex"]:
            weak_indicators_only = weak_indicators_count > 0 and strong_indicators_count == 0
            if weak_indicators_only and top_score < 1.5:
                protection_type = "none"
                protection_level = "basic"
                confidence = 0.1  # 极低confidence score
                self.log(f"📊 只有弱特征且DEX正常，强制判断为无reinforcement", "DEBUG")
        
        # 特殊情况：多个DEXfile且都正常，通常不是reinforcement
        if dex_results.get("dex_count", 0) > 1 and dex_status["is_normal_dex"]:
            if protection_type != "none" and top_score < 2.0:
                protection_type = "none"
                protection_level = "basic"
                confidence = confidence * 0.5
                self.log(f"📊 多个正常DEXfile，降低reinforcement可能性", "DEBUG")
        
        self.analysis_results.update({
            "protection_type": protection_type,
            "protection_level": protection_level,
            "confidence_score": confidence,
            "detected_vendors": list(vendor_scores.keys()),
            "detailed_findings": {
                "dex": dex_results,
                "native": native_results,
                "manifest": manifest_results,
                "resource": resource_results,
                "dex_status": dex_status,
                "indicator_stats": {
                    "total": len(all_indicators),
                    "weak": weak_indicators_count,
                    "strong": strong_indicators_count
                }
            }
        })
    
    def generate_recommendations(self):
        """生成UnpackingRecommendation"""
        protection_type = self.analysis_results["protection_type"]
        protection_level = self.analysis_results["protection_level"]
        confidence = self.analysis_results["confidence_score"]
        
        recommendations = []
        
        # 1. Low confidence warning（优先显示）
        if confidence < 0.3:
            recommendations.append("⚠️  **Low confidence warning**: Detection result confidence is low (below 30%)，Possible misjudgment")
        
        # 2. 基于protection类型的Recommendation
        if protection_type == "none" and protection_level == "basic":
            recommendations.extend([
                "✅ Application可能未reinforcement或使用简单protection",
                "💡 Recommendation: 使用标准Unpacking模式 (android-armor-breaker --package <Package name>)",
                "📊 Estimated success rate: 95%以上",
                "⏱️  Estimated time: 1-2分钟"
            ])

                
        elif protection_type == "ijiami":
            if protection_level == "enterprise":
                recommendations.extend([
                    "⚠️  detected爱encryption企业版reinforcement",
                    "💡 Recommendation: 使用激进Unpacking策略",
                    "🛠️  Recommended parameters: --bypass-antidebug --dynamic-puzzle",
                    "📊 Estimated success rate: 30-50% (基于历史TestingData)",
                    "⏱️  Estimated time: 5-10分钟",
                    "🔑 关键: 可能需要Root权限进行MemoryAttack"
                ])
            else:
                recommendations.extend([
                    "✅ detected IJIAMI reinforcement (standard edition)",
                    "💡 Recommendation: Use deep search mode",
                    "🛠️  Recommended parameters: --deep-search --bypass-antidebug",
                    "📊 Estimated success rate: 70-85%",
                    "⏱️  Estimated time: 2-4 minutes"
                ])
                
        elif protection_type == "360":
            recommendations.extend([
                "✅ detected360reinforcement",
                "💡 Recommendation: Use deep search mode",
                "🛠️  Recommended parameters: --deep-search",
                "📊 Estimated success rate: 80-90%",
                "⏱️  Estimated time: 2-3分钟"
            ])
            
        elif protection_type == "baidu":
            recommendations.extend([
                "✅ detected百度reinforcement",
                "💡 Recommendation: Use deep search mode突破DEX数量限制",
                "🛠️  Recommended parameters: --deep-search",
                "📊 Estimated success rate: 85-95%",
                "⏱️  Estimated time: 2-3分钟",
                "💾 经验: 可突破26个DEX限制，获取完整53个DEX"
            ])
            
        elif protection_type == "tencent":
            recommendations.extend([
                "✅ detected腾讯reinforcement",
                "💡 Recommendation: 使用Anti-debugBypass+深度搜索",
                "🛠️  Recommended parameters: --deep-search --bypass-antidebug",
                "📊 Estimated success rate: 75-85%",
                "⏱️  Estimated time: 3-5分钟"
            ])
            
        elif protection_type == "ali":
            # 阿里reinforcement特别处理，因为容易误判
            if confidence < 0.5:
                recommendations.extend([
                    f"⚠️  detected阿里reinforcement (置信度: {confidence*100:.1f}%)",
                    "🔍 **Note**: 阿里reinforcementDetection容易误判，libEncryptorP.so等library可能是Application自有encryption",
                    "🔄 **Unpacking策略**: 如果确实有Anti-debugprotection，使用 --bypass-antidebug Parameter"
                ])
            else:
                recommendations.extend([
                    "✅ detected阿里reinforcement",
                    "💡 Recommendation: 使用自适应策略",
                    "🛠️  Recommended parameters: --bypass-antidebug --deep-search",
                    f"📊 置信度: {confidence*100:.1f}%",
                    "⏱️  Estimated time: 3-5分钟"
                ])
                
        else:
            # 其他reinforcement类型
            recommendations.extend([
                f"✅ detected {protection_type} reinforcement (protection级别: {protection_level})",
                "💡 Recommendation: 尝试自适应策略",
                "🛠️  Recommended parameters: --detect-protection (让技能自动选择最佳策略)",
                f"📊 置信度: {confidence*100:.1f}%",
                "⏱️  Estimated time: 2-5分钟"
            ])
        
        # 3. DEXfile直接提取Recommendation（如果DEX数量多且可能未reinforcement）
        dex_count = self.analysis_results.get("detailed_findings", {}).get("dex", {}).get("dex_count", 0)
        if dex_count >= 2 and confidence < 0.4:
            recommendations.append("📦 **直接提取Recommendation**: 可尝试直接从APK提取DEX: `unzip -j apk '*.dex'`")
        
        self.analysis_results["recommendations"] = recommendations
    
    def print_report(self):
        """打印analysisReport"""
        results = self.analysis_results
        
        self.log("=" * 60)
        self.log("📊 APKreinforcementanalysisReport")
        self.log("=" * 60)
        self.log(f"📦 file: {results['apk_file']}")
        self.log(f"📏 size: {results['file_size'] / (1024*1024):.1f} MB")
        self.log("")
        
        self.log("🔐 reinforcementanalysisresult:")
        self.log(f"  protection类型: {results['protection_type'].upper()}")
        self.log(f"  protection级别: {results['protection_level'].upper()}")
        self.log(f"  detected vendors: {', '.join(results['detected_vendors']) if results['detected_vendors'] else '无'}")
        self.log(f"  置信度: {results['confidence_score']*100:.1f}%")
        
        self.log("")
        
        # 详细发现
        details = results['detailed_findings']
        if details.get('dex', {}).get('dex_count', 0) > 0:
            dex_info = details['dex']
            self.log(f"📄 DEXfile: {dex_info['dex_count']} 个")
            
            # 显示DEX头analysisresult
            dex_headers = dex_info.get('dex_headers', [])
            if dex_headers:
                for dex_analysis in dex_headers[:2]:  # 只显示前2个analysisresult
                    if dex_analysis.get('status') == 'success':
                        magic = dex_analysis.get('magic', '未知')
                        is_valid = dex_analysis.get('is_valid_dex', False)
                        file_size = dex_analysis.get('file_size', 0)
                        
                        if is_valid:
                            self.log(f"  ✅ DEX头部: 标准格式 (magic: {magic}), size: {file_size:,} 字节")
                            if dex_analysis.get('analysis', {}).get('conclusion'):
                                self.log(f"    analysis: {dex_analysis['analysis']['conclusion']}")
                        else:
                            self.log(f"  ⚠️  DEX头部: Exception格式 (magic: {magic})")
                            if dex_analysis.get('analysis', {}).get('warning'):
                                self.log(f"    Warning: {dex_analysis['analysis']['warning']}")
        
        if details.get('native', {}).get('lib_count', 0) > 0:
            native_info = details['native']
            self.log(f"⚙️  原生library: {native_info['lib_count']} 个")
            
            # 显示Securitylibrary（非reinforcement特征）
            security_libs = native_info.get('security_libs', [])
            if security_libs:
                self.log("  🔒 detected security library (possibly application-owned):")
                for lib in security_libs[:3]:  # 只显示前3个
                    self.log(f"    - {os.path.basename(lib)}")
            
            # 显示reinforcement feature library
            if native_info.get('protection_indicators'):
                self.log("  🔍 detected reinforcement feature library:")
                for indicator in native_info['protection_indicators'][:5]:  # 只显示前5个
                    self.log(f"    - {indicator['vendor']}: {os.path.basename(indicator['file'])}")
        
        self.log("")
        
        # Recommendation
        self.log("🎯 UnpackingRecommendation:")
        for rec in results['recommendations']:
            if rec.startswith("✅"):
                self.log(f"  {rec}")
            elif rec.startswith("⚠️"):
                self.log(f"  {rec}")
            elif rec.startswith("💡"):
                self.log(f"  {rec}")
            else:
                self.log(f"    {rec}")
        
        self.log("=" * 60)

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='APKreinforcement类型analysis器')
    parser.add_argument('--apk', '-a', required=True, help='APKfilePath')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细Output')
    
    args = parser.parse_args()
    
    analyzer = ApkprotectionAnalyzer(verbose=args.verbose)
    results = analyzer.analyze_apk(args.apk)
    analyzer.print_report()
    
    # 保存result到file
    output_file = os.path.splitext(args.apk)[0] + '_protection_analysis.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n📁 Detailed result saved to: {output_file}")

if __name__ == '__main__':
    main()