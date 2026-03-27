#!/usr/bin/env python3
"""
APK Protection Type Analyzer
Directly analyzes APK files to detect used protection types and protection levels
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

class ApkProtectionAnalyzer:
    """APK Protection Analyzer"""
    
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
        
        # Protection feature library        self.protection_patterns = {
            # iJiami            "ijiami": [
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
            # 360 Protection            "360": [
                (r".*libjiagu.*\.so$", "strong"),           # libjiagu library in any directory                (r"assets/libjiagu.*\.so$", "strong"),      # assetsdirectory下的jiagulibrary（important）                (r"lib360\.so$", "strong"),
                (r"jiagu\.dex$", "strong"),
                (r"protect\.jar$", "medium"),
                (r".*360.*\.so$", "medium"),                # 任何360.sofile                (r"assets/.*360.*", "weak"),                # assets中的360file                (r"assets/.*jiagu.*", "strong"),            # assets中的jiagufile                (r".*jiagu.*", "weak"),                     # file名包含jiagu            ],
            # Baidu Protection            "baidu": [
                (r"baiduprotect.*\.dex$", "strong"),
                (r"baiduprotect.*\.i\.dex$", "strong"),  # 新Baidu ProtectionintermediateDEXfile                (r"libbaiduprotect.*\.so$", "strong"),
                (r"libbdprotect.*\.so$", "strong"),
                (r"protect\.jar$", "medium"),
                (r"baiduprotect.*\.jar$", "medium"),  # Baidu ProtectionJARfile            ],
            # Tencent Protection            "tencent": [
                (r"libshell.*\.so$", "strong"),
                (r"libtprotect.*\.so$", "strong"),
                (r"libstub\.so$", "strong"),
                (r"libAntiCheat\.so$", "strong"),  # Tencent Game Security (ACE) anti-cheat core library                (r"tps\.jar$", "medium"),
                (r"libmain\.so$", "weak"),  # Note: Could also be a normal library            ],
            # Ali Protection            "ali": [
                (r"libmobisec.*\.so$", "strong"),
                (r"aliprotect\.dex$", "strong"),
                (r"aliprotect\.jar$", "medium"),
            ],
            # Bangbang Protection            "bangcle": [
                (r"libbangcle.*\.so$", "strong"),
                (r"libbc.*\.so$", "strong"),
                (r"bangcle\.jar$", "medium"),
                # Bangbang Protection enterprise edition features                (r"libdexjni\.so$", "strong"),
                (r"libDexHelper\.so$", "strong"),
                (r"libdexjni.*\.so$", "strong"),  # variant                (r"libdexhelper.*\.so$", "strong"),  # Variant            ],
            # Naga Protection            "naga": [
                (r"libnaga.*\.so$", "strong"),
                (r"libng.*\.so$", "strong"),
            ],
            # Dingxiang Protection            "dingxiang": [
                (r"libdxp.*\.so$", "strong"),
                (r"libdx\.so$", "strong"),
            ],
            # NetEase Yidun            "netease": [
                (r"libnesec\.so$", "strong"),
                (r"libneso\.so$", "strong"),
            ],
            # 几维安全（KiwiVM/奇安信/奇虎360）            "kiwivm": [
                (r"libKwProtectSDK\.so$", "strong"),
                (r"libkiwi.*\.so$", "strong"),           # libkiwi_dumper.so, libkiwicrash.so
                (r"libkwsdataenc\.so$", "strong"),
                (r"libkadp\.so$", "strong"),
                (r"com\.kiwivm\.security\.StubApplication", "strong"),  # Application类            ],
        }
        
        # 白名单（不视为Protection）        self.sdk_whitelist = [
            r".*BaiduSpeechSDK.*",
            r".*baidumap.*",
            r".*AMapSDK.*",
            r".*bugly.*",
            r".*qq.*",
            r".*wechat.*",
            r".*alipay.*",
            r".*alivc.*",       # Alibaba Cloud Video SDK            r".*aliyun.*",      # Alibaba Cloud General SDK            r".*alibaba.*",     # Alibaba SDK            r".*umeng.*",
            r".*tencent.*\.so$",  # Note: Excluding Tencent SDK, but not libtprotect.so            r"^libc\.so$",
            r"^libz\.so$",
            r"^liblog\.so$",
            r"^libm\.so$",
            r"^libdl\.so$",
            # 常见application自有加密/安全库（非Protection特征）            r".*Encryptor.*",
            r".*encrypt.*",
            r".*crypto.*",
            r".*security.*",
            r".*secure.*",
            r".*safe.*",
            # r".*protect.*",  # 注意：可能是Protection，但排除常见application自有保护库 - Temporarily commented to avoid missing Baidu Protection reports            r".*guard.*",
            r".*shield.*",
            r".*defense.*",
            r".*armor.*",
            r".*obfuscate.*",
            r".*antidebug.*",
            r".*anti.*debug.*",
            # 常见SDK库            r".*volc.*",
            r".*tx.*",
            r".*apminsight.*",
            r".*mmkv.*",
            r".*liteav.*",
            r".*rive.*",
            r".*CtaApi.*",
        ]
    
    def log(self, message: str, level: str = "INFO"):
        """Log message"""
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
        """分析APKfileprotection type"""
        if not os.path.exists(apk_path):
            self.log(f"APKfile不存在: {apk_path}", "ERROR")
            return self.analysis_results
        
        self.apk_path = apk_path
        self.analysis_results["apk_file"] = os.path.basename(apk_path)
        self.analysis_results["file_size"] = os.path.getsize(apk_path)
        
        self.log("=" * 60)
        self.log("🔍 APKprotection type分析")
        self.log(f"目标file: {os.path.basename(apk_path)}")
        self.log(f"file大小: {self.analysis_results['file_size'] / (1024*1024):.1f} MB")
        self.log("=" * 60)
        
        try:
            with zipfile.ZipFile(apk_path, 'r') as apk_zip:
                # 1. Analyze DEX files                dex_analysis = self.analyze_dex_files(apk_zip)
                
                # 2. Analyze native libraries                native_lib_analysis = self.analyze_native_libs(apk_zip)
                
                # 3. Analyze AndroidManifest.xml                manifest_analysis = self.analyze_manifest(apk_zip)
                
                # 4. Analyze resource files                resource_analysis = self.analyze_resources(apk_zip)
                
                # 5. Comprehensive judgment                self.calculate_protection_level(
                    dex_analysis, 
                    native_lib_analysis, 
                    manifest_analysis, 
                    resource_analysis
                )
                
                # 7. Generate suggestions                self.generate_recommendations()
                
        except Exception as e:
            self.log(f"分析APKFailed: {e}", "ERROR")
        
        return self.analysis_results
    
    def analyze_dex_files(self, apk_zip: zipfile.ZipFile) -> Dict:
        """分析DEXfilefeatures"""
        self.log("分析DEXfile...")
        
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
            self.log("❌ Not foundDEXfile", "WARNING")
            results["unusual_patterns"].append("no_dex_files")
        elif len(dex_files) == 1:
            self.log(f"✅ 发现 {len(dex_files)} 个DEXfile: {dex_files[0]}")
            # 单DEX可能是Protection特征            if "classes.dex" in dex_files:
                # 深度Analyze DEX files头                dex_analysis = self.deep_analyze_dex(apk_zip, dex_files[0])
                results["dex_headers"].append(dex_analysis)
                results["dex_size_analysis"][dex_files[0]] = dex_analysis
        else:
            self.log(f"✅ 发现 {len(dex_files)} 个DEXfile")
            # Analyze 第一个DEXfile作为样本            if dex_files and "classes.dex" in dex_files:
                dex_analysis = self.deep_analyze_dex(apk_zip, "classes.dex")
                results["dex_headers"].append(dex_analysis)
                results["dex_size_analysis"]["classes.dex"] = dex_analysis
        
        # Check Protection特征DEX        for dex_file in dex_files:
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
        """深度分析DEXfile头"""
        try:
            with apk_zip.open(dex_file) as f:
                # 读取DEXfileheader（前112bytes包含关键information）                data = f.read(112)
                if len(data) < 8:
                    return {"status": "error", "reason": "file太小"}
                
                # Check DEX魔数                magic = data[0:8]
                is_valid_dex = magic in [b'dex\n035\x00', b'dex\n036\x00', b'dex\n037\x00', b'dex\n038\x00', b'dex\n039\x00']
                
                # Check file大小（从偏移0x20开始，4bytes小端）                if len(data) >= 0x24:
                    file_size = struct.unpack('<I', data[0x20:0x24])[0]
                else:
                    file_size = 0
                
                # Check 校验和（偏移0x08，4bytes小端）                if len(data) >= 0x0C:
                    checksum = struct.unpack('<I', data[0x08:0x0C])[0]
                else:
                    checksum = 0
                
                # Check 签名（偏移0x0C，20bytesSHA-1）                if len(data) >= 0x20:
                    signature = data[0x0C:0x20].hex()
                else:
                    signature = ""
                
                # Analyze 结果                result = {
                    "status": "success",
                    "magic": magic.hex(),
                    "is_valid_dex": is_valid_dex,
                    "file_size": file_size,
                    "checksum": checksum,
                    "signature": signature,
                    "analysis": {}
                }
                
                # 判断是否加密或混淆                if not is_valid_dex:
                    result["analysis"]["warning"] = "DEX魔数异常，可能被加密或修改"
                    # 尝试Check 是否为常见的Protection特征                    if magic[0:4] == b'\x00\x00\x00\x00':
                        result["analysis"]["suspicion"] = "可能为零填充加密"
                else:
                    result["analysis"]["conclusion"] = "标准DEX格式，可能未加密"
                    
                    # Check 是否有常见的Protection特征                    # 读取更多数据Check 是否有明显的加密模式                    f.seek(0)
                    sample_data = f.read(1024)
                    zero_count = sample_data.count(b'\x00')
                    if zero_count > 512:  # More than 50% zero                        result["analysis"]["suspicion"] = "高零值比例，可能为简单加密或填充"
                
                return result
                
        except Exception as e:
            return {"status": "error", "reason": str(e)}
    
    def analyze_native_libs(self, apk_zip: zipfile.ZipFile) -> Dict:
        """分析原生libraryfeatures"""
        self.log("分析原生libraryfile...")
        
        # Check 所有.sofile，包括assets/目录下的Protection库        lib_files = [f for f in apk_zip.namelist() if f.endswith('.so')]
        results = {
            "lib_count": len(lib_files),
            "lib_files": lib_files,
            "protection_indicators": [],
            "security_libs": [],
            "sdk_libs": []
        }
        
        if len(lib_files) == 0:
            self.log("❌ Not found原生libraryfile", "WARNING")
        else:
            self.log(f"✅ 发现 {len(lib_files)} 个原生libraryfile")
        
        # Check Protection feature library        protection_found = False
        for lib_file in lib_files:
            lib_name = os.path.basename(lib_file)
            
            # Check 是否是白名单SDK            if self.is_whitelisted(lib_file):
                results["sdk_libs"].append(lib_file)
                continue
            
            # Check Protection特征            vendor_found = False
            for vendor, patterns in self.protection_patterns.items():
                for pattern, strength in patterns:
                    if re.search(pattern, lib_file, re.IGNORECASE):
                        if not vendor_found:  # Avoid duplicate addition                            results["protection_indicators"].append({
                                "type": "native",
                                "vendor": vendor,
                                "file": lib_file,
                                "strength": strength,
                                "pattern": pattern
                            })
                            vendor_found = True
                            protection_found = True
            
            # 如果没有匹配Protection特征，Check 是否是其他安全库            if not vendor_found:
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
            self.log(f"⚠️  发现Protectionfeatureslibrary", "WARNING")
        else:
            self.log("✅ 未发现明显的Protectionfeatureslibrary", "SUCCESS")
        
        return results
    
    def analyze_manifest(self, apk_zip: zipfile.ZipFile) -> Dict:
        """Analyze AndroidManifest.xml"""
        self.log("Analyze AndroidManifest.xml...")
        
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
                    
                    # 简单文本Check （实际application中应使用AXML解析器）                    try:
                        text = content.decode('utf-8', errors='ignore')
                        
                        # Check Debug属性                        if 'android:debuggable="true"' in text:
                            results["debuggable"] = True
                            self.log("⚠️  application可Debug (debuggable=true)", "WARNING")
                        
                        # Check 备份属性                        if 'android:allowBackup="false"' in text:
                            results["backup_allowed"] = False
                            self.log("✅ 备份已禁用 (安全配置)", "INFO")
                        
                        # Check Protection相关特征                        if 'com.ijiami' in text:
                            results["protection_indicators"].append({
                                "type": "manifest",
                                "vendor": "ijiami",
                                "indicator": "包名包含ijiami"
                            })
                        
                    except:
                        pass
            else:
                self.log("❌ Not foundAndroidManifest.xml", "WARNING")
                
        except Exception as e:
            self.log(f"分析ManifestFailed: {e}", "DEBUG")
        
        return results
    
    def analyze_resources(self, apk_zip: zipfile.ZipFile) -> Dict:
        """分析资源file"""
        self.log("分析资源file...")
        
        results = {
            "resource_count": 0,
            "protection_indicators": [],
            "unusual_files": []
        }
        
        file_list = apk_zip.namelist()
        results["resource_count"] = len(file_list)
        
        # Protection资源file特征模式        resource_protection_patterns = {
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
                r"assets/libwbsafeedit.*",  # 腾讯Web安全编辑组件            ],
            "ali": [
                r"assets/aliprotect.*",
                r"assets/alisec.*",
            ],
            "bangcle": [
                r"assets/meta-data/.*",  # Bangbang Protectionenterprise edition签名filedirectory                r"assets/.*bangcle.*",
                r"assets/.*bangele.*",
                r"assets/.*libdexjni.*",
                r"assets/.*libDexHelper.*",
            ],
            # NetEase Yidun资源file特征            "netease": [
                r"assets/netease.*",
                r"assets/yidun.*",
                r"assets/nd.*",
                r"assets/libnesec.*",
                r"assets/libneso.*",
            ]
        }
        
        for file_name in file_list:
            # 跳过白名单file            if self.is_whitelisted(file_name):
                continue
                
            # Check 是否是明显的Protection资源file            for vendor, patterns in resource_protection_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, file_name, re.IGNORECASE):
                        results["protection_indicators"].append({
                            "type": "resource",
                            "vendor": vendor,
                            "file": file_name,
                            "pattern": pattern
                        })
                        break  # Break inner loop when a match is found        
        return results
    
    def is_whitelisted(self, file_name: str) -> bool:
        """检查是否在白名单中"""
        for pattern in self.sdk_whitelist:
            if re.search(pattern, file_name, re.IGNORECASE):
                return True
        return False
    
    def analyze_dex_status(self, dex_results: Dict) -> Dict:
        """分析DEXfile状态"""
        status = {
            "is_normal_dex": False,
            "is_encrypted": False,
            "is_obfuscated": False,
            "details": []
        }
        
        # Check DEX头Analyze 结果        dex_headers = dex_results.get("dex_headers", [])
        if dex_headers:
            for header_info in dex_headers:
                if header_info.get("status") == "success":
                    is_valid = header_info.get("is_valid_dex", False)
                    if is_valid:
                        status["is_normal_dex"] = True
                        status["details"].append("标准DEX格式")
                    else:
                        status["is_encrypted"] = True
                        status["details"].append("DEX魔数异常")
        
        # 如果没有深度Analyze 结果，使用简单判断        if not dex_headers and dex_results.get("dex_count", 0) > 0:
            # 假设DEX正常，直到有证据证明异常            status["is_normal_dex"] = True
            status["details"].append("未深度分析，假设为标准DEX")
        
        return status
    
    def calculate_protection_level(self, dex_results: Dict, native_results: Dict, 
                                  manifest_results: Dict, resource_results: Dict):
        """Comprehensive judgmentprotection level"""
        
        # 收集所有保护指标        all_indicators = []
        all_indicators.extend(dex_results.get("protection_indicators", []))
        all_indicators.extend(native_results.get("protection_indicators", []))
        all_indicators.extend(manifest_results.get("protection_indicators", []))
        all_indicators.extend(resource_results.get("protection_indicators", []))
        
        # 按厂商分组，调整弱特征权重        vendor_scores = {}
        weak_indicators_count = 0
        strong_indicators_count = 0
        
        for indicator in all_indicators:
            vendor = indicator.get("vendor")
            strength = indicator.get("strength", "weak")
            if vendor:
                # 调整权重：弱特征权重降低，强特征权重增加                score = {"strong": 3, "medium": 1.5, "weak": 0.3}.get(strength, 0.3)  # 弱特征权重大幅降低                vendor_scores[vendor] = vendor_scores.get(vendor, 0) + score
                
                if strength == "weak":
                    weak_indicators_count += 1
                elif strength == "strong":
                    strong_indicators_count += 1
        
        # Analyze DEX状态        dex_status = self.analyze_dex_status(dex_results)
        self.log(f"📊 DEX状态分析: 正常={dex_status['is_normal_dex']}, 加密={dex_status['is_encrypted']}", "DEBUG")
        
        # 计算初始confidence        total_score = sum(vendor_scores.values())
        max_score = len(all_indicators) * 3 if all_indicators else 0
        confidence = total_score / max_score if max_score > 0 else 0
        
        # 考虑DEX深度Analyze 结果        dex_headers = dex_results.get("dex_headers", [])
        if dex_headers:
            for dex_analysis in dex_headers:
                if dex_analysis.get("status") == "success" and dex_analysis.get("is_valid_dex"):
                    # 标准DEX格式，大幅降低Protection可能性                    confidence = confidence * 0.3  # Confidence significantly reduced                    self.log(f"📊 标准DEX格式检测到，大幅降低Protectionconfidence至 {confidence:.1%}", "DEBUG")
        

        
        # 确定保护类型 - 使用更严格的判断逻辑        protection_type = "none"
        protection_level = "basic"
        
        if vendor_scores:
            # 选择得分最高的厂商            protection_type = max(vendor_scores.items(), key=lambda x: x[1])[0]
            top_score = vendor_scores[protection_type]
            
            # 基于DEX状态和特征强度进行Comprehensive judgment            if dex_status["is_normal_dex"]:
                # DEX normal, need stronger evidence to judge as protected                if top_score >= 2.0 and strong_indicators_count >= 1:
                    protection_level = "commercial"
                elif top_score >= 1.0 and weak_indicators_count <= 2:
                    protection_level = "basic"
                else:
                    # 分数不够高，可能是误判                    protection_type = "none"
                    protection_level = "basic"
                    confidence = max(confidence * 0.2, 0.1)  # Significantly reduce confidence            else:
                # DEX abnormal, easier to judge as protected                if top_score >= 3:
                    protection_level = "enterprise"
                elif top_score >= 2:
                    protection_level = "commercial"
                elif top_score >= 1:
                    protection_level = "basic"
                else:
                    protection_type = "none"
                    protection_level = "basic"
        else:
            # 没有检测到Protection特征            if dex_results.get("dex_count", 0) == 1:
                # 单DEX可能是简单保护或未Protection                protection_type = "unknown"
                protection_level = "basic"
            else:
                protection_type = "none"
                protection_level = "basic"
        
        # 特殊情况：如果只有弱特征且DEX正常，强制判断为无Protection        if vendor_scores and dex_status["is_normal_dex"]:
            weak_indicators_only = weak_indicators_count > 0 and strong_indicators_count == 0
            if weak_indicators_only and top_score < 1.5:
                protection_type = "none"
                protection_level = "basic"
                confidence = 0.1  # Extremely low confidence                self.log(f"📊 只有弱features且DEX正常，强制判断为无Protection", "DEBUG")
        
        # 特殊情况：多个DEXfile且都正常，通常不是Protection        if dex_results.get("dex_count", 0) > 1 and dex_status["is_normal_dex"]:
            if protection_type != "none" and top_score < 2.0:
                protection_type = "none"
                protection_level = "basic"
                confidence = confidence * 0.5
                self.log(f"📊 多个正常DEXfile，降低Protection可能性", "DEBUG")
        
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
        """生成脱壳建议"""
        protection_type = self.analysis_results["protection_type"]
        protection_level = self.analysis_results["protection_level"]
        confidence = self.analysis_results["confidence_score"]
        
        recommendations = []
        
        # 1. Low confidence warning (display first)        if confidence < 0.3:
            recommendations.append("⚠️  **Low confidence warning**: 检测结果confidence较低 (低于30%)，可能存在误判")
        
        # 2. Suggestions based on protection type        if protection_type == "none" and protection_level == "basic":
            recommendations.extend([
                "✅ application可能未Protection或使用简单保护",
                "💡 建议: 使用标准脱壳模式 (android-armor-breaker --package <包名>)",
                "📊 预估Success率: 95%以上",
                "⏱️  预估时间: 1-2分钟"
            ])

                
        elif protection_type == "ijiami":
            if protection_level == "enterprise":
                recommendations.extend([
                    "⚠️  检测到iJiamienterprise editionProtection",
                    "💡 建议: 使用激进脱壳策略",
                    "🛠️  推荐参数: --bypass-antidebug --dynamic-puzzle",
                    "📊 预估Success率: 30-50% (基于历史Test数据)",
                    "⏱️  预估时间: 5-10分钟",
                    "🔑 关键: 可能需要Root权限进行内存攻击"
                ])
            else:
                recommendations.extend([
                    "✅ 检测到iJiamiProtection (标准版)",
                    "💡 建议: 使用深度搜索模式",
                    "🛠️  推荐参数: --deep-search --bypass-antidebug",
                    "📊 预估Success率: 70-85%",
                    "⏱️  预估时间: 2-4分钟"
                ])
                
        elif protection_type == "360":
            recommendations.extend([
                "✅ 检测到360 Protection",
                "💡 建议: 使用深度搜索模式",
                "🛠️  推荐参数: --deep-search",
                "📊 预估Success率: 80-90%",
                "⏱️  预估时间: 2-3分钟"
            ])
            
        elif protection_type == "baidu":
            recommendations.extend([
                "✅ 检测到Baidu Protection",
                "💡 建议: 使用深度搜索模式突破DEX数量限制",
                "🛠️  推荐参数: --deep-search",
                "📊 预估Success率: 85-95%",
                "⏱️  预估时间: 2-3分钟",
                "💾 经验: 可突破26个DEX限制，获取完整53个DEX"
            ])
            
        elif protection_type == "tencent":
            recommendations.extend([
                "✅ 检测到Tencent Protection",
                "💡 建议: 使用反Debug绕过+深度搜索",
                "🛠️  推荐参数: --deep-search --bypass-antidebug",
                "📊 预估Success率: 75-85%",
                "⏱️  预估时间: 3-5分钟"
            ])
            
        elif protection_type == "ali":
            # Ali Protection特别处理，因为容易误判            if confidence < 0.5:
                recommendations.extend([
                    f"⚠️  检测到Ali Protection (confidence: {confidence*100:.1f}%)",
                    "🔍 **注意**: Ali Protection检测容易误判，libEncryptorP.so等library可能是application自有加密",
                    "🔄 **脱壳策略**: 如果确实有反Debug保护，使用 --bypass-antidebug 参数"
                ])
            else:
                recommendations.extend([
                    "✅ 检测到Ali Protection",
                    "💡 建议: 使用自适应策略",
                    "🛠️  推荐参数: --bypass-antidebug --deep-search",
                    f"📊 confidence: {confidence*100:.1f}%",
                    "⏱️  预估时间: 3-5分钟"
                ])
                
        else:
            # 其他protection type            recommendations.extend([
                f"✅ 检测到 {protection_type} Protection (protection level: {protection_level})",
                "💡 建议: 尝试自适应策略",
                "🛠️  推荐参数: --detect-protection (让技能自动选择最佳策略)",
                f"📊 confidence: {confidence*100:.1f}%",
                "⏱️  预估时间: 2-5分钟"
            ])
        
        # 3. DEX file direct extraction suggestion (if many DEX files and possibly not protected)        dex_count = self.analysis_results.get("detailed_findings", {}).get("dex", {}).get("dex_count", 0)
        if dex_count >= 2 and confidence < 0.4:
            recommendations.append("📦 **直接提取建议**: 可尝试直接从APK提取DEX: `unzip -j apk '*.dex'`")
        
        self.analysis_results["recommendations"] = recommendations
    
    def print_report(self):
        """打印分析report"""
        results = self.analysis_results
        
        self.log("=" * 60)
        self.log("📊 APKProtection分析report")
        self.log("=" * 60)
        self.log(f"📦 file: {results['apk_file']}")
        self.log(f"📏 大小: {results['file_size'] / (1024*1024):.1f} MB")
        self.log("")
        
        self.log("🔐 Protection分析结果:")
        self.log(f"  保护类型: {results['protection_type'].upper()}")
        self.log(f"  protection level: {results['protection_level'].upper()}")
        self.log(f"  检测到的厂商: {', '.join(results['detected_vendors']) if results['detected_vendors'] else '无'}")
        self.log(f"  confidence: {results['confidence_score']*100:.1f}%")
        
        self.log("")
        
        # 详细发现        details = results['detailed_findings']
        if details.get('dex', {}).get('dex_count', 0) > 0:
            dex_info = details['dex']
            self.log(f"📄 DEXfile: {dex_info['dex_count']} 个")
            
            # 显示DEX头Analyze 结果            dex_headers = dex_info.get('dex_headers', [])
            if dex_headers:
                for dex_analysis in dex_headers[:2]:  # Only show first 2 analysis results                    if dex_analysis.get('status') == 'success':
                        magic = dex_analysis.get('magic', 'Unknown')
                        is_valid = dex_analysis.get('is_valid_dex', False)
                        file_size = dex_analysis.get('file_size', 0)
                        
                        if is_valid:
                            self.log(f"  ✅ DEX头部: 标准格式 (magic: {magic}), 大小: {file_size:,} 字节")
                            if dex_analysis.get('analysis', {}).get('conclusion'):
                                self.log(f"    分析: {dex_analysis['analysis']['conclusion']}")
                        else:
                            self.log(f"  ⚠️  DEX头部: 异常格式 (magic: {magic})")
                            if dex_analysis.get('analysis', {}).get('warning'):
                                self.log(f"    Warning: {dex_analysis['analysis']['warning']}")
        
        if details.get('native', {}).get('lib_count', 0) > 0:
            native_info = details['native']
            self.log(f"⚙️  原生library: {native_info['lib_count']} 个")
            
            # 显示安全库（非Protection特征）            security_libs = native_info.get('security_libs', [])
            if security_libs:
                self.log("  🔒 检测到的安全library (可能为application自有):")
                for lib in security_libs[:3]:  # Only show first 3                    self.log(f"    - {os.path.basename(lib)}")
            
            # 显示Protection feature library            if native_info.get('protection_indicators'):
                self.log("  🔍 检测到的Protectionfeatureslibrary:")
                for indicator in native_info['protection_indicators'][:5]:  # Only show first 5                    self.log(f"    - {indicator['vendor']}: {os.path.basename(indicator['file'])}")
        
        self.log("")
        
        # 建议        self.log("🎯 脱壳建议:")
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
    
    parser = argparse.ArgumentParser(description='APKprotection type分析器')
    parser.add_argument('--apk', '-a', required=True, help='APKfilePath')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    analyzer = ApkProtectionAnalyzer(verbose=args.verbose)
    results = analyzer.analyze_apk(args.apk)
    analyzer.print_report()
    
    # Save results到file    output_file = os.path.splitext(args.apk)[0] + '_protection_analysis.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n📁 详细结果已保存到: {output_file}")

if __name__ == '__main__':
    main()