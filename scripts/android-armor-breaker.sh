#!/usr/bin/env bash
# Android Armor Breaker skill wrapper script
# APK protection analysis and intelligent unpacking solution：Statically identify mainstream protection vendors, dynamically extract DEX files
# Supports deep search and anti-debug bypass, provides complete DEX integrity verification
# Provides simple command-line interface

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_SCRIPT="${SCRIPT_DIR}/enhanced_dexdump_runner.py"
APK_ANALYZER="${SCRIPT_DIR}/apk_protection_analyzer.py"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    log_error "Cannot find Python execution script: $PYTHON_SCRIPT"
    exit 1
fi

# Check if Python3 is available
if ! command -v python3 &> /dev/null; then
    log_error "Python3 not found, please install Python3 first"
    exit 1
fi

# Display help information
show_help() {
    cat << EOF
Android Armor Breaker - APK protection analysis and intelligent unpacking solution

Usage:
  android-armor-breaker [analyze|dump] [Options]

Subcommands:
  analyze              Analyze APK file protection type
  dump                 Unpack Android application (DefaultSubcommands)

Analyze APK (analyze):
  android-armor-breaker analyze --apk <apkfile_path> [--verbose]

  -a, --apk <file_path>   APK file path (Required)
  -v, --verbose        Verbose output mode

Unpack application (dump):
  android-armor-breaker dump [Options] <package_name>
  or
  android-armor-breaker [Options] <package_name> (Shorthand form)

  -p, --package <package_name>    Android application package name (Required)
  -o, --output <directory>     Output directory (Default: ./dex_output)
  -d, --deep-search      Deep search mode（For strong protections like new Baidu protection）
  -b, --bypass-antidebug Enable anti-debug bypass（For strong anti-debugging protection）
  -v, --verbose          Verbose output mode

Examples:
  # Analyze APK protection type
  android-armor-breaker analyze --apk ./app.apk --verbose

  # Unpack application (full form)
  android-armor-breaker dump --package com.example.app --deep-search

  # Unpack application (shorthand form - backward compatible)
  android-armor-breaker --package com.example.app --output ./output/
  android-armor-breaker -p com.example.app -o ./dex_output/ -v

Skill features:
  1. 🔍 APK protection analysis (analyzeSubcommands)
  2. ⚡ Intelligent unpacking strategy (Frida-based deep search and anti-debug bypass)
  3. 🛡️ Anti-debug bypass (--bypass-antidebug)
  4. 📊 DEX integrity verification
  5. 📄 Generate detailed execution report

Recommended workflow:
  1. First analyze APK: android-armor-breaker analyze --apk app.apk
  2. Select unpacking parameters based on analysis results
  3. Execute unpacking: android-armor-breaker --package <package_name> [parameters]
EOF
}

show_analyze_help() {
    cat << EOF
APK protection analysistool

Usage:
  android-armor-breaker analyze --apk <apkfile_path> [Options]

Options:
  -a, --apk <file_path>   APK file path (Required)
  -v, --verbose        Verbose output mode
  -h, --help           Display this help information

Examples:
  android-armor-breaker analyze --apk ./app.apk
  android-armor-breaker analyze --apk /path/to/app.apk --verbose

Output:
  - Console displays protection analysis report
  - Generate JSON format detailed report: <apkfilename>_protection_analysis.json
EOF
}

show_dump_help() {
    cat << EOF
Android application unpacking tool

Usage:
  android-armor-breaker dump [Options] <Package name or APK file>
  or
  android-armor-breaker [Options] <Package name or APK file> (Shorthand form)

Options:
  -p, --package <package_name>    Android application package name (Mutually exclusive with --apk)
  -a, --apk <APKfile>     APK file path (Automatically analyze protection and extract package name)
  -o, --output <directory>     Output directory (Default: ./dex_output)
  -d, --deep-search      Deep search mode（For strong protections like new Baidu protection）
  -b, --bypass-antidebug Enable anti-debug bypass（For strong anti-debugging protection）
  -v, --verbose          Verbose output mode
  -h, --help             Display this help information

Description:
  - If --apk parameter is specified, automatically analyzes APK protection situation：
      * If not protected: directly extract static DEX files
      * If protected: execute dynamic unpacking (requires application installed)
  - If --package parameter is specified, directly execute dynamic unpacking

Examples:
  android-armor-breaker dump --apk ./app.apk --output ./app_dex/
  android-armor-breaker --apk /path/to/app.apk -v
  android-armor-breaker dump --package com.example.app
  android-armor-breaker --package com.example.app --output ./dex_output/
  android-armor-breaker -p com.example.app -o ./dump/ -v
  android-armor-breaker --package cn.ninebot.ninebot --bypass-antidebug
EOF
}

# Check if APK analysis tool exists
check_apk_analyzer() {
    if [ ! -f "$APK_ANALYZER" ]; then
        log_error "Cannot find APK analysis tool: $APK_ANALYZER"
        log_info "Please ensure apk_protection_analyzer.py is in the scripts directory"
        exit 1
    fi
}

# APK analysis function
analyze_apk() {
    local APK_PATH=""
    local VERBOSE=false
    
    # Analyze the parameters of analyzeSubcommands
    shift  # Remove "analyze"
    while [[ $# -gt 0 ]]; do
        case $1 in
            -a|--apk)
                APK_PATH="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_analyze_help
                exit 0
                ;;
            *)
                log_error "Unknown parameter: $1"
                show_analyze_help
                exit 1
                ;;
        esac
    done
    
    # Verify parameters
    if [ -z "$APK_PATH" ]; then
        log_error "Please specify the APK file path"
        show_analyze_help
        exit 1
    fi
    
    if [ ! -f "$APK_PATH" ]; then
        log_error "APK file does not exist: $APK_PATH"
        exit 1
    fi
    
    # Execute analysis
    check_apk_analyzer
    
    log_info "Starting to analyze APK: $(basename "$APK_PATH")"
    
    if [ "$VERBOSE" = true ]; then
        python3 "$APK_ANALYZER" --apk "$APK_PATH" --verbose
    else
        python3 "$APK_ANALYZER" --apk "$APK_PATH"
    fi
}

# Unpacking function (original function)
dump_apk() {
    local PACKAGE_NAME=""
    local OUTPUT_DIR="./dex_output"
    local DEEP_SEARCH=false
    local BYPASS_ANTIDEBUG=false
    local VERBOSE=false
    
    # If it is dumpSubcommands, remove the first parameter
    if [ "$1" = "dump" ]; then
        shift
    fi
    
    # Parse parameters (compatible with original syntax)
    while [[ $# -gt 0 ]]; do
        case $1 in
            -p|--package)
                PACKAGE_NAME="$2"
                shift 2
                ;;
            -o|--output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            -d|--deep-search)
                DEEP_SEARCH=true
                shift
                ;;
            -b|--bypass-antidebug)
                BYPASS_ANTIDEBUG=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -t|--detect-protection)
                log_warning "⚠️  --detect-protection Parameter deprecated"
                log_info "💡 Please use new command to analyze APK: android-armor-breaker analyze --apk <apkfile_path>"
                shift
                ;;
            -h|--help)
                show_dump_help
                exit 0
                ;;
            *)
                # If -p/--package is not specified, the first non-option parameter is treated as package name
                if [ -z "$PACKAGE_NAME" ]; then
                    PACKAGE_NAME="$1"
                    shift
                else
                    log_warning "Unknown parameter: $1"
                    shift
                fi
                ;;
        esac
    done
    
    # Verify required parameters
    if [ -z "$PACKAGE_NAME" ]; then
        log_error "Please specify application package name"
        echo ""
        show_dump_help
        exit 1
    fi
    
    # create Output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Display execution information
    log_info "Target application: $PACKAGE_NAME"
    log_info "Output directory: $OUTPUT_DIR"
    
    if [ "$DEEP_SEARCH" = true ]; then
        log_info "Deep search mode: enable"
    fi
    if [ "$BYPASS_ANTIDEBUG" = true ]; then
        log_info "Anti-debug bypass: enable"
    fi
    if [ "$VERBOSE" = true ]; then
        log_info "Verbose mode: Enabled"
    fi
    
    # Build Python command parameters
    local PYTHON_ARGS="--package $PACKAGE_NAME --output $OUTPUT_DIR"
    
    if [ "$DEEP_SEARCH" = true ]; then
        PYTHON_ARGS="$PYTHON_ARGS --deep-search"
    fi
    if [ "$BYPASS_ANTIDEBUG" = true ]; then
        PYTHON_ARGS="$PYTHON_ARGS --bypass-antidebug"
    fi
    if [ "$VERBOSE" = true ]; then
        PYTHON_ARGS="$PYTHON_ARGS --verbose"
    fi
    
    # Execute Python script
    log_info "start Execute unpacking..."
    python3 "$PYTHON_SCRIPT" $PYTHON_ARGS
    
    # Check execution result
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Unpacking task completed!"
        log_info "DEX files saved to: $OUTPUT_DIR"
    else
        log_error "Unpacking task failed (Exit code: $EXIT_CODE)"
        exit $EXIT_CODE
    fi
}

# Main function
main() {
    # If no parameters, display help
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    # Check whether the first parameter is a Subcommand
    case "$1" in
        analyze)
            analyze_apk "$@"
            ;;
        dump)
            dump_apk "$@"
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            # If there are no Subcommands, the DefaultExecute unpacking function (backward compatibility)
            # Check if parameter is a package name (does not start with -)
            if [[ "$1" == -* ]]; then
                # Options，Execute unpacking
                dump_apk "$@"
            else
                # Might be a package name, check if it contains . character (package name characteristic)
                if [[ "$1" == *.* ]]; then
                    log_info "Detected package_name format, execute unpacking function"
                    dump_apk "$@"
                else
                    # Unknown command
                    log_error "Unknown command: $1"
                    echo ""
                    show_help
                    exit 1
                fi
            fi
            ;;
    esac
}

# execute Main function
main "$@"