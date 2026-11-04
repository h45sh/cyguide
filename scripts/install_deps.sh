#!/usr/bin/env bash
# CyGuide System Dependency Installer
# Automatically installs recommended security tools and their requirements.

set -e

echo "========================================="
echo " CyGuide System Dependency Installer"
echo "========================================="

TOOLS="nmap gobuster nikto whois"
# Note: subfinder is sometimes packaged directly, or available via Go. 
# We'll try to install it from the package manager.

if command -v apt-get >/dev/null 2>&1; then
    echo "[*] Detected Debian/Ubuntu based system (apt)."
    echo "[*] Installing: $TOOLS subfinder libxml-writer-perl"
    
    sudo apt-get update
    sudo apt-get install -y $TOOLS libxml-writer-perl
    
    # Try to install subfinder if available, otherwise suggest go install
    if ! sudo apt-get install -y subfinder 2>/dev/null; then
        echo "[!] subfinder not found in default apt repos. You may need to install it via Go:"
        echo "    go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@v2.6.6"
    fi
    
elif command -v pacman >/dev/null 2>&1; then
    echo "[*] Detected Arch Linux based system (pacman)."
    echo "[*] Installing: $TOOLS subfinder perl-xml-writer"
    
    sudo pacman -Sy --noconfirm --needed $TOOLS subfinder perl-xml-writer

elif command -v dnf >/dev/null 2>&1; then
    echo "[*] Detected Fedora/RHEL based system (dnf)."
    echo "[*] Installing: $TOOLS perl-XML-Writer"
    
    sudo dnf install -y $TOOLS perl-XML-Writer
    
    if ! sudo dnf install -y subfinder 2>/dev/null; then
        echo "[!] subfinder not found in default dnf repos. You may need to install it via Go:"
        echo "    go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@v2.6.6"
    fi

elif command -v brew >/dev/null 2>&1; then
    echo "[*] Detected macOS (Homebrew)."
    echo "[*] Installing: $TOOLS subfinder"
    
    brew install $TOOLS subfinder
    # Brew usually handles Nikto's Perl dependencies automatically.

else
    echo "[-] Unsupported package manager. Please manually install:"
    echo "    1. nmap"
    echo "    2. gobuster"
    echo "    3. nikto"
    echo "    4. whois"
    echo "    5. subfinder"
    echo "    6. perl-xml-writer (or libxml-writer-perl depending on your distro)"
    exit 1
fi

echo "========================================="
echo "✅ Installation complete!"
echo "You can now run CyGuide with full tool support."
