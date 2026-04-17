# Android Armor Breaker v2.2.0 - Android APK Unpacker & Reinforcement Breaker

> **Internationalized Version (65% Complete)** - Supports English and Chinese languages with internationalization of core functionality. Most scripts support bilingual output, some auxiliary scripts still have hardcoded English.

Android应用护甲破坏者 - 基于OpenClaw平台的Frida脱壳技术，针对从商业级到企业级的Android应用保护方案，提供**APK加固分析**与**DEX智能提取**的完整解决方案。

**关键词**: Android APK脱壳, 加固破解, Frida脱壳, DEX提取, 反调试绕过, 内存提取, 逆向工程, 安全研究, Android逆向, 移动安全

## 🎯 核心特性

### 🔧 功能特性
- ✅ **APK加固分析** - 静态分析APK文件，识别加固厂商和保护级别
- ✅ **环境检查** - 自动检查Frida环境、设备连接、应用安装状态、Root权限
- ✅ **智能脱壳** - 根据保护级别自动选择最佳脱壳策略
- ✅ **实时监控界面** - 追踪Dex文件提取过程，实时显示进度
- ✅ **DEX完整性验证** - 验证生成的DEX文件完整性和有效性
- ✅ **增强功能** - 应用预热机制、多次脱壳尝试、动态加载检测、完整性深度验证

### 🌐 国际化特性 (v2.2.0 完善)
- ✅ **多语言支持** - 支持英语和中文环境（约65%完成度）
- ✅ **国际化日志** - 统一的国际化日志系统
- ✅ **参数支持** - `--language en-US/zh-CN` 参数
- ✅ **向后兼容** - 默认英语，不影响现有功能
- 🔄 **核心功能双语** - 主要脚本支持双语输出
- ⚠️ **部分硬编码** - 一些辅助脚本仍有英文输出

**国际化状态**: 框架完整，核心功能支持双语，正在逐步完善。

## 支持的加固方案

- ✅ 360加固（已验证：示例应用1，85个DEX）
- ✅ 梆梆企业版（已验证：示例应用2，115个DEX）
- ✅ 梆梆企业版轻量级（已验证：示例应用3，59个DEX）
- ⚠️ 新百度加固（理论支持，待验证）
- ❌ 混合加固（360+腾讯等，当前技术限制）

## 🚀 快速开始

### 安装依赖
```bash
pip install frida-tools
sudo apt-get install adb
```

### 基本使用
```bash
# 分析APK加固类型 (英语环境)
android-armor-breaker analyze --apk app.apk --verbose --language en-US

# 分析APK加固类型 (中文环境)
android-armor-breaker analyze --apk app.apk --verbose --language zh-CN

# 执行脱壳 (智能策略选择)
android-armor-breaker --package com.example.app --deep-search --verbose

# 针对强反调试应用
android-armor-breaker --package com.example.app --bypass-antidebug --verbose
```

### 🌐 国际化使用示例
```bash
# 英语环境 - 完整流程
android-armor-breaker analyze --apk app.apk --language en-US
android-armor-breaker --package com.example.app --language en-US --verbose

# 中文环境 - 完整流程
android-armor-breaker analyze --apk app.apk --language zh-CN
android-armor-breaker --package com.example.app --language zh-CN --verbose

# 默认环境 (英语)
android-armor-breaker --package com.example.app
```

## 测试结果

基于2026年3月18-19日实际测试：

| 应用 | 加固类型 | DEX数量 | 结果 |
|------|----------|---------|------|
| 示例应用1 | 360加固 | 85个 | ✅ 成功 |
| 示例应用2 | 梆梆企业版 | 115个 | ✅ 成功 |
| 示例应用3 | 梆梆企业版 | 59个 | ✅ 成功 |
| 示例应用4 | 360+腾讯混合 | 0个 | ❌ 失败 |

**成功率**: 75% (3/4应用成功)
**总DEX文件**: 259个
**总文件大小**: 约1.6GB

## 技术突破

1. **内存权限修改** - 突破`PROT_NONE`内存保护，解决访问违规问题
2. **Frida特征隐藏** - 重命名文件、非标准端口、函数名混淆，避免脚本销毁
3. **反调试绕过** - 分阶段注入，突破企业级反调试保护
4. **深度搜索模式** - 从1个静态DEX发现100+个运行时DEX
5. **完整性深度验证** - CRC32、SHA-1、MD5多维度校验

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 作者

Android Armor Breaker Team

## 支持

如有问题或建议，请通过OpenClaw社区反馈。